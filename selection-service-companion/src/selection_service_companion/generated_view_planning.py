"""Frozen Generated Mask propagation helper for legacy reference fixtures.

The product server exposes no Generated Mask route and no current product path
invokes this helper. The ``generated-view-mask/v1`` identity is retained only
to replay frozen migration fixtures; it cannot validate as a current artifact
or capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from .support_probe import AnchorSupportProbeCamera


LEGACY_GENERATED_VIEW_MASK_POLICY_VERSION = "generated-view-mask/v1"

# Opacity gate: alpha >= 0.5 is exactly logitOpacity >= 0 (support probe parity).
_MIN_LOGIT_OPACITY = 0.0
_MAX_SYNTHESIZED_PROMPTS = 3


@dataclass(frozen=True)
class SynthesizedViewPrompts:
    """Deterministic include prompts plus the propagation diagnostic count."""

    prompts: tuple[tuple[int, int], ...]
    projected_support_count: int


def _collect_support_means(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    camera: AnchorSupportProbeCamera,
    mask: bytes,
) -> list[tuple[float, float, float]]:
    """Collect world means whose projection lands on a set Stable Mask pixel.

    The gating is identical to the Anchor support probe: camera-space depth in
    [near, far], a rounded pinhole pixel in bounds, opacity at least 0.5, and
    the LSB-first mask bit set at that pixel.
    """

    matrix = camera.world_to_camera
    if len(matrix) != 16:
        raise ValueError("Generated View planning camera is malformed")
    if len(mask) != (camera.width * camera.height + 7) // 8:
        raise ValueError("Generated View planning mask does not match the camera")
    support: list[tuple[float, float, float]] = []
    for means_view, logit_view in planes:
        means = means_view.cast("f")
        logits = logit_view.cast("f")
        if len(means) != 3 * len(logits):
            raise ValueError("Generated View planning planes are inconsistent")
        for index in range(len(logits)):
            base = 3 * index
            camera_x = (
                matrix[0] * means[base]
                + matrix[1] * means[base + 1]
                + matrix[2] * means[base + 2]
                + matrix[3]
            )
            camera_y = (
                matrix[4] * means[base]
                + matrix[5] * means[base + 1]
                + matrix[6] * means[base + 2]
                + matrix[7]
            )
            camera_z = (
                matrix[8] * means[base]
                + matrix[9] * means[base + 1]
                + matrix[10] * means[base + 2]
                + matrix[11]
            )
            if camera_z < camera.near or camera_z > camera.far:
                continue
            u = int(round(camera.fx * (camera_x / camera_z) + camera.cx))
            v = int(round(camera.fy * (camera_y / camera_z) + camera.cy))
            if u < 0 or u >= camera.width or v < 0 or v >= camera.height:
                continue
            if logits[index] < _MIN_LOGIT_OPACITY:
                continue
            pixel = v * camera.width + u
            if (mask[pixel >> 3] >> (pixel & 7)) & 1:
                support.append(
                    (means[base], means[base + 1], means[base + 2])
                )
    return support


def synthesize_legacy_view_prompts(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    anchor_camera: AnchorSupportProbeCamera,
    view_camera: AnchorSupportProbeCamera,
    mask: bytes,
    max_prompts: int = _MAX_SYNTHESIZED_PROMPTS,
) -> SynthesizedViewPrompts | None:
    """Project Anchor mask support into the Generated View as include prompts.

    The prompt set is deterministic: the robust centroid pixel first, then
    the farthest distinct support pixels. An empty projection — the Generated
    View simply does not observe the Anchor's support — yields no prompts and
    fails Mask production closed instead of inventing a prompt.
    """

    if max_prompts < 1:
        raise ValueError("Generated View Mask propagation requires one prompt")
    support = _collect_support_means(planes=planes, camera=anchor_camera, mask=mask)
    if not support:
        return None
    matrix = view_camera.world_to_camera
    if len(matrix) != 16:
        raise ValueError("Generated View Mask propagation camera is malformed")
    projected: list[tuple[int, int]] = []
    for point in support:
        camera_x = (
            matrix[0] * point[0] + matrix[1] * point[1] + matrix[2] * point[2] + matrix[3]
        )
        camera_y = (
            matrix[4] * point[0] + matrix[5] * point[1] + matrix[6] * point[2] + matrix[7]
        )
        camera_z = (
            matrix[8] * point[0] + matrix[9] * point[1] + matrix[10] * point[2] + matrix[11]
        )
        if camera_z < view_camera.near or camera_z > view_camera.far:
            continue
        u = int(round(view_camera.fx * (camera_x / camera_z) + view_camera.cx))
        v = int(round(view_camera.fy * (camera_y / camera_z) + view_camera.cy))
        if 0 <= u < view_camera.width and 0 <= v < view_camera.height:
            projected.append((u, v))
    if not projected:
        return None
    centroid = (
        int(round(median(pixel[0] for pixel in projected))),
        int(round(median(pixel[1] for pixel in projected))),
    )
    centroid = (
        min(max(centroid[0], 0), view_camera.width - 1),
        min(max(centroid[1], 0), view_camera.height - 1),
    )
    unique = sorted(set(projected))
    farthest_first = sorted(
        (pixel for pixel in unique if pixel != centroid),
        key=lambda pixel: (
            -((pixel[0] - centroid[0]) ** 2 + (pixel[1] - centroid[1]) ** 2),
            pixel[0],
            pixel[1],
        ),
    )
    prompts = tuple([centroid, *farthest_first][:max_prompts])
    return SynthesizedViewPrompts(
        prompts=prompts,
        projected_support_count=len(projected),
    )


__all__ = [
    "LEGACY_GENERATED_VIEW_MASK_POLICY_VERSION",
    "SynthesizedViewPrompts",
    "synthesize_legacy_view_prompts",
]
