"""Visible-Evidence Coverage, View Diversity, and Lift Readiness.

The evaluator consumes an exact current reference aggregation result. It does
not produce P/N/V, classify ownership, publish a Candidate, or mutate editor
state. Production same-decision Evidence remains Ticket 20 work.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Final

from .camera_binding import camera_binding_digest, parse_camera_binding
from .digests import route_b_artifact_digest
from .gaussian_evidence_contract import is_evidence_working_set
from .reference_gaussian_evidence_aggregation import (
    is_reference_gaussian_evidence_aggregation_result,
)


LIFT_READINESS_RESULT_SCHEMA_VERSION: Final = 1
LIFT_READINESS_POLICY_SCHEMA_VERSION: Final = 1
LIFT_READINESS_POLICY_ID: Final = "lift-readiness/reference-v1"
_GENERATION_STATES: Final = {"active", "stopped", "complete", "unavailable"}
_READINESS_STATES: Final = {"not-ready", "limited", "ready"}
_REASONS: Final = {
    "formal-evidence-pending",
    "low-visible-support",
    "weak-gaussian-support",
    "low-view-diversity",
}
_RECOMMENDATIONS: Final = {
    "none",
    "wait-for-current-views",
    "generate-more",
    "add-view",
}


class LiftReadinessError(ValueError):
    """A Lift Readiness input failed closed."""


def _policy_payload() -> dict[str, object]:
    return {
        "schemaVersion": LIFT_READINESS_POLICY_SCHEMA_VERSION,
        "policyId": LIFT_READINESS_POLICY_ID,
        "minimumPerGaussianVisibleMass": 0.1,
        "minimumLimitedCoverageRatio": 0.25,
        "minimumReadyCoverageRatio": 0.75,
        "minimumUsefulViewCoverageRatio": 0.1,
        "minimumReadyViewDiversityDegrees": 20.0,
        "coverageAggregationMode": "max-per-view-visible-mass/v1",
        "viewDirectionMode": "opencv-camera-forward/v1",
    }


def default_lift_readiness_policy() -> dict[str, object]:
    """Return the versioned Ticket 13 reference calibration policy."""

    payload = _policy_payload()
    return {**payload, "readinessPolicyDigest": route_b_artifact_digest(payload)}


def _validated_policy(value: object) -> dict[str, object]:
    expected = default_lift_readiness_policy()
    if value != expected:
        raise LiftReadinessError(
            "AI Select Lift Readiness Policy is incomplete or unsupported."
        )
    return deepcopy(expected)


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _is_request_binding(value: object, target_splat_id: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "targetContextId",
        "contextRevision",
        "dependencyToken",
    }:
        return False
    dependency = value["dependencyToken"]
    return (
        isinstance(value["targetContextId"], str)
        and bool(value["targetContextId"].strip())
        and isinstance(value["contextRevision"], int)
        and not isinstance(value["contextRevision"], bool)
        and 0 <= value["contextRevision"] <= 2**53 - 1
        and isinstance(dependency, dict)
        and set(dependency)
        == {
            "splatId",
            "renderStateToken",
            "geometryToken",
            "gaussianIdentityToken",
            "worldTransformToken",
        }
        and dependency["splatId"] == target_splat_id
        and all(
            isinstance(dependency[key], str) and bool(dependency[key].strip())
            for key in dependency
        )
    )


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_coverage(value: object, source: str) -> bool:
    if not isinstance(value, dict):
        return False
    if source == "formal-evidence":
        return (
            set(value)
            == {
                "status",
                "coverageRatio",
                "observedCoreGaussianCount",
                "totalCoreGaussianCount",
            }
            and value["status"] == "available"
            and _is_finite_number(value["coverageRatio"])
            and 0.0 <= float(value["coverageRatio"]) <= 1.0
            and isinstance(value["observedCoreGaussianCount"], int)
            and not isinstance(value["observedCoreGaussianCount"], bool)
            and isinstance(value["totalCoreGaussianCount"], int)
            and not isinstance(value["totalCoreGaussianCount"], bool)
            and 0
            <= value["observedCoreGaussianCount"]
            <= value["totalCoreGaussianCount"]
        )
    return (
        set(value) == {"status", "totalCoreGaussianCount"}
        and value["status"] == "pending-formal-evidence"
        and isinstance(value["totalCoreGaussianCount"], int)
        and not isinstance(value["totalCoreGaussianCount"], bool)
        and value["totalCoreGaussianCount"] >= 0
    )


def _is_diversity(value: object, source: str) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "status",
            "usefulViewCount",
            "maximumAngularSeparationDegrees",
        }
        and value["status"]
        in (
            {"available", "insufficient-support"}
            if source == "formal-evidence"
            else {"pending-formal-evidence"}
        )
        and isinstance(value["usefulViewCount"], int)
        and not isinstance(value["usefulViewCount"], bool)
        and value["usefulViewCount"] >= 0
        and _is_finite_number(value["maximumAngularSeparationDegrees"])
        and 0.0 <= float(value["maximumAngularSeparationDegrees"]) <= 180.0
    )


def _has_exact_reasons(value: object, expected: list[str]) -> bool:
    return isinstance(value, list) and value == expected


def _has_consistent_result_semantics(value: dict[str, object]) -> bool:
    source = str(value["source"])
    readiness = str(value["readiness"])
    generation_state = str(value["generationState"])
    coverage = value["observationCoverage"]
    diversity = value["viewDiversity"]
    assert isinstance(coverage, dict)
    assert isinstance(diversity, dict)
    if value["recommendation"] != _recommendation(readiness, generation_state):
        return False
    if source == "formal-evidence":
        expected_readiness, expected_reasons = _readiness(
            coverage,
            diversity,
            default_lift_readiness_policy(),
        )
        useful_count = int(diversity["usefulViewCount"])
        if diversity["status"] != (
            "available" if useful_count > 0 else "insufficient-support"
        ):
            return False
        if useful_count < 2 and float(
            diversity["maximumAngularSeparationDegrees"]
        ) != 0.0:
            return False
        return readiness == expected_readiness and _has_exact_reasons(
            value["reasons"], expected_reasons
        )
    if (
        diversity["usefulViewCount"] != 0
        or float(diversity["maximumAngularSeparationDegrees"]) != 0.0
    ):
        return False
    if source == "low-cost-diagnostic" and readiness == "limited":
        return _has_exact_reasons(value["reasons"], ["formal-evidence-pending"])
    return readiness == "not-ready" and _has_exact_reasons(
        value["reasons"],
        [
            "formal-evidence-pending",
            "low-visible-support",
            "weak-gaussian-support",
        ],
    )


def is_lift_readiness_result(value: object) -> bool:
    """Validate one immutable Companion result at a browser/protocol boundary."""

    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "kind",
        "requestBinding",
        "targetSplatId",
        "evidenceWorkingSetToken",
        "evidenceArtifactSetDigest",
        "aggregationResultDigest",
        "readinessPolicy",
        "readinessPolicyDigest",
        "source",
        "lowCostSupportDiagnosticDigest",
        "observationCoverage",
        "viewDiversity",
        "readiness",
        "reasons",
        "generationState",
        "recommendation",
        "resultDigest",
    }:
        return False
    target_splat_id = value["targetSplatId"]
    source = value["source"]
    reasons = value["reasons"]
    if (
        value["schemaVersion"] != LIFT_READINESS_RESULT_SCHEMA_VERSION
        or value["kind"] != "lift-readiness/reference-v1"
        or not isinstance(target_splat_id, str)
        or not target_splat_id.strip()
        or not _is_request_binding(value["requestBinding"], target_splat_id)
        or not _is_digest(value["evidenceWorkingSetToken"])
        or value["readinessPolicy"] != default_lift_readiness_policy()
        or value["readinessPolicyDigest"]
        != default_lift_readiness_policy()["readinessPolicyDigest"]
        or source not in {"formal-evidence", "low-cost-diagnostic", "none"}
        or value["readiness"] not in _READINESS_STATES
        or not isinstance(reasons, list)
        or len(reasons) != len(set(reasons))
        or any(reason not in _REASONS for reason in reasons)
        or value["generationState"] not in _GENERATION_STATES
        or value["recommendation"] not in _RECOMMENDATIONS
        or not _is_coverage(value["observationCoverage"], source)
        or not _is_diversity(value["viewDiversity"], source)
        or not _is_digest(value["resultDigest"])
    ):
        return False
    if source == "formal-evidence":
        if not _is_digest(value["evidenceArtifactSetDigest"]) or not _is_digest(
            value["aggregationResultDigest"]
        ):
            return False
    elif (
        value["evidenceArtifactSetDigest"] is not None
        or value["aggregationResultDigest"] is not None
    ):
        return False
    if source == "low-cost-diagnostic":
        if not _is_digest(value["lowCostSupportDiagnosticDigest"]):
            return False
    elif source == "none":
        if value["lowCostSupportDiagnosticDigest"] is not None:
            return False
    elif value["lowCostSupportDiagnosticDigest"] is not None:
        if not _is_digest(value["lowCostSupportDiagnosticDigest"]):
            return False
    if not _has_consistent_result_semantics(value):
        return False
    payload = {key: deepcopy(item) for key, item in value.items() if key != "resultDigest"}
    return value["resultDigest"] == route_b_artifact_digest(payload)


def _validated_low_cost_diagnostic(
    value: object,
    request_binding: dict[str, object],
    target_splat_id: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "requestBinding",
            "targetSplatId",
            "viewId",
            "cameraBindingDigest",
            "rgbDigest",
            "stableMaskDigest",
            "supportProbePolicyVersion",
            "computable",
            "observedGaussianCount",
        }
        or value["requestBinding"] != request_binding
        or value["targetSplatId"] != target_splat_id
        or not isinstance(value["viewId"], str)
        or not value["viewId"].strip()
        or not _is_digest(value["cameraBindingDigest"])
        or not _is_digest(value["rgbDigest"])
        or not _is_digest(value["stableMaskDigest"])
        or value["supportProbePolicyVersion"] != "anchor-support-probe/v1"
        or not isinstance(value["computable"], bool)
        or isinstance(value["observedGaussianCount"], bool)
        or not isinstance(value["observedGaussianCount"], int)
        or value["observedGaussianCount"] < 0
        or value["computable"] != (value["observedGaussianCount"] > 0)
    ):
        raise LiftReadinessError(
            "AI Select low-cost support diagnostic is invalid or stale."
        )
    return deepcopy(value)


def _camera_forward(camera_binding: dict[str, object]) -> tuple[float, float, float]:
    camera_to_world = camera_binding["cameraToWorld"]
    assert isinstance(camera_to_world, list)
    forward = (
        float(camera_to_world[2]),
        float(camera_to_world[6]),
        float(camera_to_world[10]),
    )
    magnitude = math.sqrt(sum(component * component for component in forward))
    if magnitude <= 0.0 or not math.isfinite(magnitude):
        raise LiftReadinessError(
            "AI Select Lift Readiness requires a finite camera direction."
        )
    return tuple(component / magnitude for component in forward)


def _observation_directions(
    value: object,
    source_artifacts: list[dict[str, object]],
) -> dict[str, tuple[float, float, float]]:
    if not isinstance(value, list):
        raise LiftReadinessError(
            "AI Select Lift Readiness observation Views are invalid."
        )
    expected_camera_digests: dict[str, str] = {}
    for artifact in source_artifacts:
        view_id = artifact.get("viewId")
        camera_digest = artifact.get("cameraBindingDigest")
        if not isinstance(view_id, str) or not isinstance(camera_digest, str):
            raise LiftReadinessError(
                "AI Select Lift Readiness source View identity is invalid."
            )
        expected_camera_digests[view_id] = camera_digest

    directions: dict[str, tuple[float, float, float]] = {}
    for record in value:
        if (
            not isinstance(record, dict)
            or set(record) != {"viewId", "cameraBinding"}
            or not isinstance(record["viewId"], str)
        ):
            raise LiftReadinessError(
                "AI Select Lift Readiness observation View is invalid."
            )
        view_id = record["viewId"]
        if view_id in directions or view_id not in expected_camera_digests:
            raise LiftReadinessError(
                "AI Select Lift Readiness observation View identity is incompatible."
            )
        try:
            camera, _, _, _ = parse_camera_binding(record["cameraBinding"])
        except ValueError as error:
            raise LiftReadinessError(
                "AI Select Lift Readiness CameraBinding is invalid."
            ) from error
        if camera_binding_digest(camera) != expected_camera_digests[view_id]:
            raise LiftReadinessError(
                "AI Select Lift Readiness CameraBinding digest is incompatible."
            )
        directions[view_id] = _camera_forward(camera)
    if set(directions) != set(expected_camera_digests):
        raise LiftReadinessError(
            "AI Select Lift Readiness requires every Included Evidence View camera."
        )
    return directions


def _maximum_separation_degrees(
    directions: list[tuple[float, float, float]],
) -> float:
    maximum = 0.0
    for left_index, left in enumerate(directions):
        for right in directions[left_index + 1 :]:
            dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))
            maximum = max(maximum, math.degrees(math.acos(dot)))
    return round(maximum, 6)


def _formal_metrics(
    aggregate: dict[str, object],
    directions: dict[str, tuple[float, float, float]],
    policy: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    working_set = aggregate["evidenceWorkingSet"]
    assert isinstance(working_set, dict)
    core_ids = working_set["coreTargetStableIds"]
    gaussian_records = aggregate["gaussians"]
    assert isinstance(core_ids, list)
    assert isinstance(gaussian_records, list)
    if not core_ids:
        return (
            {
                "status": "available",
                "coverageRatio": 0.0,
                "observedCoreGaussianCount": 0,
                "totalCoreGaussianCount": 0,
            },
            {
                "status": "insufficient-support",
                "usefulViewCount": 0,
                "maximumAngularSeparationDegrees": 0.0,
            },
        )

    records_by_id = {
        record.get("stableGaussianId"): record
        for record in gaussian_records
        if isinstance(record, dict)
    }
    if any(stable_id not in records_by_id for stable_id in core_ids):
        raise LiftReadinessError(
            "AI Select Lift Readiness aggregation omits Core Target Evidence."
        )
    minimum_visible = float(policy["minimumPerGaussianVisibleMass"])
    per_view_coverage = {view_id: 0.0 for view_id in directions}
    coverage_sum = 0.0
    observed = 0
    for stable_id in core_ids:
        record = records_by_id[stable_id]
        per_view = record.get("perView")
        if not isinstance(per_view, list):
            raise LiftReadinessError(
                "AI Select Lift Readiness Core Target Evidence is incomplete."
            )
        visible_by_view: dict[str, float] = {}
        for view_record in per_view:
            if not isinstance(view_record, dict):
                raise LiftReadinessError(
                    "AI Select Lift Readiness per-View Evidence is invalid."
                )
            view_id = view_record.get("viewId")
            visible_value = view_record.get("effectiveVisibleMass")
            if (
                view_id not in directions
                or isinstance(visible_value, bool)
                or not isinstance(visible_value, (int, float))
                or not math.isfinite(float(visible_value))
                or float(visible_value) < 0.0
            ):
                raise LiftReadinessError(
                    "AI Select Lift Readiness per-View Visible Mass is invalid."
                )
            visible_by_view[str(view_id)] = float(visible_value)
        if set(visible_by_view) != set(directions):
            raise LiftReadinessError(
                "AI Select Lift Readiness per-View Evidence identity is incomplete."
            )
        maximum_visible = max(visible_by_view.values(), default=0.0)
        coverage_sum += min(1.0, maximum_visible / minimum_visible)
        if maximum_visible >= minimum_visible:
            observed += 1
        for view_id, visible in visible_by_view.items():
            per_view_coverage[view_id] += min(1.0, visible / minimum_visible)

    total = len(core_ids)
    coverage_ratio = coverage_sum / total
    useful_view_ids = [
        view_id
        for view_id, coverage in per_view_coverage.items()
        if coverage / total
        >= float(policy["minimumUsefulViewCoverageRatio"])
    ]
    maximum_separation = _maximum_separation_degrees(
        [directions[view_id] for view_id in useful_view_ids]
    )
    return (
        {
            "status": "available",
            "coverageRatio": coverage_ratio,
            "observedCoreGaussianCount": observed,
            "totalCoreGaussianCount": total,
        },
        {
            "status": "available" if useful_view_ids else "insufficient-support",
            "usefulViewCount": len(useful_view_ids),
            "maximumAngularSeparationDegrees": maximum_separation,
        },
    )


def _readiness(
    coverage: dict[str, object],
    diversity: dict[str, object],
    policy: dict[str, object],
) -> tuple[str, list[str]]:
    ratio = float(coverage["coverageRatio"])
    reasons: list[str] = []
    if ratio < float(policy["minimumLimitedCoverageRatio"]):
        reasons.extend(["low-visible-support", "weak-gaussian-support"])
        return "not-ready", reasons
    if ratio < float(policy["minimumReadyCoverageRatio"]):
        reasons.append("weak-gaussian-support")
    if (
        diversity["status"] != "available"
        or float(diversity["maximumAngularSeparationDegrees"])
        < float(policy["minimumReadyViewDiversityDegrees"])
    ):
        reasons.append("low-view-diversity")
    return ("ready", reasons) if not reasons else ("limited", reasons)


def _recommendation(readiness: str, generation_state: str) -> str:
    if readiness == "ready":
        return "none"
    if generation_state == "active":
        return "wait-for-current-views"
    if generation_state in {"stopped", "complete"}:
        return "generate-more"
    return "add-view"


def evaluate_lift_readiness(
    readiness_input: object,
    policy: object,
) -> dict[str, object]:
    """Evaluate one immutable, target-scoped formal Lift Readiness result."""

    validated_policy = _validated_policy(policy)
    if (
        not isinstance(readiness_input, dict)
        or set(readiness_input)
        != {
            "requestBinding",
            "targetSplatId",
            "evidenceWorkingSet",
            "aggregationResult",
            "observationViews",
            "generationState",
            "lowCostSupportDiagnostic",
        }
        or not isinstance(readiness_input["requestBinding"], dict)
        or not isinstance(readiness_input["targetSplatId"], str)
        or not readiness_input["targetSplatId"].strip()
        or not _is_request_binding(
            readiness_input["requestBinding"],
            readiness_input["targetSplatId"],
        )
        or not is_evidence_working_set(readiness_input["evidenceWorkingSet"])
        or readiness_input["evidenceWorkingSet"]["targetSplatId"]
        != readiness_input["targetSplatId"]
        or readiness_input["generationState"] not in _GENERATION_STATES
        or (
            readiness_input["aggregationResult"] is not None
            and not is_reference_gaussian_evidence_aggregation_result(
                readiness_input["aggregationResult"]
            )
        )
    ):
        raise LiftReadinessError("AI Select Lift Readiness input is invalid.")
    aggregate = readiness_input["aggregationResult"]
    working_set = readiness_input["evidenceWorkingSet"]
    assert isinstance(working_set, dict)
    request_binding = readiness_input["requestBinding"]
    assert isinstance(request_binding, dict)
    target_splat_id = str(readiness_input["targetSplatId"])
    diagnostic = _validated_low_cost_diagnostic(
        readiness_input["lowCostSupportDiagnostic"],
        request_binding,
        target_splat_id,
    )
    generation_state = str(readiness_input["generationState"])
    if aggregate is None:
        if readiness_input["observationViews"] != []:
            raise LiftReadinessError(
                "AI Select Lift Readiness cannot bind observation cameras without formal Evidence."
            )
        total_core = len(working_set["coreTargetStableIds"])
        computable = diagnostic is not None and bool(diagnostic["computable"])
        readiness = "limited" if computable else "not-ready"
        reasons = (
            ["formal-evidence-pending"]
            if computable
            else [
                "formal-evidence-pending",
                "low-visible-support",
                "weak-gaussian-support",
            ]
        )
        payload: dict[str, object] = {
            "schemaVersion": LIFT_READINESS_RESULT_SCHEMA_VERSION,
            "kind": "lift-readiness/reference-v1",
            "requestBinding": deepcopy(request_binding),
            "targetSplatId": target_splat_id,
            "evidenceWorkingSetToken": working_set["evidenceWorkingSetToken"],
            "evidenceArtifactSetDigest": None,
            "aggregationResultDigest": None,
            "readinessPolicy": validated_policy,
            "readinessPolicyDigest": validated_policy["readinessPolicyDigest"],
            "source": "low-cost-diagnostic" if diagnostic is not None else "none",
            "lowCostSupportDiagnosticDigest": (
                route_b_artifact_digest(diagnostic) if diagnostic is not None else None
            ),
            "observationCoverage": {
                "status": "pending-formal-evidence",
                "totalCoreGaussianCount": total_core,
            },
            "viewDiversity": {
                "status": "pending-formal-evidence",
                "usefulViewCount": 0,
                "maximumAngularSeparationDegrees": 0.0,
            },
            "readiness": readiness,
            "reasons": reasons,
            "generationState": generation_state,
            "recommendation": _recommendation(readiness, generation_state),
        }
        return {**payload, "resultDigest": route_b_artifact_digest(payload)}

    assert isinstance(aggregate, dict)
    if (
        aggregate["requestBinding"] != request_binding
        or aggregate["targetSplatId"] != target_splat_id
        or aggregate["evidenceWorkingSet"] != working_set
    ):
        raise LiftReadinessError(
            "AI Select Lift Readiness aggregation identity is incompatible."
        )
    source_artifacts = aggregate["sourceEvidenceArtifacts"]
    assert isinstance(source_artifacts, list)
    directions = _observation_directions(
        readiness_input["observationViews"], source_artifacts
    )
    coverage, diversity = _formal_metrics(aggregate, directions, validated_policy)
    readiness, reasons = _readiness(coverage, diversity, validated_policy)
    payload: dict[str, object] = {
        "schemaVersion": LIFT_READINESS_RESULT_SCHEMA_VERSION,
        "kind": "lift-readiness/reference-v1",
        "requestBinding": deepcopy(readiness_input["requestBinding"]),
        "targetSplatId": readiness_input["targetSplatId"],
        "evidenceWorkingSetToken": working_set["evidenceWorkingSetToken"],
        "evidenceArtifactSetDigest": aggregate["evidenceArtifactSetDigest"],
        "aggregationResultDigest": aggregate["resultDigest"],
        "readinessPolicy": validated_policy,
        "readinessPolicyDigest": validated_policy["readinessPolicyDigest"],
        "source": "formal-evidence",
        "lowCostSupportDiagnosticDigest": (
            route_b_artifact_digest(diagnostic) if diagnostic is not None else None
        ),
        "observationCoverage": coverage,
        "viewDiversity": diversity,
        "readiness": readiness,
        "reasons": reasons,
        "generationState": generation_state,
        "recommendation": _recommendation(readiness, generation_state),
    }
    return {**payload, "resultDigest": route_b_artifact_digest(payload)}


__all__ = [
    "LIFT_READINESS_POLICY_ID",
    "LIFT_READINESS_POLICY_SCHEMA_VERSION",
    "LIFT_READINESS_RESULT_SCHEMA_VERSION",
    "LiftReadinessError",
    "default_lift_readiness_policy",
    "evaluate_lift_readiness",
    "is_lift_readiness_result",
]
