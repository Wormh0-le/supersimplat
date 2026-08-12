"""Trusted reference per-view P/N/V Evidence for AI Select Ticket 14B.

This module owns the deliberately slower reference algorithm. It consumes
complete ``alpha * incoming-transmittance`` Contributor weights, keeps the
three Evidence channels independent, and never publishes a Candidate. Ticket
20's production same-decision path is a separate backend identity.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
from dataclasses import dataclass
from typing import Final

from .gaussian_evidence_contract import (
    GaussianEvidenceContractError,
    admit_gaussian_evidence,
    create_gaussian_evidence_artifact,
    is_gaussian_evidence_artifact,
)
from .digests import canonical_json_digest


REFERENCE_EVIDENCE_POLICY_SCHEMA_VERSION: Final = 1
REFERENCE_EVIDENCE_POLICY_ID: Final = "mask-region-evidence/reference-v1"
_MAX_MASK_PIXELS: Final = 16_777_216
_REGION_STRONG_POSITIVE: Final = "strong-positive-interior"
_REGION_BOUNDARY: Final = "boundary-ignore-band"
_REGION_LOCAL_NEGATIVE: Final = "local-negative-context-ring"
_REGION_FAR_NEUTRAL: Final = "far-neutral-region"
_CONTRIBUTOR_MASS_ATOL: Final = 2e-6
_CONTRIBUTOR_MASS_RTOL: Final = 1e-5


class ReferenceGaussianEvidenceError(ValueError):
    """Reference Evidence input or computation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalidReferenceEvidence",
        cause_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.cause_code = cause_code


@dataclass(frozen=True)
class PixelEvidenceWeight:
    """Independent P/N/V weights and an optional boundary diagnostic."""

    region: str
    positive: float
    negative: float
    visible: float
    boundary: float


@dataclass(frozen=True)
class PixelEvidenceWeights:
    """Immutable row-major weights derived from one exact Stable Mask."""

    width: int
    height: int
    values: tuple[PixelEvidenceWeight, ...]

    def at(self, x_px: int, y_px: int) -> PixelEvidenceWeight:
        if not 0 <= x_px < self.width or not 0 <= y_px < self.height:
            raise IndexError("AI Select Evidence pixel lies outside the Stable Mask.")
        return self.values[y_px * self.width + x_px]


def _policy_payload() -> dict[str, object]:
    return {
        "schemaVersion": REFERENCE_EVIDENCE_POLICY_SCHEMA_VERSION,
        "policyId": REFERENCE_EVIDENCE_POLICY_ID,
        "morphologyVersion": "chebyshev-mask-regions/v1",
        "positiveWeightPolicyVersion": "positive-interior-boundary-soft/v1",
        "negativeWeightPolicyVersion": "negative-local-context-ring/v1",
        "visibleWeightPolicyVersion": "visible-observation-roi/v1",
        "boundaryWeightPolicyVersion": "boundary-diagnostic/v1",
        "positiveInteriorErosionRadiusPx": 1,
        "boundaryBandRadiusPx": 1,
        "localNegativeOuterRadiusPx": 3,
        "strongPositiveWeight": 1.0,
        "boundaryPositiveWeight": 0.25,
        "localNegativeWeight": 1.0,
        "positiveVisibleWeight": 1.0,
        "boundaryVisibleWeight": 1.0,
        "localNegativeVisibleWeight": 1.0,
        "farNeutralPositiveWeight": 0.0,
        "farNeutralNegativeWeight": 0.0,
        "farNeutralVisibleWeight": 0.0,
        "boundaryDiagnosticWeight": 1.0,
    }


def default_reference_evidence_policy() -> dict[str, object]:
    """Return the exact independently-versioned Ticket 14B pixel policy."""

    payload = _policy_payload()
    return {**payload, "evidencePolicyDigest": canonical_json_digest(payload)}


