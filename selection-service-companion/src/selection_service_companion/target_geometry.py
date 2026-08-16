"""Ticket 08 TargetGeometryHint and bounded local Key-View planning policies.

The ``target-geometry/v2`` policy compresses the exact confirmed Anchor Stable
Mask into one compact visible-surface geometry hint, and the
``local-key-view-planner/v2`` policy turns that hint into a small bounded local
Key-View batch. Both policies are pure CPU geometry over immutable mmap planes
and plain mappings, exactly like the Anchor support probe: they never import
the locked renderer runtime (no torch, no gsplat), never run SAM inference,
and never classify Stable Gaussian IDs, sample weights, or ownership. The hint
is localization, framing, and later Prompt-synthesis context only.

The visible-surface seam is the first-hit surface at Gaussian-mean granularity
(the Final Spec v1.3 §9 "equivalent visible-surface seam"): per set Stable Mask
pixel, the nearest in-frame Gaussian with alpha >= 0.5 contributes its world
mean. A production depth-render integration is deliberately deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Iterable, Mapping, Sequence

from .digests import canonical_json_digest
from .support_probe import AnchorSupportProbeCamera


AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION = "target-geometry/v2"
AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION = "local-key-view-planner/v2"
TARGET_GEOMETRY_HINT_SCHEMA_VERSION = 2
LOCAL_KEY_VIEW_PLAN_SCHEMA_VERSION = 1

# Opacity gate: alpha >= 0.5 is exactly logitOpacity >= 0 (support probe parity).
_MIN_LOGIT_OPACITY = 0.0
_MAX_VISIBLE_POINTS = 64
_OUTLIER_MIN_DISTANCE = 0.05
_OUTLIER_MEDIAN_FACTOR = 3.0
# Scaled MAD approximates a standard-deviation span without ever trusting raw
# extrema; the epsilon floor keeps thin/degenerate targets finite.
_EXTENT_MAD_SCALE = 1.4826
_EXTENT_EPSILON = 1e-3
_SPARSE_SUPPORT_COUNT = 8
_SEPARATED_DROP_FRACTION = 0.25
_PROMPT_SUPPORT_MIN_COUNT = 4
_PROMPT_SUPPORT_PROMOTABLE_REASONS = frozenset({"separatedSupportFiltered"})

# Bounded local movement: the ring distance never collapses below four extent
# radii or four near planes, and candidates inherit the exact Anchor pinhole
# projection, resolution, and clipping.
_EXTENT_RADIUS_FLOOR = 0.05
_DISTANCE_EXTENT_FACTOR = 4.0
_DISTANCE_NEAR_FACTOR = 4.0
# Fixed deterministic (azimuth, elevation) offset sequence in degrees. The
# current fixed configuration schedules four initial automatic Generated
# Views, inside the normative 4–8 range; later compatibility batches consume
# the remaining offsets inside the same bounded local fan.
_VIEW_OFFSETS_DEGREES = (
    (30.0, 0.0),
    (-30.0, 0.0),
    (0.0, 20.0),
    (60.0, 0.0),
    (-60.0, 0.0),
    (30.0, 20.0),
    (-30.0, 20.0),
    (0.0, 40.0),
)
_INITIAL_AUTOMATIC_VIEW_COUNT_MIN = 4
_INITIAL_AUTOMATIC_VIEW_COUNT_MAX = 8
_VIEWS_PER_BATCH = 4
_MIN_PROJECTED_SIZE_FRACTION = 0.05
_VISIBILITY_FAIL_FRACTION = 0.25
_VISIBILITY_LIMITED_FRACTION = 0.5
_REPLACEMENT_DISTANCE_FACTORS = (0.7, 0.45)


class GeometryUnavailableError(ValueError):
    """The confirmed Anchor Stable Mask has no usable first-hit support."""


class PlanExhaustedError(ValueError):
    """No further bounded local Key-View batch exists."""


class PlannerFailureError(ValueError):
    """Every candidate in the batch failed conservative validation."""


@dataclass(frozen=True)
class TargetGeometryHintDerivation:
    """The geometric payload of one TargetGeometryHintArtifact."""

    center: tuple[float, float, float]
    extent: tuple[float, float, float]
    visible_points: tuple[tuple[float, float, float], ...]
    quality: str
    reasons: tuple[str, ...]
    prompt_support: str


@dataclass(frozen=True)
class PlannedLocalKeyView:
    """One planner-owned Key-View candidate in the editor CameraBinding shape."""

    view_id: str
    camera_binding: Mapping[str, object]
    quality: str
    reasons: tuple[str, ...]


def target_geometry_policy_descriptor() -> dict[str, object]:
    """The versioned numeric identity of the geometry derivation policy."""

    return {
        "version": AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION,
        "minLogitOpacity": _MIN_LOGIT_OPACITY,
        "maxVisiblePoints": _MAX_VISIBLE_POINTS,
        "outlierMinDistance": _OUTLIER_MIN_DISTANCE,
        "outlierMedianFactor": _OUTLIER_MEDIAN_FACTOR,
        "extentMadScale": _EXTENT_MAD_SCALE,
        "extentEpsilon": _EXTENT_EPSILON,
        "sparseSupportCount": _SPARSE_SUPPORT_COUNT,
        "separatedDropFraction": _SEPARATED_DROP_FRACTION,
        "promptSupportMinCount": _PROMPT_SUPPORT_MIN_COUNT,
        "promptSupportPromotableReasons": sorted(_PROMPT_SUPPORT_PROMOTABLE_REASONS),
        "visiblePointIdentity": "distinct-first-hit-world-mean-v1",
    }


def target_geometry_policy_digest() -> str:
    return canonical_json_digest(target_geometry_policy_descriptor())


def prompt_support_is_usable(
    visible_points: Sequence[Sequence[float]], reasons: Sequence[str]
) -> bool:
    """Validate the semantic meaning of a published Prompt Support enum."""

    distinct_points = {
        (float(point[0]), float(point[1]), float(point[2]))
        for point in visible_points
    }
    return (
        len(distinct_points) >= _PROMPT_SUPPORT_MIN_COUNT
        and set(reasons).issubset(_PROMPT_SUPPORT_PROMOTABLE_REASONS)
    )


def local_key_view_policy_descriptor() -> dict[str, object]:
    """The versioned numeric identity of the local Key-View planner policy."""

    return {
        "version": AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION,
        "extentRadiusFloor": _EXTENT_RADIUS_FLOOR,
        "distanceExtentFactor": _DISTANCE_EXTENT_FACTOR,
        "distanceNearFactor": _DISTANCE_NEAR_FACTOR,
        "viewOffsetsDegrees": [
            [azimuth, elevation] for azimuth, elevation in _VIEW_OFFSETS_DEGREES
        ],
        "initialAutomaticViewCountRange": [
            _INITIAL_AUTOMATIC_VIEW_COUNT_MIN,
            _INITIAL_AUTOMATIC_VIEW_COUNT_MAX,
        ],
        "initialAutomaticViewCount": _VIEWS_PER_BATCH,
        "viewsPerBatch": _VIEWS_PER_BATCH,
        "minProjectedSizeFraction": _MIN_PROJECTED_SIZE_FRACTION,
        "visibilityFailFraction": _VISIBILITY_FAIL_FRACTION,
        "visibilityLimitedFraction": _VISIBILITY_LIMITED_FRACTION,
        "replacementDistanceFactors": list(_REPLACEMENT_DISTANCE_FACTORS),
    }


def local_key_view_policy_digest() -> str:
    return canonical_json_digest(local_key_view_policy_descriptor())


def _collect_first_hit_support(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    camera: AnchorSupportProbeCamera,
    mask: bytes,
) -> list[tuple[float, float, float]]:
    """Collect the nearest visible Gaussian world mean per set Mask pixel.

    The gating is identical to the Anchor support probe: camera-space depth in
    [near, far], a rounded pinhole pixel in bounds, opacity at least 0.5, and
    the LSB-first mask bit set at that pixel. Per set pixel only the NEAREST
    (minimum-depth) Gaussian survives: its world mean is the first-hit
    visible-surface sample at that pixel. The result is ordered by ascending
    source pixel index (row-major), so it is deterministic for an immutable
    plane/camera/mask triple.
    """

    matrix = camera.world_to_camera
    if len(matrix) != 16:
        raise ValueError("Target Geometry camera is malformed")
    if len(mask) != (camera.width * camera.height + 7) // 8:
        raise ValueError("Target Geometry mask does not match the camera")
    best: dict[int, tuple[float, float, float, float]] = {}
    for means_view, logit_view in planes:
        means = means_view.cast("f")
        logits = logit_view.cast("f")
        if len(means) != 3 * len(logits):
            raise ValueError("Target Geometry planes are inconsistent")
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
            if not (mask[pixel >> 3] >> (pixel & 7)) & 1:
                continue
            current = best.get(pixel)
            if current is None or camera_z < current[0]:
                best[pixel] = (
                    camera_z,
                    means[base],
                    means[base + 1],
                    means[base + 2],
                )
    return [
        (sample[1], sample[2], sample[3])
        for _, sample in sorted(best.items())
    ]


def _distinct_points(
    points: Iterable[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Deduplicate first-hit world means without introducing protocol IDs."""

    seen: set[tuple[float, float, float]] = set()
    distinct: list[tuple[float, float, float]] = []
    for point in points:
        canonical = (float(point[0]), float(point[1]), float(point[2]))
        if canonical in seen:
            continue
        seen.add(canonical)
        distinct.append(canonical)
    return distinct


