"""Versioned multi-view aggregation for Ticket 14C reference Evidence.

The module consumes independently published per-view P/N/V artifacts and
produces classification input for Ticket 14D. It does not publish a Candidate
or mutate editor-owned Native Selection.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Final

from .digests import canonical_json_digest
from .gaussian_evidence_contract import (
    is_current_gaussian_evidence_artifact,
    is_evidence_working_set,
    is_gaussian_evidence_admission_input,
    is_gaussian_evidence_artifact,
)


REFERENCE_AGGREGATION_RESULT_SCHEMA_VERSION: Final = 1
REFERENCE_AGGREGATION_POLICY_SCHEMA_VERSION: Final = 1
REFERENCE_AGGREGATION_POLICY_ID: Final = "multiview-evidence/reference-v1"
_PER_VIEW_CAP_MODE: Final = "per-view-visible-mass-cap/v1"
_RAW_SUM_MODE: Final = "raw-mass-sum/v1"


class ReferenceGaussianEvidenceAggregationError(ValueError):
    """A multi-view aggregation input failed closed."""


def _policy_payload(aggregation_mode: str) -> dict[str, object]:
    if aggregation_mode == _PER_VIEW_CAP_MODE:
        normalization_mode = "scale-pnv-by-visible-cap/v1"
        per_view_cap: float | None = 1.0
    elif aggregation_mode == _RAW_SUM_MODE:
        normalization_mode = "none/v1"
        per_view_cap = None
    else:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation mode is unsupported."
        )
    return {
        "schemaVersion": REFERENCE_AGGREGATION_POLICY_SCHEMA_VERSION,
        "policyId": REFERENCE_AGGREGATION_POLICY_ID,
        "aggregationMode": aggregation_mode,
        "normalizationMode": normalization_mode,
        "perViewVisibleMassCap": per_view_cap,
        "minimumAggregateVisibleMass": 0.1,
        "minimumAggregateEvidenceMass": 0.1,
        "minimumPerViewVisibleMass": 0.05,
        "minimumPerViewEvidenceMass": 0.05,
        "selectedPositiveRatioThreshold": 0.8,
        "rejectedNegativeRatioThreshold": 0.8,
        "materialPositiveRatioThreshold": 0.2,
        "materialNegativeRatioThreshold": 0.2,
    }


def reference_aggregation_policy(
    *,
    aggregation_mode: str = _PER_VIEW_CAP_MODE,
) -> dict[str, object]:
    """Create one declared raw-sum or per-view-capped reference policy."""

    payload = _policy_payload(aggregation_mode)
    return {
        **payload,
        "aggregationPolicyDigest": canonical_json_digest(payload),
    }


def default_reference_aggregation_policy() -> dict[str, object]:
    """Return the default capped Ticket 14C aggregation/classification policy."""

    return reference_aggregation_policy()


def _validated_policy(value: object) -> dict[str, object]:
    expected_keys = set(default_reference_aggregation_policy())
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation Policy is incomplete or unsupported."
        )
    aggregation_mode = value.get("aggregationMode")
    if not isinstance(aggregation_mode, str):
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation Policy identity or thresholds are invalid."
        )
    try:
        expected = reference_aggregation_policy(
            aggregation_mode=aggregation_mode
        )
    except ReferenceGaussianEvidenceAggregationError:
        expected = None
    if value != expected:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation Policy identity or thresholds are invalid."
        )
    return deepcopy(value)


def _same_request_binding(left: object, right: object) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _is_sorted_stable_ids(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(stable_id, int)
            and not isinstance(stable_id, bool)
            and 0 <= stable_id <= 0xFFFFFFFF
            for stable_id in value
        )
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _evidence_artifact_set(
    included: list[tuple[str, dict[str, object]]],
) -> list[dict[str, object]]:
    return [
        {
            "viewId": view_id,
            "artifactDigest": source["artifactDigest"],
        }
        for view_id, source in included
    ]


def _reference_backend_identities(
    included: list[tuple[str, dict[str, object]]],
) -> list[dict[str, object]]:
    identities = {
        (
            str(source["rasterImplementationId"]),
            str(source["evidenceBackendKind"]),
            str(source["evidenceBackendId"]),
            str(source["runtimeBuildId"]),
        )
        for _, source in included
    }
    return [
        {
            "rasterImplementationId": identity[0],
            "evidenceBackendKind": identity[1],
            "evidenceBackendId": identity[2],
            "runtimeBuildId": identity[3],
        }
        for identity in sorted(identities)
    ]


def _index_source_artifacts(
    included: list[tuple[str, dict[str, object]]],
) -> list[tuple[str, dict[str, object], dict[int, int]]]:
    result: list[tuple[str, dict[str, object], dict[int, int]]] = []
    for view_id, source in included:
        stable_ids = source["stableGaussianIds"]
        assert isinstance(stable_ids, list)
        result.append(
            (
                view_id,
                source,
                {
                    stable_id: source_index
                    for source_index, stable_id in enumerate(stable_ids)
                },
            )
        )
    return result


def _classification(
    effective_positive: float,
    effective_negative: float,
    effective_visible: float,
    positive_view_ids: list[str],
    negative_view_ids: list[str],
    mixed_view_ids: list[str],
    policy: dict[str, object],
) -> tuple[str, str | None]:
    if effective_visible < float(policy["minimumAggregateVisibleMass"]):
        return "uncertain", "unobserved-or-insufficient"
    evidence_mass = effective_positive + effective_negative
    if evidence_mass < float(policy["minimumAggregateEvidenceMass"]):
        return "uncertain", "insufficient-evidence"
    positive_ratio = effective_positive / evidence_mass
    negative_ratio = effective_negative / evidence_mass
    if positive_view_ids and negative_view_ids:
        return "uncertain", "conflicting-views"
    if (
        mixed_view_ids
        or (
            positive_ratio >= float(policy["materialPositiveRatioThreshold"])
            and negative_ratio >= float(policy["materialNegativeRatioThreshold"])
        )
    ):
        return "uncertain", "mixed-positive-negative"
    if positive_ratio >= float(policy["selectedPositiveRatioThreshold"]):
        return "selected", None
    if negative_ratio >= float(policy["rejectedNegativeRatioThreshold"]):
        return "rejected", None
    return "uncertain", "undecided-support"


def aggregate_reference_gaussian_evidence(
    aggregation_input: object,
    policy: object,
) -> dict[str, object]:
    """Atomically aggregate current Included per-view artifacts and classify IDs."""

    validated_policy = _validated_policy(policy)
    if (
        not isinstance(aggregation_input, dict)
        or set(aggregation_input)
        != {
            "requestBinding",
            "targetSplatId",
            "classificationUniverseStableGaussianIds",
            "evidenceWorkingSet",
            "views",
        }
        or not isinstance(aggregation_input["requestBinding"], dict)
        or not isinstance(aggregation_input["targetSplatId"], str)
        or not aggregation_input["targetSplatId"].strip()
        or not _is_sorted_stable_ids(
            aggregation_input["classificationUniverseStableGaussianIds"]
        )
        or not is_evidence_working_set(aggregation_input["evidenceWorkingSet"])
        or not isinstance(aggregation_input["views"], list)
    ):
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation input is invalid."
        )

    target_splat_id = aggregation_input["targetSplatId"]
    request_binding = aggregation_input["requestBinding"]
    evidence_working_set = aggregation_input["evidenceWorkingSet"]
    assert isinstance(evidence_working_set, dict)
    if evidence_working_set["targetSplatId"] != target_splat_id:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation Evidence Working Set is incompatible."
        )
    included: list[tuple[str, dict[str, object]]] = []
    seen_view_ids: set[str] = set()
    for record in aggregation_input["views"]:
        if (
            not isinstance(record, dict)
            or set(record) - {"currentInput", "artifact"}
            or "currentInput" not in record
            or not is_gaussian_evidence_admission_input(record["currentInput"])
        ):
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select reference aggregation contains an invalid current View input."
            )
        current_input = record["currentInput"]
        assert isinstance(current_input, dict)
        current_view = current_input["view"]
        assert isinstance(current_view, dict)
        view_id = current_view["viewId"]
        assert isinstance(view_id, str)
        if (
            view_id in seen_view_ids
            or current_input["targetSplatId"] != target_splat_id
            or current_input["evidenceWorkingSet"] != evidence_working_set
            or not _same_request_binding(
                current_input["requestBinding"], request_binding
            )
        ):
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select reference aggregation View identity is incompatible."
            )
        seen_view_ids.add(view_id)
        if current_view["participation"] == "excluded":
            continue
        artifact = record.get("artifact")
        if not is_current_gaussian_evidence_artifact(artifact, current_input):
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select Included View is missing current compatible Evidence."
            )
        assert isinstance(artifact, dict)
        included.append((view_id, artifact))

    if not included:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation has no Included current Evidence."
        )
    included.sort(key=lambda entry: entry[0])

    universe = list(aggregation_input["classificationUniverseStableGaussianIds"])
    universe_set = set(universe)
    evidence_scope = list(evidence_working_set["stableGaussianIds"])
    evidence_scope_set = set(evidence_scope)
    if not evidence_scope_set.issubset(universe_set):
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select Evidence scope lies outside the classification universe."
        )
    for _, source in included:
        source_ids = source["stableGaussianIds"]
        assert isinstance(source_ids, list)
        if not set(source_ids).issubset(evidence_scope_set):
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select artifact lies outside the current Evidence scope."
            )

    gaussian_records: list[dict[str, object]] = []
    selected: list[int] = []
    rejected: list[int] = []
    uncertain: list[int] = []
    out_of_scope: list[int] = []
    cap_value = validated_policy["perViewVisibleMassCap"]
    cap = float(cap_value) if cap_value is not None else None
    indexed_sources = _index_source_artifacts(included)
    for stable_id in universe:
        if stable_id not in evidence_scope_set:
            out_of_scope.append(stable_id)
            gaussian_records.append(
                {
                    "stableGaussianId": stable_id,
                    "classification": "out-of-scope",
                    "uncertaintyReason": None,
                }
            )
            continue

        raw_positive = 0.0
        raw_negative = 0.0
        raw_visible = 0.0
        effective_positive = 0.0
        effective_negative = 0.0
        effective_visible = 0.0
        observed_view_ids: list[str] = []
        positive_view_ids: list[str] = []
        negative_view_ids: list[str] = []
        mixed_view_ids: list[str] = []
        per_view: list[dict[str, object]] = []
        for view_id, source, source_index_by_id in indexed_sources:
            source_index = source_index_by_id.get(stable_id)
            if source_index is None:
                continue
            positive = float(source["positiveMass"][source_index])
            negative = float(source["negativeMass"][source_index])
            visible = float(source["visibleMass"][source_index])
            scale = (
                min(1.0, cap / visible)
                if cap is not None and visible > 0.0
                else 1.0
            )
            capped_positive = positive * scale
            capped_negative = negative * scale
            capped_visible = visible * scale
            raw_positive += positive
            raw_negative += negative
            raw_visible += visible
            effective_positive += capped_positive
            effective_negative += capped_negative
            effective_visible += capped_visible
            view_evidence = capped_positive + capped_negative
            if capped_visible >= float(
                validated_policy["minimumPerViewVisibleMass"]
            ):
                observed_view_ids.append(view_id)
            if view_evidence >= float(
                validated_policy["minimumPerViewEvidenceMass"]
            ):
                positive_ratio = capped_positive / view_evidence
                negative_ratio = capped_negative / view_evidence
                if (
                    positive_ratio
                    >= float(validated_policy["selectedPositiveRatioThreshold"])
                ):
                    positive_view_ids.append(view_id)
                if (
                    negative_ratio
                    >= float(validated_policy["rejectedNegativeRatioThreshold"])
                ):
                    negative_view_ids.append(view_id)
                if (
                    positive_ratio
                    >= float(validated_policy["materialPositiveRatioThreshold"])
                    and negative_ratio
                    >= float(validated_policy["materialNegativeRatioThreshold"])
                ):
                    mixed_view_ids.append(view_id)
            per_view.append(
                {
                    "viewId": view_id,
                    "artifactDigest": source["artifactDigest"],
                    "rawPositiveMass": positive,
                    "rawNegativeMass": negative,
                    "rawVisibleMass": visible,
                    "effectivePositiveMass": capped_positive,
                    "effectiveNegativeMass": capped_negative,
                    "effectiveVisibleMass": capped_visible,
                    "normalizationScale": scale,
                }
            )

        if not all(
            math.isfinite(mass)
            for mass in (
                raw_positive,
                raw_negative,
                raw_visible,
                effective_positive,
                effective_negative,
                effective_visible,
            )
        ):
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select reference aggregation requires finite aggregate Evidence."
            )
        classification, reason = _classification(
            effective_positive,
            effective_negative,
            effective_visible,
            positive_view_ids,
            negative_view_ids,
            mixed_view_ids,
            validated_policy,
        )
        if classification == "selected":
            selected.append(stable_id)
        elif classification == "rejected":
            rejected.append(stable_id)
        else:
            uncertain.append(stable_id)
        gaussian_records.append(
            {
                "stableGaussianId": stable_id,
                "classification": classification,
                "uncertaintyReason": reason,
                "rawPositiveMass": raw_positive,
                "rawNegativeMass": raw_negative,
                "rawVisibleMass": raw_visible,
                "effectivePositiveMass": effective_positive,
                "effectiveNegativeMass": effective_negative,
                "effectiveVisibleMass": effective_visible,
                "observedViewIds": observed_view_ids,
                "positiveSupportingViewIds": positive_view_ids,
                "negativeSupportingViewIds": negative_view_ids,
                "mixedViewIds": mixed_view_ids,
                "perView": per_view,
            }
        )

    artifact_set = _evidence_artifact_set(included)
    payload: dict[str, object] = {
        "schemaVersion": REFERENCE_AGGREGATION_RESULT_SCHEMA_VERSION,
        "requestBinding": deepcopy(request_binding),
        "targetSplatId": target_splat_id,
        "aggregationPolicy": validated_policy,
        "aggregationPolicyDigest": validated_policy["aggregationPolicyDigest"],
        "classificationUniverseStableGaussianIds": universe,
        "evidenceWorkingSet": deepcopy(evidence_working_set),
        "evidenceWorkingSetToken": evidence_working_set[
            "evidenceWorkingSetToken"
        ],
        "evidenceScopeStableGaussianIds": evidence_scope,
        "evidenceArtifactSet": artifact_set,
        "evidenceArtifactSetDigest": canonical_json_digest(
            {"artifacts": artifact_set}
        ),
        "referenceBackendIdentities": _reference_backend_identities(included),
        "sourceEvidenceArtifacts": [
            deepcopy(source) for _, source in included
        ],
        "gaussians": gaussian_records,
        "selectedStableGaussianIds": selected,
        "rejectedStableGaussianIds": rejected,
        "uncertainStableGaussianIds": uncertain,
        "outOfScopeStableGaussianIds": out_of_scope,
        "candidateInputStableGaussianIds": list(selected),
    }
    return {
        **payload,
        "resultDigest": canonical_json_digest(payload),
    }


def is_reference_gaussian_evidence_aggregation_result(value: object) -> bool:
    """Validate the complete immutable handoff contract consumed by Ticket 14D."""

    expected_keys = {
        "schemaVersion",
        "requestBinding",
        "targetSplatId",
        "aggregationPolicy",
        "aggregationPolicyDigest",
        "classificationUniverseStableGaussianIds",
        "evidenceWorkingSet",
        "evidenceWorkingSetToken",
        "evidenceScopeStableGaussianIds",
        "evidenceArtifactSet",
        "evidenceArtifactSetDigest",
        "referenceBackendIdentities",
        "sourceEvidenceArtifacts",
        "gaussians",
        "selectedStableGaussianIds",
        "rejectedStableGaussianIds",
        "uncertainStableGaussianIds",
        "outOfScopeStableGaussianIds",
        "candidateInputStableGaussianIds",
        "resultDigest",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or value.get("schemaVersion")
        != REFERENCE_AGGREGATION_RESULT_SCHEMA_VERSION
        or not _is_digest(value.get("resultDigest"))
        or not _is_digest(value.get("evidenceArtifactSetDigest"))
    ):
        return False
    try:
        policy = _validated_policy(value["aggregationPolicy"])
    except ReferenceGaussianEvidenceAggregationError:
        return False
    if value.get("aggregationPolicyDigest") != policy["aggregationPolicyDigest"]:
        return False
    universe = value.get("classificationUniverseStableGaussianIds")
    if not _is_sorted_stable_ids(universe):
        return False
    evidence_working_set = value.get("evidenceWorkingSet")
    if (
        not is_evidence_working_set(evidence_working_set)
        or not isinstance(evidence_working_set, dict)
        or evidence_working_set.get("targetSplatId") != value.get("targetSplatId")
        or value.get("evidenceWorkingSetToken")
        != evidence_working_set.get("evidenceWorkingSetToken")
        or value.get("evidenceScopeStableGaussianIds")
        != evidence_working_set.get("stableGaussianIds")
    ):
        return False
    class_keys = (
        "selectedStableGaussianIds",
        "rejectedStableGaussianIds",
        "uncertainStableGaussianIds",
        "outOfScopeStableGaussianIds",
    )
    classes = [value.get(key) for key in class_keys]
    if any(
        not isinstance(stable_ids, list)
        or (
            bool(stable_ids)
            and not _is_sorted_stable_ids(stable_ids)
        )
        for stable_ids in classes
    ):
        return False
    class_sets = [set(stable_ids) for stable_ids in classes]
    if (
        any(
            class_sets[left_index] & class_sets[right_index]
            for left_index in range(len(class_sets))
            for right_index in range(left_index + 1, len(class_sets))
        )
        or set().union(*class_sets) != set(universe)
        or value.get("candidateInputStableGaussianIds") != classes[0]
    ):
        return False
    sources = value.get("sourceEvidenceArtifacts")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not is_gaussian_evidence_artifact(source) for source in sources)
    ):
        return False
    included = sorted(
        (
            str(source["viewId"]),
            source,
        )
        for source in sources
    )
    if len({view_id for view_id, _ in included}) != len(included):
        return False
    request_binding = value.get("requestBinding")
    target_splat_id = value.get("targetSplatId")
    if any(
        source.get("requestBinding") != request_binding
        or source.get("targetSplatId") != target_splat_id
        or source.get("evidenceWorkingSetToken")
        != evidence_working_set.get("evidenceWorkingSetToken")
        or source.get("stableGaussianIds")
        != evidence_working_set.get("stableGaussianIds")
        for _, source in included
    ):
        return False
    artifact_set = _evidence_artifact_set(included)
    source_scope = {
        stable_id
        for _, source in included
        for stable_id in source["stableGaussianIds"]
    }
    evidence_scope = evidence_working_set.get("stableGaussianIds")
    if not _is_sorted_stable_ids(evidence_scope):
        return False
    if not isinstance(evidence_scope, list):
        return False
    if not source_scope.issubset(set(evidence_scope)):
        return False
    if (
        value.get("evidenceArtifactSet") != artifact_set
        or value.get("evidenceArtifactSetDigest")
        != canonical_json_digest({"artifacts": artifact_set})
        or value.get("referenceBackendIdentities")
        != _reference_backend_identities(included)
        or not set(evidence_scope).issubset(set(universe))
    ):
        return False
    gaussians = value.get("gaussians")
    if (
        not isinstance(gaussians, list)
        or [
            record.get("stableGaussianId")
            for record in gaussians
            if isinstance(record, dict)
        ]
        != universe
        or len(gaussians) != len(universe)
    ):
        return False
    expected_class_by_id = {
        stable_id: classification
        for classification, stable_ids in zip(
            ("selected", "rejected", "uncertain", "out-of-scope"),
            classes,
            strict=True,
        )
        for stable_id in stable_ids
    }
    if any(
        not isinstance(record, dict)
        or record.get("classification")
        != expected_class_by_id.get(record.get("stableGaussianId"))
        for record in gaussians
    ):
        return False
    payload = {key: item for key, item in value.items() if key != "resultDigest"}
    try:
        return canonical_json_digest(payload) == value["resultDigest"]
    except (TypeError, ValueError):
        return False