def _is_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _validated_policy(value: object) -> dict[str, object]:
    expected = default_reference_evidence_policy()
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy is incomplete or unsupported."
        )
    payload = {
        key: item for key, item in value.items() if key != "evidencePolicyDigest"
    }
    if (
        value.get("schemaVersion") != REFERENCE_EVIDENCE_POLICY_SCHEMA_VERSION
        or value.get("policyId") != REFERENCE_EVIDENCE_POLICY_ID
        or value.get("evidencePolicyDigest") != canonical_json_digest(payload)
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy identity is invalid."
        )
    version_fields = (
        "morphologyVersion",
        "positiveWeightPolicyVersion",
        "negativeWeightPolicyVersion",
        "visibleWeightPolicyVersion",
        "boundaryWeightPolicyVersion",
    )
    if any(
        not isinstance(value[field], str) or not value[field].strip()
        for field in version_fields
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy versions are invalid."
        )
    integer_fields = (
        "positiveInteriorErosionRadiusPx",
        "boundaryBandRadiusPx",
        "localNegativeOuterRadiusPx",
    )
    if (
        any(
            isinstance(value[field], bool)
            or not isinstance(value[field], int)
            or value[field] < 0
            for field in integer_fields
        )
        or value["localNegativeOuterRadiusPx"] <= value["boundaryBandRadiusPx"]
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy radii are invalid."
        )
    weight_fields = tuple(key for key in expected if key.endswith("Weight"))
    if any(
        not _is_number(value[field]) or float(value[field]) < 0.0
        for field in weight_fields
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy weights must be finite and non-negative."
        )
    if any(
        float(value[field]) != 0.0
        for field in (
            "farNeutralPositiveWeight",
            "farNeutralNegativeWeight",
            "farNeutralVisibleWeight",
        )
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence far region must remain neutral."
        )
    return dict(value)


