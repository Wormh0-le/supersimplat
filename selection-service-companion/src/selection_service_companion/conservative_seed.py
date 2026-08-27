"""Deterministic S0 Conservative Seed experimental shadow evaluation.

The evaluator consumes one exact production Direct Evidence artifact and
world-space target geometry. It emits a separate immutable-by-digest shadow
record only; it does not mutate Evidence, readiness, Candidate, or Native
Selection state.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from .digests import route_b_artifact_digest
from .gaussian_evidence_contract import is_gaussian_evidence_artifact


CONSERVATIVE_SEED_POLICY_SCHEMA_VERSION: Final = 1
CONSERVATIVE_SEED_TARGET_GEOMETRY_SCHEMA_VERSION: Final = 1
CONSERVATIVE_SEED_RECORD_SCHEMA_VERSION: Final = 1
CONSERVATIVE_SEED_RECORD_KIND: Final = (
    "conservative-seed-s0/experimental-shadow"
)
_MAX_STABLE_GAUSSIAN_ID: Final = (1 << 32) - 1
_POLICY_KEYS: Final = {
    "schemaVersion",
    "policyId",
    "minimumVisibleMass",
    "minimumPositiveRatio",
    "maximumNegativeMass",
    "maximumConflictRatio",
    "connectivityScaleMultiplier",
    "minimumSatelliteGaussianCount",
    "minimumSatellitePositiveMass",
    "grossOutlierScaleMultiplier",
}
_OUTCOMES: Final = {
    "core-candidate",
    "satellite",
    "filtered-low-visibility",
    "filtered-low-positive-ratio",
    "filtered-conflict",
    "filtered-disconnected",
    "gross-outlier",
}


class ConservativeSeedError(ValueError):
    """An S0 shadow input or record failed closed."""


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _stable_id(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_STABLE_GAUSSIAN_ID
    )


def _sorted_unique_stable_ids(value: object, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_stable_id(stable_id) for stable_id in value)
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def create_conservative_seed_policy(value: object) -> dict[str, object]:
    """Validate one explicit versioned experimental S0 policy."""

    if not isinstance(value, Mapping) or set(value) != _POLICY_KEYS:
        raise ConservativeSeedError(
            "Conservative Seed policy is incomplete or has unknown fields."
        )
    policy_id = value.get("policyId")
    if (
        value.get("schemaVersion") != CONSERVATIVE_SEED_POLICY_SCHEMA_VERSION
        or not isinstance(policy_id, str)
        or not policy_id.startswith("conservative-seed-s0/experimental-shadow-v")
        or not policy_id.removeprefix(
            "conservative-seed-s0/experimental-shadow-v"
        ).isdigit()
    ):
        raise ConservativeSeedError(
            "Conservative Seed policy identity is not an experimental S0 version."
        )
    float_fields = (
        "minimumVisibleMass",
        "minimumPositiveRatio",
        "maximumNegativeMass",
        "maximumConflictRatio",
        "connectivityScaleMultiplier",
        "minimumSatellitePositiveMass",
        "grossOutlierScaleMultiplier",
    )
    if any(not _finite_number(value.get(name)) for name in float_fields):
        raise ConservativeSeedError(
            "Conservative Seed numeric policy values must be finite."
        )
    minimum_satellite_count = value.get("minimumSatelliteGaussianCount")
    if (
        not isinstance(minimum_satellite_count, int)
        or isinstance(minimum_satellite_count, bool)
        or minimum_satellite_count <= 0
        or float(value["minimumVisibleMass"]) <= 0.0
        or not 0.0 <= float(value["minimumPositiveRatio"]) <= 1.0
        or float(value["maximumNegativeMass"]) < 0.0
        or not 0.0 <= float(value["maximumConflictRatio"]) <= 1.0
        or float(value["connectivityScaleMultiplier"]) <= 0.0
        or float(value["minimumSatellitePositiveMass"]) < 0.0
        or float(value["grossOutlierScaleMultiplier"])
        <= float(value["connectivityScaleMultiplier"])
    ):
        raise ConservativeSeedError(
            "Conservative Seed policy thresholds are outside their valid ranges."
        )
    payload: dict[str, object] = {
        "schemaVersion": CONSERVATIVE_SEED_POLICY_SCHEMA_VERSION,
        "policyId": policy_id,
        **{name: float(value[name]) for name in float_fields},
        "minimumSatelliteGaussianCount": minimum_satellite_count,
    }
    return {**payload, "policyDigest": route_b_artifact_digest(payload)}


def validate_conservative_seed_policy(value: object) -> dict[str, object]:
    """Return an owned copy of one digest-valid experimental policy record."""

    if not isinstance(value, Mapping) or set(value) != _POLICY_KEYS | {
        "policyDigest"
    }:
        raise ConservativeSeedError(
            "Conservative Seed evaluation requires a complete policy record."
        )
    payload = {key: value[key] for key in _POLICY_KEYS}
    expected = create_conservative_seed_policy(payload)
    if value.get("policyDigest") != expected["policyDigest"]:
        raise ConservativeSeedError("Conservative Seed policy digest is invalid.")
    return expected


def _vector3(value: object, label: str, *, positive: bool = False) -> list[float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 3
        or any(not _finite_number(component) for component in value)
    ):
        raise ConservativeSeedError(f"Conservative Seed {label} must be finite xyz.")
    result = [float(component) for component in value]
    if positive and any(component <= 0.0 for component in result):
        raise ConservativeSeedError(
            f"Conservative Seed {label} must be strictly positive."
        )
    return result


def create_conservative_seed_target_geometry(
    *,
    target_splat_id: object,
    rows: object,
) -> dict[str, object]:
    """Canonicalize target Stable-ID centers and declared log scales by ID."""

    if not isinstance(target_splat_id, str) or not target_splat_id.strip():
        raise ConservativeSeedError("Conservative Seed target identity is invalid.")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ConservativeSeedError("Conservative Seed target geometry is empty.")
    canonical_rows: list[dict[str, object]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "stableGaussianId",
            "center",
            "logScales",
        }:
            raise ConservativeSeedError(
                "Conservative Seed target geometry row is incomplete."
            )
        stable_id = row.get("stableGaussianId")
        if not _stable_id(stable_id) or stable_id in seen:
            raise ConservativeSeedError(
                "Conservative Seed target geometry requires unique uint32 Stable Gaussian IDs."
            )
        assert isinstance(stable_id, int)
        seen.add(stable_id)
        log_scales = _vector3(row.get("logScales"), "log scales")
        try:
            declared_scales = [math.exp(value) for value in log_scales]
        except OverflowError as error:
            raise ConservativeSeedError(
                "Conservative Seed declared scales are outside the finite range."
            ) from error
        if any(not math.isfinite(value) or value <= 0.0 for value in declared_scales):
            raise ConservativeSeedError(
                "Conservative Seed declared scales are outside the finite range."
            )
        canonical_rows.append({
            "stableGaussianId": stable_id,
            "center": _vector3(row.get("center"), "center"),
            "logScales": log_scales,
        })
    canonical_rows.sort(key=lambda row: int(row["stableGaussianId"]))
    stable_ids = [int(row["stableGaussianId"]) for row in canonical_rows]
    payload: dict[str, object] = {
        "schemaVersion": CONSERVATIVE_SEED_TARGET_GEOMETRY_SCHEMA_VERSION,
        "targetSplatId": target_splat_id,
        "stableGaussianIds": stable_ids,
        "rows": canonical_rows,
    }
    return {**payload, "geometryDigest": route_b_artifact_digest(payload)}


def _validated_geometry(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "schemaVersion",
        "targetSplatId",
        "stableGaussianIds",
        "rows",
        "geometryDigest",
    }:
        raise ConservativeSeedError(
            "Conservative Seed target geometry record is invalid."
        )
    expected = create_conservative_seed_target_geometry(
        target_splat_id=value.get("targetSplatId"),
        rows=value.get("rows"),
    )
    if value.get("schemaVersion") != CONSERVATIVE_SEED_TARGET_GEOMETRY_SCHEMA_VERSION:
        raise ConservativeSeedError(
            "Conservative Seed target geometry schema is unsupported."
        )
    if (
        value.get("stableGaussianIds") != expected["stableGaussianIds"]
        or value.get("geometryDigest") != expected["geometryDigest"]
    ):
        raise ConservativeSeedError(
            "Conservative Seed target geometry identity is invalid."
        )
    return expected


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _components(
    candidates: list[dict[str, object]],
    multiplier: float,
) -> tuple[list[list[dict[str, object]]], int]:
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    comparisons = 0
    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            comparisons += 1
            threshold = multiplier * max(float(left["scale"]), float(right["scale"]))
            if _distance(left["center"], right["center"]) <= threshold:
                union(left_index, right_index)
    grouped: dict[int, list[dict[str, object]]] = {}
    for index, candidate in enumerate(candidates):
        grouped.setdefault(find(index), []).append(candidate)
    components = [
        sorted(component, key=lambda row: int(row["stableGaussianId"]))
        for component in grouped.values()
    ]
    components.sort(key=lambda component: int(component[0]["stableGaussianId"]))
    return components, comparisons


def _component_summary(
    component: list[dict[str, object]], classification: str
) -> dict[str, object]:
    stable_ids = [int(row["stableGaussianId"]) for row in component]
    identity = {"stableGaussianIds": stable_ids}
    return {
        "componentId": route_b_artifact_digest(identity),
        "stableGaussianIds": stable_ids,
        "gaussianCount": len(stable_ids),
        "totalPositiveMass": sum(float(row["positiveMass"]) for row in component),
        "totalNegativeMass": sum(float(row["negativeMass"]) for row in component),
        "totalVisibleMass": sum(float(row["visibleMass"]) for row in component),
        "maximumScale": max(float(row["scale"]) for row in component),
        "classification": classification,
    }


def _primary_component(
    components: list[list[dict[str, object]]],
) -> list[dict[str, object]] | None:
    if not components:
        return None
    return min(
        components,
        key=lambda component: (
            -sum(float(row["positiveMass"]) for row in component),
            -sum(float(row["visibleMass"]) for row in component),
            tuple(int(row["stableGaussianId"]) for row in component),
        ),
    )


def _normalized_component_distance(
    left: list[dict[str, object]],
    right: list[dict[str, object]],
) -> float:
    return min(
        _distance(left_row["center"], right_row["center"])
        / max(float(left_row["scale"]), float(right_row["scale"]))
        for left_row in left
        for right_row in right
    )


def evaluate_conservative_seed_shadow(
    *,
    evidence_artifact: object,
    target_geometry: object,
    policy: object,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> dict[str, object]:
    """Evaluate one exact Anchor Direct Evidence artifact without side effects.

    Measured timing is a sibling telemetry sidecar, deliberately outside the
    canonical record and its digest so equal inputs remain byte-equivalent.
    """

    started = clock_ns()
    if (
        not is_gaussian_evidence_artifact(evidence_artifact)
        or not isinstance(evidence_artifact, Mapping)
        or evidence_artifact.get("evidenceBackendKind") != "production-direct"
    ):
        raise ConservativeSeedError(
            "Conservative Seed requires one exact production Direct Evidence artifact."
        )
    geometry = _validated_geometry(target_geometry)
    validated_policy = validate_conservative_seed_policy(policy)
    if evidence_artifact.get("targetSplatId") != geometry["targetSplatId"]:
        raise ConservativeSeedError(
            "Conservative Seed Evidence and target geometry identities do not match."
        )
    evidence_ids = evidence_artifact.get("stableGaussianIds")
    target_ids = geometry["stableGaussianIds"]
    assert isinstance(evidence_ids, list)
    assert isinstance(target_ids, list)
    if not set(evidence_ids).issubset(target_ids):
        raise ConservativeSeedError(
            "Conservative Seed Evidence contains a Stable Gaussian ID outside the target universe."
        )
    geometry_by_id = {
        int(row["stableGaussianId"]): row
        for row in geometry["rows"]
        if isinstance(row, Mapping)
    }
    positive = evidence_artifact["positiveMass"]
    negative = evidence_artifact["negativeMass"]
    visible = evidence_artifact["visibleMass"]
    assert isinstance(positive, list)
    assert isinstance(negative, list)
    assert isinstance(visible, list)

    per_gaussian: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for index, stable_id in enumerate(evidence_ids):
        geometry_row = geometry_by_id[int(stable_id)]
        positive_mass = float(positive[index])
        negative_mass = float(negative[index])
        visible_mass = float(visible[index])
        positive_ratio = positive_mass / visible_mass if visible_mass > 0.0 else 0.0
        conflict_ratio = negative_mass / visible_mass if visible_mass > 0.0 else 0.0
        if visible_mass < float(validated_policy["minimumVisibleMass"]):
            outcome = "filtered-low-visibility"
            reasons = ["insufficient-visible-mass", "semantic-disposition-unknown"]
        elif (
            negative_mass > float(validated_policy["maximumNegativeMass"])
            or conflict_ratio > float(validated_policy["maximumConflictRatio"])
        ):
            outcome = "filtered-conflict"
            reasons = ["negative-or-conflict-mass-above-bound"]
        elif positive_ratio < float(validated_policy["minimumPositiveRatio"]):
            outcome = "filtered-low-positive-ratio"
            reasons = ["positive-support-ratio-below-minimum"]
        else:
            outcome = "filtered-disconnected"
            reasons = ["support-thresholds-passed", "component-pending"]
            log_scales = geometry_row["logScales"]
            assert isinstance(log_scales, list)
            candidate = {
                "stableGaussianId": int(stable_id),
                "center": geometry_row["center"],
                "scale": math.exp(max(float(value) for value in log_scales)),
                "positiveMass": positive_mass,
                "negativeMass": negative_mass,
                "visibleMass": visible_mass,
            }
            candidates.append(candidate)
        per_gaussian.append({
            "stableGaussianId": int(stable_id),
            "positiveMass": positive_mass,
            "negativeMass": negative_mass,
            "visibleMass": visible_mass,
            "positiveRatio": positive_ratio,
            "conflictRatio": conflict_ratio,
            "outcome": outcome,
            "reasons": reasons,
            "componentId": None,
        })

    components, comparisons = _components(
        candidates,
        float(validated_policy["connectivityScaleMultiplier"]),
    )
    primary = _primary_component(components)
    summaries: list[dict[str, object]] = []
    by_id = {int(row["stableGaussianId"]): row for row in per_gaussian}
    for component in components:
        gross_outlier = (
            primary is not None
            and component is not primary
            and _normalized_component_distance(component, primary)
            > float(validated_policy["grossOutlierScaleMultiplier"])
        )
        material_satellite = (
            not gross_outlier
            and len(component)
            >= int(validated_policy["minimumSatelliteGaussianCount"])
            and sum(float(row["positiveMass"]) for row in component)
            >= float(validated_policy["minimumSatellitePositiveMass"])
        )
        classification = (
            "core"
            if component is primary
            else "gross-outlier"
            if gross_outlier
            else "satellite"
            if material_satellite
            else "filtered-disconnected"
        )
        summary = _component_summary(component, classification)
        summaries.append(summary)
        for candidate in component:
            row = by_id[int(candidate["stableGaussianId"])]
            row["componentId"] = summary["componentId"]
            if component is primary:
                row["outcome"] = "core-candidate"
                row["reasons"] = [
                    "support-thresholds-passed",
                    "primary-connected-component",
                ]
            elif gross_outlier:
                row["outcome"] = "gross-outlier"
                row["reasons"] = [
                    "support-thresholds-passed",
                    "distance-from-primary-exceeds-gross-outlier-bound",
                ]
            elif material_satellite:
                row["outcome"] = "satellite"
                row["reasons"] = [
                    "support-thresholds-passed",
                    "material-disconnected-component",
                ]
            else:
                row["reasons"] = [
                    "support-thresholds-passed",
                    "disconnected-component-below-admission",
                ]

    core_ids = sorted(
        int(row["stableGaussianId"])
        for row in per_gaussian
        if row["outcome"] == "core-candidate"
    )
    satellite_ids = sorted(
        int(row["stableGaussianId"])
        for row in per_gaussian
        if row["outcome"] == "satellite"
    )
    admitted_ids = sorted(core_ids + satellite_ids)
    filtered_ids = sorted(set(evidence_ids) - set(admitted_ids))
    request_binding = evidence_artifact["requestBinding"]
    payload: dict[str, object] = {
        "schemaVersion": CONSERVATIVE_SEED_RECORD_SCHEMA_VERSION,
        "recordKind": CONSERVATIVE_SEED_RECORD_KIND,
        "status": "experimental-shadow",
        "requestBinding": deepcopy(request_binding),
        "targetSplatId": evidence_artifact["targetSplatId"],
        "anchorViewIdentity": {
            "viewId": evidence_artifact["viewId"],
            "cameraBindingDigest": evidence_artifact["cameraBindingDigest"],
            "rgbDigest": evidence_artifact["rgbDigest"],
            "stableMaskDigest": evidence_artifact["stableMaskDigest"],
        },
        "evidenceIdentity": {
            key: evidence_artifact[key]
            for key in (
                "artifactDigest",
                "evidencePolicyDigest",
                "renderWorkingSetToken",
                "evidenceWorkingSetToken",
                "rasterImplementationId",
                "evidenceBackendKind",
                "evidenceBackendId",
                "runtimeBuildId",
            )
        },
        "targetStableGaussianIds": list(target_ids),
        "targetGeometryDigest": geometry["geometryDigest"],
        "seedPolicy": deepcopy(validated_policy),
        "seedPolicyDigest": validated_policy["policyDigest"],
        "admittedStableGaussianIds": admitted_ids,
        "coreCandidateStableGaussianIds": core_ids,
        "satelliteStableGaussianIds": satellite_ids,
        "filteredStableGaussianIds": filtered_ids,
        "perGaussianSupport": per_gaussian,
        "componentSummaries": summaries,
    }
    record = {**payload, "recordDigest": route_b_artifact_digest(payload)}
    finished = clock_ns()
    return {
        "record": record,
        "timingTelemetry": {
            "evaluationNanoseconds": max(0, int(finished) - int(started)),
            "evaluatedGaussianCount": len(evidence_ids),
            "connectivityComparisonCount": comparisons,
        },
    }


def is_conservative_seed_shadow_record(value: object) -> bool:
    """Validate the immutable digest and sorted/disjoint Stable-ID outputs."""

    required = {
        "schemaVersion",
        "recordKind",
        "status",
        "requestBinding",
        "targetSplatId",
        "anchorViewIdentity",
        "evidenceIdentity",
        "targetStableGaussianIds",
        "targetGeometryDigest",
        "seedPolicy",
        "seedPolicyDigest",
        "admittedStableGaussianIds",
        "coreCandidateStableGaussianIds",
        "satelliteStableGaussianIds",
        "filteredStableGaussianIds",
        "perGaussianSupport",
        "componentSummaries",
        "recordDigest",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        return False
    try:
        if (
            value["schemaVersion"] != CONSERVATIVE_SEED_RECORD_SCHEMA_VERSION
            or value["recordKind"] != CONSERVATIVE_SEED_RECORD_KIND
            or value["status"] != "experimental-shadow"
            or not _digest(value["recordDigest"])
            or not _digest(value["targetGeometryDigest"])
            or not _digest(value["seedPolicyDigest"])
            or not isinstance(value["targetSplatId"], str)
            or not value["targetSplatId"].strip()
        ):
            return False
        policy = validate_conservative_seed_policy(value["seedPolicy"])
        if policy["policyDigest"] != value["seedPolicyDigest"]:
            return False
        target_ids = value["targetStableGaussianIds"]
        admitted = value["admittedStableGaussianIds"]
        core = value["coreCandidateStableGaussianIds"]
        satellite = value["satelliteStableGaussianIds"]
        filtered = value["filteredStableGaussianIds"]
        if not all(
            _sorted_unique_stable_ids(ids)
            for ids in (target_ids, admitted, core, satellite, filtered)
        ):
            return False
        if (
            set(core) & set(satellite)
            or set(admitted) != set(core) | set(satellite)
            or set(admitted) & set(filtered)
            or not (set(admitted) | set(filtered)).issubset(set(target_ids))
        ):
            return False
        rows = value["perGaussianSupport"]
        if (
            not isinstance(rows, list)
            or [row.get("stableGaussianId") for row in rows if isinstance(row, Mapping)]
            != sorted(set(admitted) | set(filtered))
            or any(
                not isinstance(row, Mapping)
                or row.get("outcome") not in _OUTCOMES
                or not isinstance(row.get("reasons"), list)
                for row in rows
            )
        ):
            return False
        payload = {key: deepcopy(item) for key, item in value.items() if key != "recordDigest"}
        return value["recordDigest"] == route_b_artifact_digest(payload)
    except (ConservativeSeedError, KeyError, TypeError, ValueError):
        return False


def canonical_conservative_seed_shadow_bytes(value: object) -> bytes:
    """Serialize one validated shadow record for byte-equivalent replay."""

    if not is_conservative_seed_shadow_record(value) or not isinstance(
        value, Mapping
    ):
        raise ConservativeSeedError("Conservative Seed shadow record is invalid.")
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


__all__ = [
    "CONSERVATIVE_SEED_RECORD_KIND",
    "ConservativeSeedError",
    "canonical_conservative_seed_shadow_bytes",
    "create_conservative_seed_policy",
    "create_conservative_seed_target_geometry",
    "evaluate_conservative_seed_shadow",
    "is_conservative_seed_shadow_record",
    "validate_conservative_seed_policy",
]