def _mask_touches_frame_border(
    *, camera: AnchorSupportProbeCamera, mask: bytes
) -> bool:
    """Report whether any set Stable Mask pixel lies on the frame border."""

    width = camera.width
    height = camera.height

    def pixel_set(pixel: int) -> bool:
        return bool((mask[pixel >> 3] >> (pixel & 7)) & 1)

    for u in range(width):
        if pixel_set(u) or pixel_set((height - 1) * width + u):
            return True
    for v in range(height):
        if pixel_set(v * width) or pixel_set(v * width + width - 1):
            return True
    return False


def derive_target_geometry_hint(
    *,
    planes: Iterable[tuple[memoryview, memoryview]],
    camera: AnchorSupportProbeCamera,
    mask: bytes,
) -> TargetGeometryHintDerivation | None:
    """Derive the compact visible-surface geometry hint for one exact Anchor.

    Returns ``None`` when the confirmed Anchor Stable Mask has no observable
    first-hit support; the route turns that into a fail-closed
    ``geometryUnavailable`` and never fabricates a hint. Center and extent use
    robust statistics (median and scaled MAD) rather than raw extrema, and
    clearly separated background support is filtered before either is computed.
    """

    points = _distinct_points(
        _collect_first_hit_support(planes=planes, camera=camera, mask=mask)
    )
    if not points:
        return None
    if len(points) > _MAX_VISIBLE_POINTS:
        stride = math.ceil(len(points) / _MAX_VISIBLE_POINTS)
        points = points[::stride]

    provisional = tuple(median(point[axis] for point in points) for axis in range(3))
    distances = [
        math.dist(point, provisional)  # type: ignore[arg-type]
        for point in points
    ]
    outlier_limit = max(_OUTLIER_MIN_DISTANCE, median(distances) * _OUTLIER_MEDIAN_FACTOR)
    retained = [
        point
        for point, distance in zip(points, distances, strict=True)
        if distance <= outlier_limit
    ]
    dropped_fraction = (len(points) - len(retained)) / len(points)
    if not retained:
        # There is no trustworthy localization when robust filtering rejects
        # every distinct support sample. Do not reintroduce those rejected
        # points as a formal Prompt input; the route turns this into the same
        # fail-closed geometryUnavailable surface as an empty mask support.
        return None

    center = tuple(median(point[axis] for point in retained) for axis in range(3))
    extent = tuple(
        max(
            _EXTENT_EPSILON,
            _EXTENT_MAD_SCALE
            * median(abs(point[axis] - center[axis]) for point in retained),
        )
        for axis in range(3)
    )

    reasons: list[str] = []
    if len(retained) < _SPARSE_SUPPORT_COUNT:
        reasons.append("sparseSupport")
    if dropped_fraction > _SEPARATED_DROP_FRACTION:
        reasons.append("separatedSupportFiltered")
    if _mask_touches_frame_border(camera=camera, mask=mask):
        reasons.append("frameBoundaryContact")
    prompt_support = (
        "usable"
        if len(retained) >= _PROMPT_SUPPORT_MIN_COUNT
        and set(reasons).issubset(_PROMPT_SUPPORT_PROMOTABLE_REASONS)
        else "limited"
    )
    return TargetGeometryHintDerivation(
        center=(float(center[0]), float(center[1]), float(center[2])),
        extent=(float(extent[0]), float(extent[1]), float(extent[2])),
        visible_points=tuple(retained),
        quality="limited" if reasons else "usable",
        reasons=tuple(reasons),
        prompt_support=prompt_support,
    )