def _decoded_mask(value: object) -> tuple[int, int, tuple[bool, ...]]:
    if not isinstance(value, dict) or set(value) != {
        "encoding",
        "width",
        "height",
        "data",
        "digest",
    }:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence requires one complete Stable Mask artifact."
        )
    width = value.get("width")
    height = value.get("height")
    if (
        value.get("encoding") != "bitset-lsb-v1"
        or isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or width * height > _MAX_MASK_PIXELS
        or not isinstance(value.get("data"), str)
        or not isinstance(value.get("digest"), str)
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask artifact is invalid."
        )
    try:
        bits = base64.b64decode(value["data"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask encoding is invalid."
        ) from error
    pixel_count = width * height
    if len(bits) != (pixel_count + 7) // 8:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask length is invalid."
        )
    remainder = pixel_count % 8
    if remainder and bits[-1] & ~((1 << remainder) - 1):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask has non-zero trailing bits."
        )
    digest = f"sha256:{hashlib.sha256(bits).hexdigest()}"
    if value["digest"] != digest:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask digest does not match its bytes."
        )
    foreground = tuple(
        bool(bits[index // 8] & (1 << (index % 8))) for index in range(pixel_count)
    )
    if not any(foreground):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence requires a non-empty Stable Mask."
        )
    return width, height, foreground


def _chebyshev_distance(
    width: int,
    height: int,
    sources: tuple[bool, ...],
) -> list[int]:
    unreachable = width + height + 1
    result = [0 if is_source else unreachable for is_source in sources]
    for y_px in range(height):
        for x_px in range(width):
            index = y_px * width + x_px
            if result[index] == 0:
                continue
            best = result[index]
            if x_px > 0:
                best = min(best, result[index - 1] + 1)
            if y_px > 0:
                best = min(best, result[index - width] + 1)
                if x_px > 0:
                    best = min(best, result[index - width - 1] + 1)
                if x_px + 1 < width:
                    best = min(best, result[index - width + 1] + 1)
            result[index] = best
    for y_px in range(height - 1, -1, -1):
        for x_px in range(width - 1, -1, -1):
            index = y_px * width + x_px
            best = result[index]
            if x_px + 1 < width:
                best = min(best, result[index + 1] + 1)
            if y_px + 1 < height:
                best = min(best, result[index + width] + 1)
                if x_px > 0:
                    best = min(best, result[index + width - 1] + 1)
                if x_px + 1 < width:
                    best = min(best, result[index + width + 1] + 1)
            result[index] = best
    return result


def _distance_to_background(
    width: int,
    height: int,
    foreground: tuple[bool, ...],
) -> list[int]:
    padded_width = width + 2
    padded_height = height + 2
    padded_background = [True] * (padded_width * padded_height)
    for y_px in range(height):
        for x_px in range(width):
            padded_index = (y_px + 1) * padded_width + x_px + 1
            padded_background[padded_index] = not foreground[y_px * width + x_px]
    padded_distance = _chebyshev_distance(
        padded_width,
        padded_height,
        tuple(padded_background),
    )
    return [
        padded_distance[(y_px + 1) * padded_width + x_px + 1]
        for y_px in range(height)
        for x_px in range(width)
    ]


def derive_pixel_evidence_weights(
    mask_artifact: object,
    policy: object,
) -> PixelEvidenceWeights:
    """Derive explicit P/N/V regions without making far exterior negative."""

    validated_policy = _validated_policy(policy)
    width, height, foreground = _decoded_mask(mask_artifact)
    distance_to_foreground = _chebyshev_distance(width, height, foreground)
    distance_to_background = _distance_to_background(width, height, foreground)
    erosion_radius = int(validated_policy["positiveInteriorErosionRadiusPx"])
    boundary_radius = int(validated_policy["boundaryBandRadiusPx"])
    negative_outer_radius = int(validated_policy["localNegativeOuterRadiusPx"])
    values: list[PixelEvidenceWeight] = []
    for index, is_foreground in enumerate(foreground):
        if is_foreground and distance_to_background[index] > erosion_radius:
            values.append(
                PixelEvidenceWeight(
                    region=_REGION_STRONG_POSITIVE,
                    positive=float(validated_policy["strongPositiveWeight"]),
                    negative=0.0,
                    visible=float(validated_policy["positiveVisibleWeight"]),
                    boundary=0.0,
                )
            )
        elif is_foreground or distance_to_foreground[index] <= boundary_radius:
            values.append(
                PixelEvidenceWeight(
                    region=_REGION_BOUNDARY,
                    positive=(
                        float(validated_policy["boundaryPositiveWeight"])
                        if is_foreground
                        else 0.0
                    ),
                    negative=0.0,
                    visible=float(validated_policy["boundaryVisibleWeight"]),
                    boundary=float(validated_policy["boundaryDiagnosticWeight"]),
                )
            )
        elif distance_to_foreground[index] <= negative_outer_radius:
            values.append(
                PixelEvidenceWeight(
                    region=_REGION_LOCAL_NEGATIVE,
                    positive=0.0,
                    negative=float(validated_policy["localNegativeWeight"]),
                    visible=float(validated_policy["localNegativeVisibleWeight"]),
                    boundary=0.0,
                )
            )
        else:
            values.append(
                PixelEvidenceWeight(
                    region=_REGION_FAR_NEUTRAL,
                    positive=float(validated_policy["farNeutralPositiveWeight"]),
                    negative=float(validated_policy["farNeutralNegativeWeight"]),
                    visible=float(validated_policy["farNeutralVisibleWeight"]),
                    boundary=0.0,
                )
            )
    return PixelEvidenceWeights(width=width, height=height, values=tuple(values))


def _validated_stable_id_mapping(value: object) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(
            isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or stable_id < 0
            or stable_id > (1 << 32) - 1
            for stable_id in value
        )
        or len(set(value)) != len(value)
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor has an invalid Stable Gaussian ID row mapping."
        )
    return list(value)


def _raster_identity_matches_admission(
    raster: dict[str, object],
    admission: dict[str, object],
) -> bool:
    return all(
        raster[key] == admission[key]
        for key in (
            "rgbDigest",
            "rasterImplementationId",
            "evidenceBackendKind",
            "evidenceBackendId",
            "runtimeBuildId",
        )
    )


