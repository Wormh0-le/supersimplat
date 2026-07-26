"""Versioned Generated View planning and cross-view Mask propagation policy.

The ``generated-view-planner/v1`` and ``generated-view-mask/v1`` policies are
pure CPU geometry over immutable mmap planes, exactly like the Anchor support
probe: they never import the locked renderer runtime (no torch, no gsplat)
and never classify Stable Gaussian IDs or ownership. Planning derives a
robust Seed Region from the confirmed Anchor's mask-conditioned Gaussian
support and sweeps a deterministic anchor-relative orbit; propagation
projects the same support into a Generated View camera to synthesize the
point prompts of one single-frame SAM pass.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Iterable, Mapping, Sequence

from .support_probe import AnchorSupportProbeCamera


AI_SELECT_GENERATED_VIEW_PLANNER_VERSION = "generated-view-planner/v1"
AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION = "generated-view-mask/v1"

# Ticket 06 publishes the first planner-owned ring neighbours only; Ticket 08
# owns the adaptive coverage-driven stop policy and larger budgets.
GENERATED_VIEW_PLAN_COUNT = 2
_ORBIT_AZIMUTH_OFFSETS_DEGREES = (45.0, -45.0)
# A conservative floor preserves the tiny-support framing case, matching the
# proven Seed Region arithmetic of the reference planner.
_MIN_SEED_RADIUS = 0.05
# Opacity gate: alpha >= 0.5 is exactly logitOpacity >= 0 (support probe parity).
_MIN_LOGIT_OPACITY = 0.0
_MAX_SYNTHESIZED_PROMPTS = 3


@dataclass(frozen=True)
class MaskSupportSeed:
    """A robust framing hint derived from mask-conditioned Gaussian support."""

    center: tuple[float, float, float]
    radius: float
    support_count: int


@dataclass(frozen=True)
class PlannedGeneratedView:
    """One planner-owned camera candidate in the editor CameraBinding shape."""

    view_id: str
    camera_binding: Mapping[str, object]


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


def derive_mask_support_seed(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    camera: AnchorSupportProbeCamera,
    mask: bytes,
) -> MaskSupportSeed | None:
    """Estimate a robust Seed Region from mask-conditioned Gaussian support.

    A background splat can still sit inside the Anchor mask, so the framing
    center is computed in two passes: a per-axis median provisional center,
    rejection of clearly separated support, then the retained mean. The
    observed support count is reported independently of the rejection.
    """

    support = _collect_support_means(planes=planes, camera=camera, mask=mask)
    if not support:
        return None
    provisional = tuple(median(point[axis] for point in support) for axis in range(3))
    distances = [
        math.dist(point, provisional)  # type: ignore[arg-type]
        for point in support
    ]
    outlier_limit = max(_MIN_SEED_RADIUS, median(distances) * 3.0)
    retained = [
        point
        for point, distance in zip(support, distances, strict=True)
        if distance <= outlier_limit
    ]
    if not retained:
        retained = list(support)
    center = tuple(
        sum(point[axis] for point in retained) / len(retained) for axis in range(3)
    )
    radius = max(
        _MIN_SEED_RADIUS,
        median([math.dist(point, center) for point in retained]) * 2.5,  # type: ignore[arg-type]
    )
    return MaskSupportSeed(
        center=(float(center[0]), float(center[1]), float(center[2])),
        radius=radius,
        support_count=len(support),
    )


def _normalise(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) * float(value) for value in vector))
    if not math.isfinite(length) or length <= 1e-12:
        raise ValueError("Generated View planning direction is degenerate")
    return tuple(float(value) / length for value in vector)  # type: ignore[return-value]


def _cross(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _rotate_about(
    direction: Sequence[float], axis: Sequence[float], degrees: float
) -> tuple[float, float, float]:
    """Rotate a unit direction around a unit axis by Rodrigues' formula."""

    radians = math.radians(degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    cross = _cross(axis, direction)
    parallel = _dot(axis, direction)
    return tuple(
        direction[index] * cosine
        + cross[index] * sine
        + axis[index] * parallel * (1.0 - cosine)
        for index in range(3)
    )  # type: ignore[return-value]


def _orbit_axis(base_direction: Sequence[float]) -> tuple[float, float, float]:
    """Return the unit orbit axis perpendicular to the anchor direction.

    The axis is the component of world +z orthogonal to the anchor axis, so a
    level anchor keeps the historical world-z longitude orbit; the next world
    axis spans the orbit plane when the anchor is aligned with world +z.
    """

    for reference in ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)):
        projection = tuple(
            reference[index] - _dot(reference, base_direction) * base_direction[index]
            for index in range(3)
        )
        if sum(value * value for value in projection) > 1e-12:
            return _normalise(projection)
    raise ValueError("Generated View orbit axis is degenerate")


