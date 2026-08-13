"""Versioned multi-view aggregation for Ticket 14C reference Evidence.

The module consumes independently published per-view P/N/V artifacts and
produces classification input for Ticket 14D. It does not publish a Candidate
or mutate editor-owned Native Selection.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
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


def _source_identity(source: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(source["evidencePolicyDigest"]),
        str(source["rasterImplementationId"]),
        str(source["evidenceBackendKind"]),
        str(source["evidenceBackendId"]),
        str(source["runtimeBuildId"]),
    )


def _compatible_source_identity(
    included: list[tuple[str, dict[str, object]]],
) -> tuple[str, str, str, str, str]:
    identities = {_source_identity(source) for _, source in included}
    if len(identities) != 1:
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select Included Evidence has incompatible source identities."
        )
    return next(iter(identities))


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


@dataclass
class _MassAccumulator:
    positive: float = 0.0
    negative: float = 0.0
    visible: float = 0.0

    def add(self, positive: float, negative: float, visible: float) -> None:
        self.positive += positive
        self.negative += negative
        self.visible += visible

    def is_finite(self) -> bool:
        return all(
            math.isfinite(mass)
            for mass in (self.positive, self.negative, self.visible)
        )


def _per_view_support(
    positive: float,
    negative: float,
    policy: dict[str, object],
) -> tuple[bool, bool, bool]:
    evidence_mass = positive + negative
    if evidence_mass < float(policy["minimumPerViewEvidenceMass"]):
        return False, False, False
    positive_ratio = positive / evidence_mass
    negative_ratio = negative / evidence_mass
    return (
        positive_ratio >= float(policy["selectedPositiveRatioThreshold"]),
        negative_ratio >= float(policy["rejectedNegativeRatioThreshold"]),
        positive_ratio >= float(policy["materialPositiveRatioThreshold"])
        and negative_ratio >= float(policy["materialNegativeRatioThreshold"]),
    )


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


def _aggregate_one_gaussian(
    stable_id: int,
    indexed_sources: list[tuple[str, dict[str, object], dict[int, int]]],
    policy: dict[str, object],
) -> tuple[dict[str, object], str]:
    raw = _MassAccumulator()
    effective = _MassAccumulator()
    observed_view_ids: list[str] = []
    positive_view_ids: list[str] = []
    negative_view_ids: list[str] = []
    mixed_view_ids: list[str] = []
    per_view: list[dict[str, object]] = []
    cap_value = policy["perViewVisibleMassCap"]
    cap = float(cap_value) if cap_value is not None else None

    for view_id, source, source_index_by_id in indexed_sources:
        source_index = source_index_by_id.get(stable_id)
        if source_index is None:
            continue
        positive_mass = source["positiveMass"]
        negative_mass = source["negativeMass"]
        visible_mass = source["visibleMass"]
        assert isinstance(positive_mass, list)
        assert isinstance(negative_mass, list)
        assert isinstance(visible_mass, list)
        positive = float(positive_mass[source_index])
        negative = float(negative_mass[source_index])
        visible = float(visible_mass[source_index])
        scale = (
            min(1.0, cap / visible)
            if cap is not None and visible > 0.0
            else 1.0
        )
        capped_positive = positive * scale
        capped_negative = negative * scale
        capped_visible = visible * scale
        raw.add(positive, negative, visible)
        effective.add(capped_positive, capped_negative, capped_visible)

        if capped_visible >= float(policy["minimumPerViewVisibleMass"]):
            observed_view_ids.append(view_id)
        positive_support, negative_support, mixed_support = _per_view_support(
            capped_positive,
            capped_negative,
            policy,
        )
        if positive_support:
            positive_view_ids.append(view_id)
        if negative_support:
            negative_view_ids.append(view_id)
        if mixed_support:
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

    if not raw.is_finite() or not effective.is_finite():
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select reference aggregation requires finite aggregate Evidence."
        )
    classification, reason = _classification(
        effective.positive,
        effective.negative,
        effective.visible,
        positive_view_ids,
        negative_view_ids,
        mixed_view_ids,
        policy,
    )
    return (
        {
            "stableGaussianId": stable_id,
            "classification": classification,
            "uncertaintyReason": reason,
            "rawPositiveMass": raw.positive,
            "rawNegativeMass": raw.negative,
            "rawVisibleMass": raw.visible,
            "effectivePositiveMass": effective.positive,
            "effectiveNegativeMass": effective.negative,
            "effectiveVisibleMass": effective.visible,
            "observedViewIds": observed_view_ids,
            "positiveSupportingViewIds": positive_view_ids,
            "negativeSupportingViewIds": negative_view_ids,
            "mixedViewIds": mixed_view_ids,
            "perView": per_view,
        },
        classification,
    )


def _classified_gaussians(
    universe: list[int],
    classification_scope: set[int],
    indexed_sources: list[tuple[str, dict[str, object], dict[int, int]]],
    policy: dict[str, object],
) -> tuple[list[dict[str, object]], list[int], list[int], list[int], list[int]]:
    records: list[dict[str, object]] = []
    selected: list[int] = []
    rejected: list[int] = []
    uncertain: list[int] = []
    out_of_scope: list[int] = []
    classifications = {
        "selected": selected,
        "rejected": rejected,
        "uncertain": uncertain,
    }
    for stable_id in universe:
        if stable_id not in classification_scope:
            out_of_scope.append(stable_id)
            records.append(
                {
                    "stableGaussianId": stable_id,
                    "classification": "out-of-scope",
                    "uncertaintyReason": None,
                }
            )
            continue
        record, classification = _aggregate_one_gaussian(
            stable_id,
            indexed_sources,
            policy,
        )
        classifications[classification].append(stable_id)
        records.append(record)
    return records, selected, rejected, uncertain, out_of_scope


def _build_result(
    *,
    request_binding: dict[str, object],
    target_splat_id: str,
    universe: list[int],
    classification_scope: list[int],
    evidence_working_set: dict[str, object],
    included: list[tuple[str, dict[str, object]]],
    policy: dict[str, object],
) -> dict[str, object]:
    source_identity = _compatible_source_identity(included)
    universe_set = set(universe)
    classification_scope_set = set(classification_scope)
    evidence_scope = list(evidence_working_set["stableGaussianIds"])
    evidence_scope_set = set(evidence_scope)
    if (
        not classification_scope_set.issubset(universe_set)
        or not evidence_scope_set.issubset(classification_scope_set)
    ):
        raise ReferenceGaussianEvidenceAggregationError(
            "AI Select classification scope is incompatible with the Evidence scope."
        )
    for _, source in included:
        if source["stableGaussianIds"] != evidence_scope:
            raise ReferenceGaussianEvidenceAggregationError(
                "AI Select artifact is incompatible with the current Evidence scope."
            )

    (
        gaussian_records,
        selected,
        rejected,
        uncertain,
        out_of_scope,
    ) = _classified_gaussians(
        universe,
        classification_scope_set,
        _index_source_artifacts(included),
        policy,
    )
    artifact_set = _evidence_artifact_set(included)
    payload: dict[str, object] = {
        "schemaVersion": REFERENCE_AGGREGATION_RESULT_SCHEMA_VERSION,
        "requestBinding": deepcopy(request_binding),
        "targetSplatId": target_splat_id,
        "aggregationPolicy": deepcopy(policy),
        "aggregationPolicyDigest": policy["aggregationPolicyDigest"],
        "sourceEvidencePolicyDigest": source_identity[0],
        "classificationUniverseStableGaussianIds": list(universe),
        "classificationScopeStableGaussianIds": list(classification_scope),
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
        "sourceEvidenceArtifacts": [deepcopy(source) for _, source in included],
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
            "classificationScopeStableGaussianIds",
            "evidenceWorkingSet",
            "views",
        }
        or not isinstance(aggregation_input["requestBinding"], dict)
        or not isinstance(aggregation_input["targetSplatId"], str)
        or not aggregation_input["targetSplatId"].strip()
        or not _is_sorted_stable_ids(
            aggregation_input["classificationUniverseStableGaussianIds"]
        )
        or not _is_sorted_stable_ids(
            aggregation_input["classificationScopeStableGaussianIds"]
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
    return _build_result(
        request_binding=request_binding,
        target_splat_id=target_splat_id,
        universe=list(
            aggregation_input["classificationUniverseStableGaussianIds"]
        ),
        classification_scope=list(
            aggregation_input["classificationScopeStableGaussianIds"]
        ),
        evidence_working_set=evidence_working_set,
        included=included,
        policy=validated_policy,
    )


def is_reference_gaussian_evidence_aggregation_result(value: object) -> bool:
    """Validate the complete immutable handoff contract consumed by Ticket 14D."""

    expected_keys = {
        "schemaVersion",
        "requestBinding",
        "targetSplatId",
        "aggregationPolicy",
        "aggregationPolicyDigest",
        "sourceEvidencePolicyDigest",
        "classificationUniverseStableGaussianIds",
        "classificationScopeStableGaussianIds",
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
        universe = value["classificationUniverseStableGaussianIds"]
        classification_scope = value["classificationScopeStableGaussianIds"]
        evidence_working_set = value["evidenceWorkingSet"]
        sources = value["sourceEvidenceArtifacts"]
        if (
            value["aggregationPolicyDigest"]
            != policy["aggregationPolicyDigest"]
            or not _is_sorted_stable_ids(universe)
            or not _is_sorted_stable_ids(classification_scope)
            or not is_evidence_working_set(evidence_working_set)
            or not isinstance(evidence_working_set, dict)
            or not isinstance(sources, list)
            or not sources
            or any(
                not is_gaussian_evidence_artifact(source) for source in sources
            )
        ):
            return False
        included = sorted(
            (str(source["viewId"]), source) for source in sources
        )
        if len({view_id for view_id, _ in included}) != len(included):
            return False
        request_binding = value["requestBinding"]
        target_splat_id = value["targetSplatId"]
        if (
            evidence_working_set.get("targetSplatId") != target_splat_id
            or any(
                source.get("requestBinding") != request_binding
                or source.get("targetSplatId") != target_splat_id
                or source.get("evidenceWorkingSetToken")
                != evidence_working_set.get("evidenceWorkingSetToken")
                or source.get("stableGaussianIds")
                != evidence_working_set.get("stableGaussianIds")
                for _, source in included
            )
        ):
            return False
        expected = _build_result(
            request_binding=request_binding,
            target_splat_id=target_splat_id,
            universe=list(universe),
            classification_scope=list(classification_scope),
            evidence_working_set=evidence_working_set,
            included=included,
            policy=policy,
        )
        return value == expected
    except (ReferenceGaussianEvidenceAggregationError, TypeError, ValueError):
        return False