def _validated_reference_raster(
    value: object,
    admission_input: dict[str, object],
    admission: dict[str, object],
) -> tuple[int, int, list[int], list[list[list[int]]], list[list[list[float]]]]:
    required = {
        "width",
        "height",
        "rgbDigest",
        "stableGaussianIdsByTensorRow",
        "alpha",
        "contributorIds",
        "contributorWeights",
        "rasterImplementationId",
        "evidenceBackendKind",
        "evidenceBackendId",
        "runtimeBuildId",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor raster is incomplete."
        )
    width = value["width"]
    height = value["height"]
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or width * height > _MAX_MASK_PIXELS
        or not _raster_identity_matches_admission(value, admission)
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor raster identity or dimensions are invalid."
        )
    stable_ids_by_row = _validated_stable_id_mapping(
        value["stableGaussianIdsByTensorRow"]
    )
    render_working_set = admission_input.get("renderWorkingSet")
    if not isinstance(render_working_set, dict) or set(stable_ids_by_row) != set(
        render_working_set["stableGaussianIds"]
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor Stable ID mapping does not match the Render Working Set."
        )
    contributor_ids = value["contributorIds"]
    contributor_weights = value["contributorWeights"]
    alpha = value["alpha"]
    if (
        not isinstance(contributor_ids, list)
        or not isinstance(contributor_weights, list)
        or not isinstance(alpha, list)
        or len(contributor_ids) != height
        or len(contributor_weights) != height
        or len(alpha) != height
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor raster dimensions are incomplete."
        )
    copied_ids: list[list[list[int]]] = []
    copied_weights: list[list[list[float]]] = []
    has_contributor = False
    for id_row, weight_row, alpha_row in zip(
        contributor_ids, contributor_weights, alpha, strict=True
    ):
        if (
            not isinstance(id_row, list)
            or not isinstance(weight_row, list)
            or not isinstance(alpha_row, list)
            or len(id_row) != width
            or len(weight_row) != width
            or len(alpha_row) != width
        ):
            raise ReferenceGaussianEvidenceError(
                "AI Select reference Contributor raster dimensions are incomplete."
            )
        copied_id_row: list[list[int]] = []
        copied_weight_row: list[list[float]] = []
        for pixel_ids, pixel_weights, pixel_alpha in zip(
            id_row, weight_row, alpha_row, strict=True
        ):
            if (
                not isinstance(pixel_ids, list)
                or not isinstance(pixel_weights, list)
                or len(pixel_ids) != len(pixel_weights)
            ):
                raise ReferenceGaussianEvidenceError(
                    "AI Select reference Contributor chains are incomplete."
                )
            if (
                not _is_number(pixel_alpha)
                or float(pixel_alpha) < 0.0
                or float(pixel_alpha) > 1.0 + _CONTRIBUTOR_MASS_ATOL
            ):
                raise ReferenceGaussianEvidenceError(
                    "AI Select reference Contributor raster alpha is invalid."
                )
            copied_pixel_ids: list[int] = []
            copied_pixel_weights: list[float] = []
            observed_rows: set[int] = set()
            pixel_mass = 0.0
            for row_id, weight in zip(pixel_ids, pixel_weights, strict=True):
                if (
                    isinstance(row_id, bool)
                    or not isinstance(row_id, int)
                    or not _is_number(weight)
                    or float(weight) < 0.0
                    or float(weight) > 1.0
                    or row_id < -1
                    or row_id >= len(stable_ids_by_row)
                    or (row_id == -1 and float(weight) != 0.0)
                    or (row_id >= 0 and float(weight) <= 0.0)
                    or (row_id >= 0 and row_id in observed_rows)
                ):
                    raise ReferenceGaussianEvidenceError(
                        "AI Select reference Contributor chain contains an invalid row ID or alpha-transmittance weight."
                    )
                if row_id >= 0:
                    observed_rows.add(row_id)
                    pixel_mass += float(weight)
                    has_contributor = True
                copied_pixel_ids.append(row_id)
                copied_pixel_weights.append(float(weight))
            alpha_number = float(pixel_alpha)
            tolerance = _CONTRIBUTOR_MASS_ATOL + (
                _CONTRIBUTOR_MASS_RTOL * abs(alpha_number)
            )
            if (
                not math.isfinite(pixel_mass)
                or abs(pixel_mass - alpha_number) > tolerance
            ):
                raise ReferenceGaussianEvidenceError(
                    "AI Select reference Contributor mass does not match raster alpha."
                )
            copied_id_row.append(copied_pixel_ids)
            copied_weight_row.append(copied_pixel_weights)
        copied_ids.append(copied_id_row)
        copied_weights.append(copied_weight_row)
    if not has_contributor:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor raster has no complete support."
        )
    return width, height, stable_ids_by_row, copied_ids, copied_weights


