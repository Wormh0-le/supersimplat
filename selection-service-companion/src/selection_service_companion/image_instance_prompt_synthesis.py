"""Deterministic Route B prompt synthesis for one static SAM 3 Image View.

This module projects the compact TargetGeometryHint visible-surface samples
through the exact Generated View CameraBinding. It has no renderer, tracker,
Multiplex, scene-snapshot, mask-propagation, or Gaussian-classification role.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Mapping, Sequence

from .digests import canonical_json_digest


AI_SELECT_IMAGE_INSTANCE_PROMPT_SYNTHESIS_POLICY_VERSION = (
    'image-instance-prompt-synthesis/v1'
)

_MAX_POSITIVE_POINTS = 3
_MAX_NEGATIVE_POINTS = 2


@dataclass(frozen=True)
class SynthesizedImageInstancePrompt:
    """One compact prompt payload without browser-owned artifact identity."""

    positive_points: tuple[tuple[int, int], ...]
    negative_points: tuple[tuple[int, int], ...]
    positive_box: tuple[int, int, int, int]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class LimitedImageInstancePrompt:
    """Conservative recovery when geometry cannot support a local prompt."""

    diagnostics: tuple[str, ...]


def prompt_synthesis_policy_descriptor() -> dict[str, object]:
    """Return every policy value that can affect prompt selection."""

    return {
        'version': AI_SELECT_IMAGE_INSTANCE_PROMPT_SYNTHESIS_POLICY_VERSION,
        'positiveInstanceBoxes': 1,
        'maxPositivePoints': _MAX_POSITIVE_POINTS,
        'maxNegativePoints': _MAX_NEGATIVE_POINTS,
        'coordinateConvention': 'authoritative-pixel-xyxy/v1',
        'pointSelection': 'farthest-point-projection-samples/v1',
        'negativePointPolicy': 'none/v1',
    }


def prompt_synthesis_policy_digest() -> str:
    return canonical_json_digest(prompt_synthesis_policy_descriptor())


def _camera_axes(
    camera_binding: Mapping[str, object],
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    camera_to_world = camera_binding.get('cameraToWorld')
    if not isinstance(camera_to_world, list) or len(camera_to_world) != 16:
        raise ValueError('Prompt synthesis CameraBinding is malformed.')
    values = [float(value) for value in camera_to_world]
    return (
        (values[0], values[4], values[8]),
        (values[1], values[5], values[9]),
        (values[2], values[6], values[10]),
        (values[3], values[7], values[11]),
    )


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _project_visible_points(
    *,
    visible_points: Sequence[Sequence[float]],
    camera_binding: Mapping[str, object],
    width: int,
    height: int,
) -> tuple[list[tuple[int, int]], int, int]:
    """Project finite hint samples while retaining only true in-frame support."""

    projection = camera_binding.get('projection')
    if not isinstance(projection, Mapping):
        raise ValueError('Prompt synthesis CameraBinding projection is malformed.')
    fx = float(projection['fx'])
    fy = float(projection['fy'])
    cx = float(projection['cx'])
    cy = float(projection['cy'])
    near = float(projection['near'])
    far = float(projection['far'])
    if (
        not all(math.isfinite(value) for value in (fx, fy, cx, cy, near, far))
        or fx <= 0
        or fy <= 0
        or near <= 0
        or far <= near
        or width <= 0
        or height <= 0
    ):
        raise ValueError('Prompt synthesis CameraBinding projection is invalid.')

    right, down, forward, position = _camera_axes(camera_binding)
    samples: list[tuple[int, int]] = []
    clipped_count = 0
    depth_valid_count = 0
    for point in visible_points:
        if len(point) != 3 or not all(math.isfinite(float(value)) for value in point):
            continue
        offset = tuple(float(point[index]) - position[index] for index in range(3))
        camera_x = _dot(right, offset)
        camera_y = _dot(down, offset)
        camera_z = _dot(forward, offset)
        if camera_z < near or camera_z > far:
            continue
        depth_valid_count += 1
        x_float = fx * (camera_x / camera_z) + cx
        y_float = fy * (camera_y / camera_z) + cy
        if not math.isfinite(x_float) or not math.isfinite(y_float):
            continue
        x_raw = int(round(x_float))
        y_raw = int(round(y_float))
        if x_raw < 0 or x_raw >= width or y_raw < 0 or y_raw >= height:
            clipped_count += 1
            continue
        samples.append((x_raw, y_raw))
    return samples, clipped_count, depth_valid_count


def _select_positive_points(
    samples: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Select up to three spatially diverse deterministic positive points."""

    unique = list(dict.fromkeys(samples))
    if not unique:
        return ()
    center_x = median(sample[0] for sample in unique)
    center_y = median(sample[1] for sample in unique)
    first = min(
        range(len(unique)),
        key=lambda index: (
            (unique[index][0] - center_x) ** 2
            + (unique[index][1] - center_y) ** 2,
            index,
        ),
    )
    selected = [unique[first]]
    while len(selected) < min(_MAX_POSITIVE_POINTS, len(unique)):
        candidate = max(
            (
                index
                for index, sample in enumerate(unique)
                if sample not in selected
            ),
            key=lambda index: (
                min(
                    (unique[index][0] - chosen[0]) ** 2
                    + (unique[index][1] - chosen[1]) ** 2
                    for chosen in selected
                ),
                -index,
            ),
        )
        selected.append(unique[candidate])
    return tuple(selected)