def _normalise(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) * float(value) for value in vector))
    if not math.isfinite(length) or length <= 1e-12:
        raise ValueError("Local Key-View planning direction is degenerate")
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


def _azimuth_axis(base_direction: Sequence[float]) -> tuple[float, float, float]:
    """Return the unit azimuth axis perpendicular to the anchor direction.

    The axis is the component of world +z orthogonal to the anchor axis, so a
    level anchor sweeps around world z; the next world axis spans the fan
    plane when the anchor is aligned with world +z.
    """

    for reference in ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)):
        projection = tuple(
            reference[index] - _dot(reference, base_direction) * base_direction[index]
            for index in range(3)
        )
        if sum(value * value for value in projection) > 1e-12:
            return _normalise(projection)
    raise ValueError("Local Key-View azimuth axis is degenerate")


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


def _camera_axes(
    camera_binding: Mapping[str, object],
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Extract (right, down, forward, position) from a CameraBinding."""

    camera_to_world = camera_binding.get("cameraToWorld")
    if not isinstance(camera_to_world, list) or len(camera_to_world) != 16:
        raise ValueError("Local Key-View camera is malformed")
    right = (
        float(camera_to_world[0]),
        float(camera_to_world[4]),
        float(camera_to_world[8]),
    )
    down = (
        float(camera_to_world[1]),
        float(camera_to_world[5]),
        float(camera_to_world[9]),
    )
    forward = (
        float(camera_to_world[2]),
        float(camera_to_world[6]),
        float(camera_to_world[10]),
    )
    position = (
        float(camera_to_world[3]),
        float(camera_to_world[7]),
        float(camera_to_world[11]),
    )
    return right, down, forward, position


def _validate_candidate(
    *,
    camera_binding: Mapping[str, object],
    center: Sequence[float],
    extent_radius: float,
    visible_points: Sequence[Sequence[float]],
) -> tuple[bool, tuple[str, ...]]:
    """Conservatively validate one Key-View candidate against the hint.

    A candidate fails when the target center clips, when the projected target
    extent falls below the useful-size floor, or when too little of the
    first-hit visible surface still projects into the frame. A marginal
    candidate is accepted as Limited with evidence-backed reasons instead of
    being silently promoted.
    """

    right, down, forward, position = _camera_axes(camera_binding)
    projection = camera_binding.get("projection")
    if not isinstance(projection, Mapping):
        raise ValueError("Local Key-View camera projection is malformed")
    near = float(projection["near"])  # type: ignore[arg-type]
    far = float(projection["far"])  # type: ignore[arg-type]
    width = int(projection["width"])  # type: ignore[arg-type]
    height = int(projection["height"])  # type: ignore[arg-type]
    fx = float(projection["fx"])  # type: ignore[arg-type]
    fy = float(projection["fy"])  # type: ignore[arg-type]
    cx = float(projection["cx"])  # type: ignore[arg-type]
    cy = float(projection["cy"])  # type: ignore[arg-type]

    def camera_depth(point: Sequence[float]) -> tuple[float, float, float]:
        offset = tuple(point[index] - position[index] for index in range(3))
        return (
            _dot(right, offset),
            _dot(down, offset),
            _dot(forward, offset),
        )

    _, _, center_depth = camera_depth(center)
    if center_depth < near or center_depth > far:
        return False, ("targetOutsideClipping",)
    projected_size = max(fx, fy) * extent_radius / center_depth
    if projected_size < _MIN_PROJECTED_SIZE_FRACTION * min(width, height):
        return False, ("projectedSizeTooSmall",)

    observed = 0
    for point in visible_points:
        camera_x, camera_y, camera_z = camera_depth(point)
        if camera_z < near or camera_z > far:
            continue
        u = int(round(fx * (camera_x / camera_z) + cx))
        v = int(round(fy * (camera_y / camera_z) + cy))
        if 0 <= u < width and 0 <= v < height:
            observed += 1
    visibility = observed / len(visible_points) if visible_points else 0.0
    if visibility < _VISIBILITY_FAIL_FRACTION:
        return False, ("insufficientVisibility",)
    if visibility < _VISIBILITY_LIMITED_FRACTION:
        return True, ("reducedVisibility",)
    return True, ()


def plan_local_key_views(
    *,
    anchor_camera_binding: Mapping[str, object],
    center: Sequence[float],
    extent: Sequence[float],
    visible_points: Sequence[Sequence[float]],
    batch_ordinal: int,
) -> tuple[PlannedLocalKeyView, ...]:
    """Plan one bounded local Key-View batch from the geometry hint.

    Every candidate is a bounded local displacement from the Anchor around the
    hint center — left/right azimuth offsets plus modest elevation, never a
    room-scale orbit. Candidates that fail conservative validation trigger a
    bounded closer replacement; a candidate that still fails is dropped, and a
    batch with zero accepted views fails closed.
    """

    camera_to_world = anchor_camera_binding.get("cameraToWorld")
    projection = anchor_camera_binding.get("projection")
    if (
        not isinstance(camera_to_world, list)
        or len(camera_to_world) != 16
        or not isinstance(projection, Mapping)
    ):
        raise ValueError("Local Key-View planning Anchor camera is malformed")
    if batch_ordinal < 0:
        raise ValueError("Local Key-View batch ordinal is invalid")
    start = batch_ordinal * _VIEWS_PER_BATCH
    if start >= len(_VIEW_OFFSETS_DEGREES):
        raise PlanExhaustedError(
            "The bounded local Key-View policy has no further batch."
        )
    offsets = _VIEW_OFFSETS_DEGREES[start : start + _VIEWS_PER_BATCH]

    anchor_position = (
        float(camera_to_world[3]),
        float(camera_to_world[7]),
        float(camera_to_world[11]),
    )
    extent_radius = max(_EXTENT_RADIUS_FLOOR, max(float(value) for value in extent))
    distance = max(
        math.dist(anchor_position, center),  # type: ignore[arg-type]
        extent_radius * _DISTANCE_EXTENT_FACTOR,
        float(projection["near"]) * _DISTANCE_NEAR_FACTOR,  # type: ignore[arg-type]
    )
    base_direction = _normalise(
        tuple(anchor_position[index] - center[index] for index in range(3))
    )
    azimuth_axis = _azimuth_axis(base_direction)
    elevation_axis = _normalise(_cross(base_direction, azimuth_axis))

    views: list[PlannedLocalKeyView] = []
    for slot, (azimuth_degrees, elevation_degrees) in enumerate(offsets):
        direction = _rotate_about(base_direction, azimuth_axis, azimuth_degrees)
        # A positive elevation rotates around the elevation axis so the camera
        # rises along the azimuth axis (the world-up-ish direction).
        direction = _rotate_about(direction, elevation_axis, elevation_degrees)
        accepted: tuple[Mapping[str, object], tuple[str, ...]] | None = None
        for factor in (1.0, *_REPLACEMENT_DISTANCE_FACTORS):
            position = tuple(
                float(center[axis]) + distance * factor * direction[axis]
                for axis in range(3)
            )
            candidate = _camera_binding_for(
                position=position,
                target=center,
                projection=projection,
            )
            passed, reasons = _validate_candidate(
                camera_binding=candidate,
                center=center,
                extent_radius=extent_radius,
                visible_points=visible_points,
            )
            if passed:
                accepted = (candidate, reasons)
                break
        if accepted is None:
            continue
        candidate, reasons = accepted
        views.append(
            PlannedLocalKeyView(
                view_id=f"key-view-{batch_ordinal}-{slot}",
                camera_binding=candidate,
                quality="limited" if reasons else "usable",
                reasons=reasons,
            )
        )
    if not views:
        raise PlannerFailureError(
            "Every bounded local Key-View candidate failed validation."
        )
    return tuple(views)


__all__ = [
    "AI_SELECT_LOCAL_KEY_VIEW_PLANNER_VERSION",
    "AI_SELECT_TARGET_GEOMETRY_POLICY_VERSION",
    "GeometryUnavailableError",
    "LOCAL_KEY_VIEW_PLAN_SCHEMA_VERSION",
    "PlanExhaustedError",
    "PlannedLocalKeyView",
    "PlannerFailureError",
    "TARGET_GEOMETRY_HINT_SCHEMA_VERSION",
    "TargetGeometryHintDerivation",
    "derive_target_geometry_hint",
    "local_key_view_policy_descriptor",
    "local_key_view_policy_digest",
    "plan_local_key_views",
    "prompt_support_is_usable",
    "target_geometry_policy_descriptor",
    "target_geometry_policy_digest",
]