def compute_reference_contributor_evidence(
    admission_input: object,
    mask_artifact: object,
    contributor_raster: object,
    policy: object,
) -> dict[str, object]:
    """Atomically compute one raw per-view artifact from complete Contributor w.

    Every supplied Contributor weight is already ``alpha * incoming T``. The
    full Render Working Set row mapping is validated before only Evidence
    Working Set IDs receive writes.
    """

    if not isinstance(admission_input, dict):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence admission input is invalid."
        )
    admission_result = admit_gaussian_evidence(admission_input)
    if admission_result["status"] != "admitted":
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence admission failed closed: "
            f"{admission_result['reason']}."
        )
    admission = admission_result["admission"]
    assert isinstance(admission, dict)
    validated_policy = _validated_policy(policy)
    if admission["evidencePolicyDigest"] != validated_policy["evidencePolicyDigest"]:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Policy does not match the admitted identity."
        )
    weights = derive_pixel_evidence_weights(mask_artifact, validated_policy)
    if (
        not isinstance(mask_artifact, dict)
        or mask_artifact.get("digest") != admission["stableMaskDigest"]
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence Stable Mask does not match the admitted identity."
        )
    width, height, stable_ids_by_row, contributor_ids, contributor_weights = (
        _validated_reference_raster(
            contributor_raster,
            admission_input,
            admission,
        )
    )
    if width != weights.width or height != weights.height:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Contributor dimensions do not match the Stable Mask."
        )
    stable_ids = list(admission["stableGaussianIds"])
    evidence_index = {stable_id: index for index, stable_id in enumerate(stable_ids)}
    positive_mass = [0.0] * len(stable_ids)
    negative_mass = [0.0] * len(stable_ids)
    visible_mass = [0.0] * len(stable_ids)
    boundary_mass = [0.0] * len(stable_ids)
    for y_px in range(height):
        for x_px in range(width):
            pixel_weight = weights.at(x_px, y_px)
            for row_id, contribution in zip(
                contributor_ids[y_px][x_px],
                contributor_weights[y_px][x_px],
                strict=True,
            ):
                if row_id < 0 or contribution == 0.0:
                    continue
                stable_id = stable_ids_by_row[row_id]
                output_index = evidence_index.get(stable_id)
                if output_index is None:
                    continue
                positive_mass[output_index] += pixel_weight.positive * contribution
                negative_mass[output_index] += pixel_weight.negative * contribution
                visible_mass[output_index] += pixel_weight.visible * contribution
                boundary_mass[output_index] += pixel_weight.boundary * contribution
    try:
        return create_gaussian_evidence_artifact(
            admission,
            {
                "positiveMass": positive_mass,
                "negativeMass": negative_mass,
                "visibleMass": visible_mass,
                "boundaryMass": boundary_mass,
            },
        )
    except GaussianEvidenceContractError as error:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence produced incomplete or non-finite P/N/V."
        ) from error


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _comparable_artifact_identity(artifact: dict[str, object]) -> dict[str, object]:
    return {
        key: artifact[key]
        for key in (
            "schemaVersion",
            "requestBinding",
            "targetSplatId",
            "viewId",
            "cameraBindingDigest",
            "rgbDigest",
            "stableMaskDigest",
            "evidencePolicyDigest",
            "renderWorkingSetToken",
            "evidenceWorkingSetToken",
            "stableGaussianIds",
        )
    }