def _camera_binding_for(
    *,
    position: Sequence[float],
    target: Sequence[float],
    projection: Mapping[str, object],
) -> Mapping[str, object]:
    """Build one OpenCV camera-to-world CameraBinding looking at the target."""

    forward = _normalise(tuple(target[index] - position[index] for index in range(3)))
    world_up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    if abs(_dot(forward, world_up)) > 0.98:
        world_up = (0.0, 1.0, 0.0)
    right = _normalise(_cross(forward, world_up))
    down = _normalise(_cross(forward, right))
    # Row-major camera-to-world: its columns are the camera right/down/forward
    # axes in world coordinates, with the position as its translation.
    camera_to_world = [
        right[0], down[0], forward[0], float(position[0]),
        right[1], down[1], forward[1], float(position[1]),
        right[2], down[2], forward[2], float(position[2]),
        0.0, 0.0, 0.0, 1.0,
    ]
    return {
        "revision": 0,
        "cameraToWorld": camera_to_world,
        "projection": {
            "model": "pinhole",
            "fx": float(projection["fx"]),  # type: ignore[arg-type]
            "fy": float(projection["fy"]),  # type: ignore[arg-type]
            "cx": float(projection["cx"]),  # type: ignore[arg-type]
            "cy": float(projection["cy"]),  # type: ignore[arg-type]
            "width": int(projection["width"]),  # type: ignore[arg-type]
            "height": int(projection["height"]),  # type: ignore[arg-type]
            "near": float(projection["near"]),  # type: ignore[arg-type]
            "far": float(projection["far"]),  # type: ignore[arg-type]
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }


def plan_first_generated_views(
    *,
    camera_binding: Mapping[str, object],
    seed: MaskSupportSeed,
) -> tuple[PlannedGeneratedView, ...]:
    """Sweep the first deterministic anchor-relative orbit neighbours.

    The orbit keeps the proven planner arithmetic: the ring distance never
    collapses below four Seed radii or four near planes, and the anchor axis
    sweeps around the axis perpendicular to the anchor direction. Every
    candidate inherits the exact Anchor pinhole projection and resolution.
    """

    camera_to_world = camera_binding.get("cameraToWorld")
    projection = camera_binding.get("projection")
    if (
        not isinstance(camera_to_world, list)
        or len(camera_to_world) != 16
        or not isinstance(projection, Mapping)
    ):
        raise ValueError("Generated View planning Anchor camera is malformed")
    anchor_position = (
        float(camera_to_world[3]),
        float(camera_to_world[7]),
        float(camera_to_world[11]),
    )
    target = seed.center
    distance = max(
        math.dist(anchor_position, target),
        seed.radius * 4.0,
        float(projection["near"]) * 4.0,  # type: ignore[arg-type]
    )
    base_direction = _normalise(
        tuple(anchor_position[index] - target[index] for index in range(3))
    )
    orbit_axis = _orbit_axis(base_direction)
    views: list[PlannedGeneratedView] = []
    for index, azimuth_offset in enumerate(
        _ORBIT_AZIMUTH_OFFSETS_DEGREES[:GENERATED_VIEW_PLAN_COUNT]
    ):
        direction = _rotate_about(base_direction, orbit_axis, azimuth_offset)
        position = tuple(
            float(target[axis]) + distance * direction[axis] for axis in range(3)
        )
        views.append(
            PlannedGeneratedView(
                view_id=f"generated-{index:02d}",
                camera_binding=_camera_binding_for(
                    position=position,
                    target=target,
                    projection=projection,
                ),
            )
        )
    return tuple(views)


def synthesize_view_prompts(
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
    "AI_SELECT_GENERATED_VIEW_MASK_POLICY_VERSION",
    "AI_SELECT_GENERATED_VIEW_PLANNER_VERSION",
    "GENERATED_VIEW_PLAN_COUNT",
    "MaskSupportSeed",
    "PlannedGeneratedView",
    "SynthesizedViewPrompts",
    "derive_mask_support_seed",
    "plan_first_generated_views",
    "synthesize_view_prompts",
]