def synthesize_image_instance_prompt(
    *,
    visible_points: Sequence[Sequence[float]],
    camera_binding: Mapping[str, object],
    width: int,
    height: int,
) -> SynthesizedImageInstancePrompt | LimitedImageInstancePrompt:
    """Create a box + 1--3 points or report semantic prompt unavailability.

    The current policy deliberately has zero negative points: there is no
    trustworthy local-background model in a geometry hint, so inventing one
    would turn missing evidence into a false negative constraint.
    """

    samples, clipped_count, depth_valid_count = _project_visible_points(
        visible_points=visible_points,
        camera_binding=camera_binding,
        width=width,
        height=height,
    )
    diagnostics: list[str] = []
    if depth_valid_count < len(visible_points):
        diagnostics.append('support-outside-camera-clipping')
    if clipped_count:
        diagnostics.append('target-projection-clipped')
    if not samples:
        if clipped_count:
            diagnostics.append('target-materially-clipped')
        diagnostics.append('no-in-frame-visible-surface-support')
        return LimitedImageInstancePrompt(diagnostics=tuple(diagnostics))
    # More off-image samples than reliable in-frame samples is insufficient
    # support for a bounded positive box. Equal support can still describe an
    # object crossing one image edge, and is retained with a clipping reason.
    if clipped_count > len(samples):
        diagnostics.append('target-materially-clipped')
        return LimitedImageInstancePrompt(diagnostics=tuple(diagnostics))
    x_values = [sample[0] for sample in samples]
    y_values = [sample[1] for sample in samples]
    x0 = min(x_values)
    y0 = min(y_values)
    x1 = max(x_values) + 1
    y1 = max(y_values) + 1
    diagnostics.insert(0, f'projected-support:{len(samples)}')
    if len(set(samples)) < 2:
        diagnostics.append('sparse-projectable-support')
    return SynthesizedImageInstancePrompt(
        positive_points=_select_positive_points(samples),
        negative_points=(),
        positive_box=(x0, y0, x1, y1),
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    'AI_SELECT_IMAGE_INSTANCE_PROMPT_SYNTHESIS_POLICY_VERSION',
    'LimitedImageInstancePrompt',
    'SynthesizedImageInstancePrompt',
    'prompt_synthesis_policy_descriptor',
    'prompt_synthesis_policy_digest',
    'synthesize_image_instance_prompt',
]