def _validated_thresholds(value: object) -> dict[str, list[float]]:
    if value is None:
        return {}
    channels = {"positiveMass", "negativeMass", "visibleMass", "boundaryMass"}
    if not isinstance(value, dict) or any(key not in channels for key in value):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference comparison thresholds are invalid."
        )
    result: dict[str, list[float]] = {}
    for channel, entries in value.items():
        if not isinstance(entries, list) or any(
            not _is_number(entry) or float(entry) < 0.0 for entry in entries
        ):
            raise ReferenceGaussianEvidenceError(
                "AI Select reference comparison thresholds are invalid."
            )
        result[channel] = sorted({float(entry) for entry in entries})
    return result


def _compare_channel(
    stable_ids: list[int],
    left: list[float],
    right: list[float],
    thresholds: list[float],
    *,
    support_epsilon: float,
    threshold_near_absolute_tolerance: float,
) -> dict[str, object]:
    absolute_errors = [
        abs(float(left_value) - float(right_value))
        for left_value, right_value in zip(left, right, strict=True)
    ]
    relative_errors = [
        error / max(abs(float(left_value)), abs(float(right_value)), support_epsilon)
        for error, left_value, right_value in zip(
            absolute_errors,
            left,
            right,
            strict=True,
        )
    ]
    support_differences = [
        stable_id
        for stable_id, left_value, right_value in zip(
            stable_ids,
            left,
            right,
            strict=True,
        )
        if (float(left_value) > support_epsilon)
        != (float(right_value) > support_epsilon)
    ]
    threshold_crossings: set[int] = set()
    threshold_near_differences: set[int] = set()
    for stable_id, left_value, right_value in zip(
        stable_ids,
        left,
        right,
        strict=True,
    ):
        left_number = float(left_value)
        right_number = float(right_value)
        for threshold in thresholds:
            if (left_number >= threshold) == (right_number >= threshold):
                continue
            threshold_crossings.add(stable_id)
            if (
                abs(left_number - threshold) <= threshold_near_absolute_tolerance
                or abs(right_number - threshold) <= threshold_near_absolute_tolerance
            ):
                threshold_near_differences.add(stable_id)
    return {
        "maxAbsoluteError": max(absolute_errors, default=0.0),
        "p95AbsoluteError": _nearest_rank(absolute_errors, 0.95),
        "p99AbsoluteError": _nearest_rank(absolute_errors, 0.99),
        "maxRelativeError": max(relative_errors, default=0.0),
        "p95RelativeError": _nearest_rank(relative_errors, 0.95),
        "p99RelativeError": _nearest_rank(relative_errors, 0.99),
        "supportDifferenceCount": len(support_differences),
        "supportDifferenceStableGaussianIds": support_differences,
        "thresholdCrossingDifferenceCount": len(threshold_crossings),
        "thresholdCrossingDifferenceStableGaussianIds": sorted(threshold_crossings),
        "thresholdNearDifferenceCount": len(threshold_near_differences),
        "thresholdNearDifferenceStableGaussianIds": sorted(threshold_near_differences),
    }


