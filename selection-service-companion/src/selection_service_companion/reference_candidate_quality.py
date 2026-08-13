"""Reference Candidate quality metrics for frozen Ticket 14 fixtures."""

from __future__ import annotations

from copy import deepcopy
from typing import Final


REFERENCE_CANDIDATE_QUALITY_SCHEMA_VERSION: Final = 1
REFERENCE_CANDIDATE_QUALITY_POLICY_ID: Final = "candidate-quality/reference-v1"
_MAX_STABLE_GAUSSIAN_ID: Final = (1 << 32) - 1


class ReferenceCandidateQualityError(ValueError):
    """A Candidate quality fixture is incomplete or internally inconsistent."""


def _is_stable_id_array(value: object, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(
            isinstance(stable_id, int)
            and not isinstance(stable_id, bool)
            and 0 <= stable_id <= _MAX_STABLE_GAUSSIAN_ID
            for stable_id in value
        )
        and all(value[index - 1] < value[index] for index in range(1, len(value)))
    )


def _stable_id_set(value: object, label: str) -> set[int]:
    if not _is_stable_id_array(value):
        raise ReferenceCandidateQualityError(
            f"AI Select Candidate quality {label} is invalid."
        )
    assert isinstance(value, list)
    return set(value)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _zero_when_empty_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _mask_iou(predicted: object, truth: object) -> float:
    if (
        not isinstance(predicted, list)
        or not isinstance(truth, list)
        or not predicted
        or len(predicted) != len(truth)
        or any(not isinstance(value, bool) for value in [*predicted, *truth])
    ):
        raise ReferenceCandidateQualityError(
            "AI Select Candidate quality novel-View masks are invalid."
        )
    intersection = sum(left and right for left, right in zip(predicted, truth))
    union = sum(left or right for left, right in zip(predicted, truth))
    return _ratio(intersection, union)


def score_reference_candidate_quality(value: object) -> dict[str, object]:
    """Score the parent Ticket 14 metrics supported by one frozen fixture."""

    required = {
        "selectedStableGaussianIds",
        "uncertainStableGaussianIds",
        "rejectedStableGaussianIds",
        "truthSelectedStableGaussianIds",
        "truthBackgroundStableGaussianIds",
        "singleViewSelectedStableGaussianIds",
        "novelViewPredictedMask",
        "novelViewGroundTruthMask",
        "excludedViewSelectedStableGaussianIds",
        "expectedExcludedViewSelectedStableGaussianIds",
        "referenceComparison",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ReferenceCandidateQualityError(
            "AI Select Candidate quality fixture is incomplete."
        )
    selected = _stable_id_set(value["selectedStableGaussianIds"], "selected IDs")
    uncertain = _stable_id_set(
        value["uncertainStableGaussianIds"], "uncertain IDs"
    )
    rejected = _stable_id_set(value["rejectedStableGaussianIds"], "rejected IDs")
    truth_selected = _stable_id_set(
        value["truthSelectedStableGaussianIds"], "truth-selected IDs"
    )
    truth_background = _stable_id_set(
        value["truthBackgroundStableGaussianIds"], "truth-background IDs"
    )
    single_selected = _stable_id_set(
        value["singleViewSelectedStableGaussianIds"], "single-View IDs"
    )
    excluded_selected = _stable_id_set(
        value["excludedViewSelectedStableGaussianIds"], "excluded-View IDs"
    )
    expected_excluded = _stable_id_set(
        value["expectedExcludedViewSelectedStableGaussianIds"],
        "expected excluded-View IDs",
    )
    if (
        selected & uncertain
        or selected & rejected
        or uncertain & rejected
        or truth_selected & truth_background
    ):
        raise ReferenceCandidateQualityError(
            "AI Select Candidate quality classifications must be disjoint."
        )
    comparison = value["referenceComparison"]
    if (
        not isinstance(comparison, dict)
        or set(comparison)
        != {
            "availableBackendPairs",
            "thresholdNearCount",
            "classificationDifferenceCount",
        }
        or any(
            not isinstance(comparison[key], int)
            or isinstance(comparison[key], bool)
            or comparison[key] < 0
            for key in comparison
        )
    ):
        raise ReferenceCandidateQualityError(
            "AI Select Candidate quality reference comparison is invalid."
        )

    true_positive = len(selected & truth_selected)
    false_positive = len(selected & truth_background)
    false_negative = len(truth_selected - selected)
    single_false_positive = len(single_selected & truth_background)
    single_false_negative = len(truth_selected - single_selected)
    classified_count = len(selected | uncertain | rejected)
    return {
        "schemaVersion": REFERENCE_CANDIDATE_QUALITY_SCHEMA_VERSION,
        "policyId": REFERENCE_CANDIDATE_QUALITY_POLICY_ID,
        "gaussianPrecision": (
            _ratio(true_positive, len(selected))
            if selected or not truth_selected
            else 0.0
        ),
        "gaussianRecall": _ratio(true_positive, len(truth_selected)),
        "novelViewRenderedMaskIoU": _mask_iou(
            value["novelViewPredictedMask"],
            value["novelViewGroundTruthMask"],
        ),
        "backgroundContamination": _zero_when_empty_ratio(
            false_positive, len(selected)
        ),
        "mixedRatio": _zero_when_empty_ratio(len(uncertain), classified_count),
        "userAddBurdenProxy": false_negative,
        "userRemoveBurdenProxy": false_positive,
        "singleVsMultiViewEffect": {
            "falsePositiveDelta": false_positive - single_false_positive,
            "falseNegativeDelta": false_negative - single_false_negative,
            "selectedCountDelta": len(selected) - len(single_selected),
        },
        "viewExclusionCorrect": excluded_selected == expected_excluded,
        "referenceComparison": deepcopy(comparison),
    }


__all__ = [
    "REFERENCE_CANDIDATE_QUALITY_POLICY_ID",
    "REFERENCE_CANDIDATE_QUALITY_SCHEMA_VERSION",
    "ReferenceCandidateQualityError",
    "score_reference_candidate_quality",
]
