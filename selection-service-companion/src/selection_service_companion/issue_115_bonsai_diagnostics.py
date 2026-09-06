"""Small, non-production diagnostic consumer for issue #115.

The consumer deliberately keeps the existing Evidence and aggregation
contracts at the boundary.  It performs one raw-mass aggregation of the
confirmed A/B artifacts, derives the Anchor-only view from the A row of that
same aggregation, and keeps C as an inspection-only projection.  It does not
publish a Candidate or alter Scope, Readiness, or Native Selection.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Final

from .digests import canonical_json_digest
from .gaussian_evidence_contract import (
    is_evidence_working_set,
    is_gaussian_evidence_artifact,
)
from .reference_gaussian_evidence_aggregation import (
    aggregate_reference_gaussian_evidence,
    reference_aggregation_policy,
)

ISSUE_115_DIAGNOSTIC_SCHEMA_VERSION: Final = 1
ISSUE_115_DIAGNOSTIC_KIND: Final = "issue-115-bonsai-3d-diagnostics/v1"
ISSUE_115_RAW_AGGREGATION_MODE: Final = "raw-mass-sum/v1"
ISSUE_115_PRIOR_A: Final = 1.0
ISSUE_115_PRIOR_B: Final = 1.0
ISSUE_115_EVIDENCE_TAU: Final = 1.0
ISSUE_115_VISIBLE_TAU: Final = 1.0

_AGGREGATION_RESULT_KEYS: Final = {
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
_AGGREGATION_RECORD_KEYS: Final = {
    "stableGaussianId",
    "classification",
    "uncertaintyReason",
    "rawPositiveMass",
    "rawNegativeMass",
    "rawVisibleMass",
    "effectivePositiveMass",
    "effectiveNegativeMass",
    "effectiveVisibleMass",
    "observedViewIds",
    "positiveSupportingViewIds",
    "negativeSupportingViewIds",
    "mixedViewIds",
    "perView",
}
_PER_VIEW_RECORD_KEYS: Final = {
    "viewId",
    "artifactDigest",
    "rawPositiveMass",
    "rawNegativeMass",
    "rawVisibleMass",
    "effectivePositiveMass",
    "effectiveNegativeMass",
    "effectiveVisibleMass",
    "normalizationScale",
}


class Issue115DiagnosticError(ValueError):
    """An issue #115 diagnostic input failed closed."""


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Issue115DiagnosticError(f"{label} must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise Issue115DiagnosticError(f"{label} must be a finite number.")
    return number


def _sorted_ids(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or any(
            isinstance(stable_id, bool)
            or not isinstance(stable_id, int)
            or stable_id < 0
            for stable_id in value
        )
        or any(value[index - 1] >= value[index] for index in range(1, len(value)))
    ):
        raise Issue115DiagnosticError(
            f"{label} must be sorted, unique Stable Gaussian IDs."
        )
    return list(value)


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _is_sorted_id_shape(value: object, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(
            isinstance(stable_id, int)
            and not isinstance(stable_id, bool)
            and 0 <= stable_id <= 0xFFFFFFFF
            for stable_id in value
        )
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _is_nonnegative_finite(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0.0


def _is_view_id_list(value: object, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(view_id, str) and view_id in expected for view_id in value)
        and len(set(value)) == len(value)
    )


def _classify(
    *,
    positive: float,
    negative: float,
    visible: float,
    positive_view_ids: Sequence[str],
    negative_view_ids: Sequence[str],
    mixed_view_ids: Sequence[str],
    aggregation_policy: Mapping[str, object],
) -> tuple[str, str | None]:
    """Mirror the existing aggregator's frozen classification rules."""

    if visible < float(aggregation_policy["minimumAggregateVisibleMass"]):
        return "uncertain", "unobserved-or-insufficient"
    evidence = positive + negative
    if evidence < float(aggregation_policy["minimumAggregateEvidenceMass"]):
        return "uncertain", "insufficient-evidence"
    positive_ratio = positive / evidence
    negative_ratio = negative / evidence
    positive_support = (
        positive_ratio
        >= float(aggregation_policy["selectedPositiveRatioThreshold"])
    )
    negative_support = (
        negative_ratio
        >= float(aggregation_policy["rejectedNegativeRatioThreshold"])
    )
    mixed_support = (
        positive_ratio
        >= float(aggregation_policy["materialPositiveRatioThreshold"])
        and negative_ratio
        >= float(aggregation_policy["materialNegativeRatioThreshold"])
    )
    if positive_view_ids and negative_view_ids:
        return "uncertain", "conflicting-views"
    if mixed_view_ids or mixed_support:
        return "uncertain", "mixed-positive-negative"
    if positive_support:
        return "selected", None
    if negative_support:
        return "rejected", None
    return "uncertain", "undecided-support"


def _posterior_and_support(
    *, positive: float, negative: float, visible: float
) -> tuple[float, float]:
    denominator = ISSUE_115_PRIOR_A + ISSUE_115_PRIOR_B + positive + negative
    if denominator <= 0.0 or not math.isfinite(denominator):
        raise Issue115DiagnosticError("The q denominator must be finite and positive.")
    q = (ISSUE_115_PRIOR_A + positive) / denominator
    support = (
        1.0 - math.exp(-(positive + negative) / ISSUE_115_EVIDENCE_TAU)
    ) * (1.0 - math.exp(-visible / ISSUE_115_VISIBLE_TAU))
    if not math.isfinite(q) or not math.isfinite(support):
        raise Issue115DiagnosticError("The q/s diagnostic must remain finite.")
    return q, support


def _source_by_view(
    aggregation_result: Mapping[str, object],
    *,
    anchor_view_id: str,
    secondary_view_id: str,
) -> dict[str, Mapping[str, object]]:
    sources = aggregation_result.get("sourceEvidenceArtifacts")
    if not isinstance(sources, list):
        raise Issue115DiagnosticError("The aggregation result has no source artifacts.")
    by_view: dict[str, Mapping[str, object]] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            raise Issue115DiagnosticError("The aggregation source artifact is invalid.")
        view_id = source.get("viewId")
        if not isinstance(view_id, str) or view_id in by_view:
            raise Issue115DiagnosticError("The aggregation source View identity is invalid.")
        by_view[view_id] = source
    expected = {anchor_view_id, secondary_view_id}
    if set(by_view) != expected:
        raise Issue115DiagnosticError(
            "Issue #115 requires exactly the confirmed Anchor and B source artifacts."
        )
    return by_view


def _aligned_artifact_masses(
    source: Mapping[str, object], universe: Sequence[int]
) -> tuple[Sequence[object], Sequence[object], Sequence[object], Sequence[object]]:
    """Validate one source and align its four mass arrays to the universe."""

    stable_ids = source.get("stableGaussianIds")
    if not isinstance(stable_ids, list):
        raise Issue115DiagnosticError("The source Stable Gaussian ID array is invalid.")
    arrays: list[list[object]] = []
    for name in ("positiveMass", "negativeMass", "visibleMass"):
        array = source.get(name)
        if not isinstance(array, list) or len(array) != len(stable_ids):
            raise Issue115DiagnosticError(f"The source {name} array is invalid.")
        arrays.append(array)
    boundary_array = source.get("boundaryMass")
    if boundary_array is None:
        arrays.append([0.0] * len(stable_ids))
    elif isinstance(boundary_array, list) and len(boundary_array) == len(stable_ids):
        arrays.append(boundary_array)
    else:
        raise Issue115DiagnosticError("The source boundaryMass array is invalid.")
    if stable_ids == list(universe):
        aligned = arrays
    else:
        source_index_by_id = {
            int(stable_id): index for index, stable_id in enumerate(stable_ids)
        }
        aligned = [
            [
                0.0 if (source_index := source_index_by_id.get(stable_id)) is None
                else array[source_index]
                for stable_id in universe
            ]
            for array in arrays
        ]
    for name, array in zip(
        ("positiveMass", "negativeMass", "visibleMass", "boundaryMass"),
        aligned,
        strict=True,
    ):
        for value in array:
            if _finite(value, f"source {name}") < 0.0:
                raise Issue115DiagnosticError("Evidence masses must be non-negative.")
    return aligned[0], aligned[1], aligned[2], aligned[3]


def _view_diagnostic(
    *,
    stable_ids: Sequence[int],
    masses: tuple[Sequence[object], Sequence[object], Sequence[object], Sequence[object]],
    classifications: Sequence[tuple[str, str | None]],
    view_ids: Sequence[str],
) -> dict[str, object]:
    positive: list[float] = []
    negative: list[float] = []
    visible: list[float] = []
    boundary: list[float] = []
    q_values: list[float | None] = []
    support_values: list[float | None] = []
    selected: list[int] = []
    rejected: list[int] = []
    uncertain: list[int] = []
    out_of_scope: list[int] = []
    reasons: dict[str, str] = {}
    for index, stable_id in enumerate(stable_ids):
        classification, reason = classifications[index]
        if classification == "out-of-scope":
            values = (0.0, 0.0, 0.0, 0.0)
            q_support: tuple[float, float] | None = None
            out_of_scope.append(stable_id)
        else:
            values = tuple(
                _finite(array[index], f"view {name}")
                for name, array in zip(
                    ("positiveMass", "negativeMass", "visibleMass", "boundaryMass"),
                    masses,
                    strict=True,
                )
            )
            q_support = _posterior_and_support(
                positive=values[0], negative=values[1], visible=values[2]
            )
            if classification == "selected":
                selected.append(stable_id)
            elif classification == "rejected":
                rejected.append(stable_id)
            elif classification == "uncertain":
                uncertain.append(stable_id)
        positive.append(values[0])
        negative.append(values[1])
        visible.append(values[2])
        boundary.append(values[3])
        q_values.append(None if q_support is None else q_support[0])
        support_values.append(None if q_support is None else q_support[1])
        if reason is not None:
            reasons[str(stable_id)] = reason
    return {
        "viewIds": list(view_ids),
        "stableGaussianIds": list(stable_ids),
        "positiveMass": positive,
        "negativeMass": negative,
        "visibleMass": visible,
        "boundaryMass": boundary,
        "q": q_values,
        "s": support_values,
        "selectedStableGaussianIds": selected,
        "rejectedStableGaussianIds": rejected,
        "uncertainStableGaussianIds": uncertain,
        "outOfScopeStableGaussianIds": out_of_scope,
        "uncertaintyReasonByStableGaussianId": reasons,
    }


def _validate_c_inspection(
    value: object, universe: Sequence[int]
) -> tuple[str, list[int], dict[str, object]]:
    if not isinstance(value, Mapping):
        raise Issue115DiagnosticError("C inspection input is required.")
    view_id = value.get("viewId")
    if not isinstance(view_id, str) or not view_id.strip():
        raise Issue115DiagnosticError("C inspection View identity is invalid.")
    visible_ids = _sorted_ids(
        value.get("visibleStableGaussianIds"), "C visible Stable Gaussian IDs"
    )
    if not set(visible_ids).issubset(set(universe)):
        raise Issue115DiagnosticError(
            "C inspection contains a Stable Gaussian ID outside the classification universe."
        )
    metadata = {
        "viewId": view_id,
        "cameraBindingDigest": value.get("cameraBindingDigest"),
        "rgbDigest": value.get("rgbDigest"),
        "visibleStableGaussianIds": visible_ids,
        "participation": "inspection-only",
        "usedForFusion": False,
        "stableMaskPresent": False,
    }
    for name in ("cameraBindingDigest", "rgbDigest"):
        if not isinstance(metadata[name], str) or not metadata[name].strip():
            raise Issue115DiagnosticError(f"C inspection {name} is invalid.")
    return view_id, visible_ids, metadata


def _is_aggregation_result_shape_valid(value: object) -> bool:
    """Validate the existing result envelope without running aggregation again.

    The complete aggregation validator rebuilds the numerical result to prove
    semantic equivalence.  That would be a second aggregation pass for this
    diagnostic, so this boundary instead checks the immutable envelope,
    canonical result digest, source artifacts, and every consumed mass field.
    """

    if not isinstance(value, Mapping) or set(value) != _AGGREGATION_RESULT_KEYS:
        return False
    policy = value["aggregationPolicy"]
    expected_policy = reference_aggregation_policy(
        aggregation_mode=ISSUE_115_RAW_AGGREGATION_MODE
    )
    sources = value["sourceEvidenceArtifacts"]
    evidence_working_set = value["evidenceWorkingSet"]
    universe = value["classificationUniverseStableGaussianIds"]
    scope = value["classificationScopeStableGaussianIds"]
    if (
        value["schemaVersion"] != 1
        or policy != expected_policy
        or value["aggregationPolicyDigest"]
        != expected_policy["aggregationPolicyDigest"]
        or not isinstance(value["requestBinding"], Mapping)
        or not isinstance(value["targetSplatId"], str)
        or not value["targetSplatId"].strip()
        or not is_evidence_working_set(evidence_working_set)
        or not isinstance(evidence_working_set, Mapping)
        or evidence_working_set.get("targetSplatId") != value["targetSplatId"]
        or value["evidenceWorkingSetToken"]
        != evidence_working_set.get("evidenceWorkingSetToken")
        or not _is_sorted_id_shape(universe, allow_empty=False)
        or not _is_sorted_id_shape(scope, allow_empty=False)
        or scope != universe
        or value["evidenceScopeStableGaussianIds"]
        != evidence_working_set.get("stableGaussianIds")
        or not isinstance(sources, list)
        or len(sources) != 2
        or not all(is_gaussian_evidence_artifact(source) for source in sources)
    ):
        return False

    source_by_view = {
        source["viewId"]: source
        for source in sources
        if isinstance(source, Mapping) and isinstance(source.get("viewId"), str)
    }
    if len(source_by_view) != len(sources):
        return False
    source_view_ids = set(source_by_view)
    if not source_view_ids or any(
        source.get("requestBinding") != value["requestBinding"]
        or source.get("targetSplatId") != value["targetSplatId"]
        or source.get("evidenceWorkingSetToken")
        != evidence_working_set.get("evidenceWorkingSetToken")
        or source.get("stableGaussianIds")
        != evidence_working_set.get("stableGaussianIds")
        for source in sources
    ):
        return False
    if value["sourceEvidencePolicyDigest"] != next(
        iter(source_by_view.values())
    )["evidencePolicyDigest"] or not _is_digest(
        value["sourceEvidencePolicyDigest"]
    ):
        return False
    if any(
        source["evidencePolicyDigest"] != value["sourceEvidencePolicyDigest"]
        for source in sources
    ):
        return False

    expected_artifact_set = [
        {
            "viewId": view_id,
            "artifactDigest": source_by_view[view_id]["artifactDigest"],
        }
        for view_id in sorted(source_by_view)
    ]
    if (
        value["evidenceArtifactSet"] != expected_artifact_set
        or value["evidenceArtifactSetDigest"]
        != canonical_json_digest({"artifacts": expected_artifact_set})
    ):
        return False
    expected_backend_identities = [
        {
            "rasterImplementationId": identity[0],
            "evidenceBackendKind": identity[1],
            "evidenceBackendId": identity[2],
            "runtimeBuildId": identity[3],
        }
        for identity in sorted({
            (
                source["rasterImplementationId"],
                source["evidenceBackendKind"],
                source["evidenceBackendId"],
                source["runtimeBuildId"],
            )
            for source in sources
        })
    ]
    if value["referenceBackendIdentities"] != expected_backend_identities:
        return False

    records = value["gaussians"]
    if not isinstance(records, list) or len(records) != len(universe):
        return False
    expected_by_class = {"selected": [], "rejected": [], "uncertain": []}
    for stable_id, record in zip(universe, records, strict=True):
        if not isinstance(record, Mapping) or set(record) != _AGGREGATION_RECORD_KEYS:
            return False
        if record["stableGaussianId"] != stable_id or record["classification"] not in {
            "selected",
            "rejected",
            "uncertain",
        }:
            return False
        classification = record["classification"]
        reason = record["uncertaintyReason"]
        if classification == "uncertain":
            if not isinstance(reason, str) or not reason.strip():
                return False
        elif reason is not None:
            return False
        for name in (
            "rawPositiveMass",
            "rawNegativeMass",
            "rawVisibleMass",
            "effectivePositiveMass",
            "effectiveNegativeMass",
            "effectiveVisibleMass",
        ):
            if not _is_nonnegative_finite(record[name]):
                return False
        for name in (
            "observedViewIds",
            "positiveSupportingViewIds",
            "negativeSupportingViewIds",
            "mixedViewIds",
        ):
            if not _is_view_id_list(record[name], source_view_ids):
                return False
        per_view = record["perView"]
        if not isinstance(per_view, list) or len(per_view) != len(sources):
            return False
        seen_per_view: set[str] = set()
        for per_view_record in per_view:
            if (
                not isinstance(per_view_record, Mapping)
                or set(per_view_record) != _PER_VIEW_RECORD_KEYS
                or not isinstance(per_view_record["viewId"], str)
                or per_view_record["viewId"] not in source_view_ids
                or per_view_record["viewId"] in seen_per_view
                or not _is_digest(per_view_record["artifactDigest"])
                or not _is_nonnegative_finite(per_view_record["normalizationScale"])
                or any(
                    not _is_nonnegative_finite(per_view_record[name])
                    for name in (
                        "rawPositiveMass",
                        "rawNegativeMass",
                        "rawVisibleMass",
                        "effectivePositiveMass",
                        "effectiveNegativeMass",
                        "effectiveVisibleMass",
                    )
                )
            ):
                return False
            seen_per_view.add(per_view_record["viewId"])
        expected_by_class[classification].append(stable_id)

    if any(
        value[key] != expected_by_class[classification]
        for key, classification in (
            ("selectedStableGaussianIds", "selected"),
            ("rejectedStableGaussianIds", "rejected"),
            ("uncertainStableGaussianIds", "uncertain"),
        )
    ) or value["outOfScopeStableGaussianIds"] != []:
        return False
    if value["candidateInputStableGaussianIds"] != value["selectedStableGaussianIds"]:
        return False
    result_payload = {
        key: item for key, item in value.items() if key != "resultDigest"
    }
    try:
        return _is_digest(value["resultDigest"]) and canonical_json_digest(
            result_payload
        ) == value["resultDigest"]
    except (TypeError, ValueError):
        return False


def build_issue_115_diagnostics(
    *,
    aggregation_result: Mapping[str, object],
    c_inspection: Mapping[str, object],
    anchor_view_id: str = "anchor-view",
    secondary_view_id: str = "view-b",
) -> dict[str, object]:
    """Build both views and the C inspection from one existing aggregation."""

    if not _is_aggregation_result_shape_valid(aggregation_result):
        raise Issue115DiagnosticError(
            "Issue #115 requires one valid raw-mass aggregation result."
        )
    source_by_view = _source_by_view(
        aggregation_result,
        anchor_view_id=anchor_view_id,
        secondary_view_id=secondary_view_id,
    )
    universe = _sorted_ids(
        aggregation_result.get("classificationUniverseStableGaussianIds"),
        "classification universe",
    )
    scope = _sorted_ids(
        aggregation_result.get("classificationScopeStableGaussianIds"),
        "classification scope",
    )
    if scope != universe:
        raise Issue115DiagnosticError(
            "Issue #115 diagnostic requires the declared full classification scope."
        )
    aggregate_records = aggregation_result.get("gaussians")
    if not isinstance(aggregate_records, list) or len(aggregate_records) != len(universe):
        raise Issue115DiagnosticError("The aggregation Gaussian records are invalid.")
    for stable_id, record in zip(universe, aggregate_records, strict=True):
        if not isinstance(record, Mapping) or not isinstance(
            record.get("stableGaussianId"), int
        ) or record["stableGaussianId"] != stable_id:
            raise Issue115DiagnosticError("The aggregation Gaussian record is invalid.")

    source_masses: dict[
        str, tuple[Sequence[object], Sequence[object], Sequence[object], Sequence[object]]
    ] = {}
    for view_id, source in source_by_view.items():
        source_masses[view_id] = _aligned_artifact_masses(source, universe)

    policy = aggregation_result["aggregationPolicy"]
    if not isinstance(policy, Mapping):
        raise Issue115DiagnosticError("The aggregation policy is invalid.")
    anchor_masses = source_masses[anchor_view_id]
    fused_masses: tuple[list[float], list[float], list[float], list[float]] = (
        [],
        [],
        [],
        [],
    )
    anchor_classifications: list[tuple[str, str | None]] = []
    fused_classifications: list[tuple[str, str | None]] = []
    for index, (stable_id, aggregate) in enumerate(
        zip(universe, aggregate_records, strict=True)
    ):
        if aggregate.get("classification") == "out-of-scope":
            anchor_classifications.append(("out-of-scope", None))
            fused_classifications.append(("out-of-scope", None))
            for array in fused_masses:
                array.append(0.0)
            continue
        anchor_positive = _finite(
            anchor_masses[0][index], "anchor positiveMass"
        )
        anchor_negative = _finite(
            anchor_masses[1][index], "anchor negativeMass"
        )
        anchor_visible = _finite(anchor_masses[2][index], "anchor visibleMass")
        anchor_classifications.append(_classify(
            positive=anchor_positive,
            negative=anchor_negative,
            visible=anchor_visible,
            positive_view_ids=(
                [anchor_view_id]
                if anchor_positive + anchor_negative
                >= float(policy["minimumPerViewEvidenceMass"])
                and anchor_positive / (anchor_positive + anchor_negative)
                >= float(policy["selectedPositiveRatioThreshold"])
                else []
            ),
            negative_view_ids=(
                [anchor_view_id]
                if anchor_positive + anchor_negative
                >= float(policy["minimumPerViewEvidenceMass"])
                and anchor_negative / (anchor_positive + anchor_negative)
                >= float(policy["rejectedNegativeRatioThreshold"])
                else []
            ),
            mixed_view_ids=(
                [anchor_view_id]
                if anchor_positive + anchor_negative
                >= float(policy["minimumPerViewEvidenceMass"])
                and anchor_positive / (anchor_positive + anchor_negative)
                >= float(policy["materialPositiveRatioThreshold"])
                and anchor_negative / (anchor_positive + anchor_negative)
                >= float(policy["materialNegativeRatioThreshold"])
                else []
            ),
            aggregation_policy=policy,
        ))
        aggregate_positive = _finite(
            aggregate.get("effectivePositiveMass"), "aggregate effectivePositiveMass"
        )
        aggregate_negative = _finite(
            aggregate.get("effectiveNegativeMass"), "aggregate effectiveNegativeMass"
        )
        aggregate_visible = _finite(
            aggregate.get("effectiveVisibleMass"), "aggregate effectiveVisibleMass"
        )
        aggregate_boundary = _finite(
            anchor_masses[3][index], "anchor boundaryMass"
        ) + _finite(
            source_masses[secondary_view_id][3][index], "secondary boundaryMass"
        )
        fused_masses[0].append(aggregate_positive)
        fused_masses[1].append(aggregate_negative)
        fused_masses[2].append(aggregate_visible)
        fused_masses[3].append(aggregate_boundary)
        positive_views = aggregate.get("positiveSupportingViewIds")
        negative_views = aggregate.get("negativeSupportingViewIds")
        mixed_views = aggregate.get("mixedViewIds")
        if not all(isinstance(value, list) for value in (positive_views, negative_views, mixed_views)):
            raise Issue115DiagnosticError("The aggregation support View IDs are invalid.")
        fused_classifications.append(_classify(
            positive=aggregate_positive,
            negative=aggregate_negative,
            visible=aggregate_visible,
            positive_view_ids=[str(value) for value in positive_views],
            negative_view_ids=[str(value) for value in negative_views],
            mixed_view_ids=[str(value) for value in mixed_views],
            aggregation_policy=policy,
        ))

    _c_view_id, c_visible_ids, c_metadata = _validate_c_inspection(
        c_inspection, universe
    )
    anchor_view = _view_diagnostic(
        stable_ids=universe,
        masses=anchor_masses,
        classifications=anchor_classifications,
        view_ids=[anchor_view_id],
    )
    fused_view = _view_diagnostic(
        stable_ids=universe,
        masses=fused_masses,
        classifications=fused_classifications,
        view_ids=[anchor_view_id, secondary_view_id],
    )
    anchor_selected = set(anchor_view["selectedStableGaussianIds"])
    fused_selected = set(fused_view["selectedStableGaussianIds"])
    fused_uncertain = set(fused_view["uncertainStableGaussianIds"])
    fused_rejected = set(fused_view["rejectedStableGaussianIds"])
    boundary_contact = {
        stable_id for stable_id, boundary in zip(
            universe, fused_masses[3], strict=True
        ) if boundary > 0.0
    }
    visible_set = set(c_visible_ids)
    new_ids = sorted(visible_set & (fused_selected - anchor_selected))
    contamination_ids = sorted(visible_set & (boundary_contact | fused_rejected))
    unknown_ids = sorted(visible_set & fused_uncertain)
    known_ids = sorted(visible_set - set(unknown_ids))
    c_output = {
        **c_metadata,
        "newStableGaussianIds": new_ids,
        "contaminationStableGaussianIds": contamination_ids,
        "unknownStableGaussianIds": unknown_ids,
        "knownStableGaussianIds": known_ids,
        "categorySemantics": {
            "new": "C-visible IDs selected only after adding B to Anchor-only.",
            "contamination": (
                "C-visible IDs with A/B mask-boundary contact or fused rejection; "
                "these are inspection candidates, not C ground truth."
            ),
            "unknown": "C-visible IDs still uncertain after the A+B aggregation.",
        },
    }
    payload: dict[str, object] = {
        "schemaVersion": ISSUE_115_DIAGNOSTIC_SCHEMA_VERSION,
        "diagnosticKind": ISSUE_115_DIAGNOSTIC_KIND,
        "requestBinding": aggregation_result["requestBinding"],
        "targetSplatId": aggregation_result["targetSplatId"],
        "aggregationPassCount": 1,
        "aggregationResultDigest": aggregation_result["resultDigest"],
        "aggregationPolicy": aggregation_result["aggregationPolicy"],
        "prior": {
            "a": ISSUE_115_PRIOR_A,
            "b": ISSUE_115_PRIOR_B,
            "tauE": ISSUE_115_EVIDENCE_TAU,
            "tauV": ISSUE_115_VISIBLE_TAU,
        },
        "sourceEvidenceArtifacts": [
            {
                "viewId": view_id,
                "artifactDigest": source["artifactDigest"],
            }
            for view_id, source in sorted(source_by_view.items())
        ],
        "anchorOnly": anchor_view,
        "anchorPlusB": fused_view,
        "cInspection": c_output,
    }
    return {**payload, "diagnosticDigest": canonical_json_digest(payload)}


def aggregate_issue_115_diagnostics(
    *,
    aggregation_input: Mapping[str, object],
    c_inspection: Mapping[str, object],
    anchor_view_id: str = "anchor-view",
    secondary_view_id: str = "view-b",
) -> dict[str, object]:
    """Run the single fixed-weight aggregation and build its diagnostics."""

    aggregation_result = aggregate_reference_gaussian_evidence(
        aggregation_input,
        reference_aggregation_policy(
            aggregation_mode=ISSUE_115_RAW_AGGREGATION_MODE
        ),
    )
    return build_issue_115_diagnostics(
        aggregation_result=aggregation_result,
        c_inspection=c_inspection,
        anchor_view_id=anchor_view_id,
        secondary_view_id=secondary_view_id,
    )


__all__ = [
    "ISSUE_115_DIAGNOSTIC_KIND",
    "ISSUE_115_DIAGNOSTIC_SCHEMA_VERSION",
    "ISSUE_115_EVIDENCE_TAU",
    "ISSUE_115_PRIOR_A",
    "ISSUE_115_PRIOR_B",
    "ISSUE_115_RAW_AGGREGATION_MODE",
    "ISSUE_115_VISIBLE_TAU",
    "Issue115DiagnosticError",
    "aggregate_issue_115_diagnostics",
    "build_issue_115_diagnostics",
]