def compare_reference_evidence_artifacts(
    left: object,
    right: object,
    *,
    thresholds: object = None,
    support_epsilon: float = 1e-12,
    threshold_near_absolute_tolerance: float = 1e-6,
) -> dict[str, object]:
    """Measure two reference backends without changing either artifact/policy."""

    if (
        not is_gaussian_evidence_artifact(left)
        or not is_gaussian_evidence_artifact(right)
        or not isinstance(left, dict)
        or not isinstance(right, dict)
        or left["evidenceBackendKind"]
        not in {
            "reference-contributor",
            "reference-autograd",
        }
        or right["evidenceBackendKind"]
        not in {
            "reference-contributor",
            "reference-autograd",
        }
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference comparison requires complete trusted artifacts."
        )
    if _comparable_artifact_identity(left) != _comparable_artifact_identity(right):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference artifacts do not bind the same per-view decision."
        )
    if (
        not _is_number(support_epsilon)
        or float(support_epsilon) <= 0.0
        or not _is_number(threshold_near_absolute_tolerance)
        or float(threshold_near_absolute_tolerance) < 0.0
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference comparison tolerances are invalid."
        )
    validated_thresholds = _validated_thresholds(thresholds)
    stable_ids = list(left["stableGaussianIds"])
    channels: dict[str, object] = {}
    availability_differences: list[str] = []
    for channel in (
        "positiveMass",
        "negativeMass",
        "visibleMass",
        "boundaryMass",
    ):
        left_available = channel in left
        right_available = channel in right
        if left_available != right_available:
            availability_differences.append(channel)
            continue
        if not left_available:
            continue
        channels[channel] = _compare_channel(
            stable_ids,
            list(left[channel]),
            list(right[channel]),
            validated_thresholds.get(channel, []),
            support_epsilon=float(support_epsilon),
            threshold_near_absolute_tolerance=float(threshold_near_absolute_tolerance),
        )
    return {
        "left": {
            "artifactDigest": left["artifactDigest"],
            "evidenceBackendKind": left["evidenceBackendKind"],
            "evidenceBackendId": left["evidenceBackendId"],
            "rasterImplementationId": left["rasterImplementationId"],
            "runtimeBuildId": left["runtimeBuildId"],
        },
        "right": {
            "artifactDigest": right["artifactDigest"],
            "evidenceBackendKind": right["evidenceBackendKind"],
            "evidenceBackendId": right["evidenceBackendId"],
            "rasterImplementationId": right["rasterImplementationId"],
            "runtimeBuildId": right["runtimeBuildId"],
        },
        "stableGaussianIds": stable_ids,
        "thresholds": validated_thresholds,
        "supportEpsilon": float(support_epsilon),
        "thresholdNearAbsoluteTolerance": float(threshold_near_absolute_tolerance),
        "channelAvailabilityDifferences": availability_differences,
        "channels": channels,
    }


def compare_available_reference_artifacts(
    artifacts: object,
    *,
    thresholds: object = None,
    support_epsilon: float = 1e-12,
    threshold_near_absolute_tolerance: float = 1e-6,
) -> dict[str, object]:
    """Require a reference backend and compare every available backend pair."""

    if not isinstance(artifacts, list) or not artifacts:
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence requires at least one trusted reference backend."
        )
    if any(
        not is_gaussian_evidence_artifact(artifact)
        or not isinstance(artifact, dict)
        or artifact["evidenceBackendKind"]
        not in {
            "reference-contributor",
            "reference-autograd",
        }
        for artifact in artifacts
    ):
        raise ReferenceGaussianEvidenceError(
            "AI Select reference Evidence requires complete trusted artifacts."
        )
    ordered = sorted(
        artifacts,
        key=lambda artifact: (
            artifact["evidenceBackendKind"],
            artifact["evidenceBackendId"],
            artifact["artifactDigest"],
        ),
    )
    comparisons: list[dict[str, object]] = []
    for left_index, left_artifact in enumerate(ordered):
        for right_artifact in ordered[left_index + 1 :]:
            comparisons.append(
                compare_reference_evidence_artifacts(
                    left_artifact,
                    right_artifact,
                    thresholds=thresholds,
                    support_epsilon=support_epsilon,
                    threshold_near_absolute_tolerance=(
                        threshold_near_absolute_tolerance
                    ),
                )
            )
    return {
        "availableBackendKinds": sorted(
            {artifact["evidenceBackendKind"] for artifact in ordered}
        ),
        "artifactDigests": [artifact["artifactDigest"] for artifact in ordered],
        "comparisons": comparisons,
    }


__all__ = [
    "PixelEvidenceWeight",
    "PixelEvidenceWeights",
    "REFERENCE_EVIDENCE_POLICY_ID",
    "REFERENCE_EVIDENCE_POLICY_SCHEMA_VERSION",
    "ReferenceGaussianEvidenceError",
    "compare_available_reference_artifacts",
    "compare_reference_evidence_artifacts",
    "compute_reference_contributor_evidence",
    "default_reference_evidence_policy",
    "derive_pixel_evidence_weights",
]
