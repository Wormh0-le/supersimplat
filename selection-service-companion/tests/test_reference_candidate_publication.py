from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.reference_candidate_publication import (
    ReferenceCandidatePublicationError,
    create_reference_candidate_artifact,
    is_reference_candidate_artifact,
)
from selection_service_companion.reference_candidate_quality import (
    score_reference_candidate_quality,
)
from selection_service_companion.reference_gaussian_evidence_aggregation import (
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def dependency() -> dict[str, object]:
    return {
        "splatId": "editor-splat:1",
        "renderStateToken": "render-v1",
        "geometryToken": "geometry-v1",
        "gaussianIdentityToken": "gaussians-v1",
        "worldTransformToken": "transform-v1",
    }


def request_binding() -> dict[str, object]:
    return {
        "targetContextId": "ai-target-context-1",
        "contextRevision": 3,
        "dependencyToken": dependency(),
    }


def current_input(
    view_id: str,
    *,
    participation: str = "included",
    stable_mask_digest: str | None = None,
) -> dict[str, object]:
    camera_digest = digest("a" if view_id == "view-1" else "f")
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": participation,
            "cameraBindingDigest": camera_digest,
            "rgbDigest": digest("b"),
            "stableMaskDigest": stable_mask_digest or digest(view_id[-1]),
        },
        "evidencePolicyDigest": digest("e"),
        "renderWorkingSet": {
            "targetSplatId": "editor-splat:1",
            "dependencyToken": dependency(),
            "cameraBindingDigest": camera_digest,
            "renderWorkingSetToken": digest("d"),
            "stableGaussianIds": [5, 9, 11, 13, 42],
            "completeness": "complete",
        },
        "evidenceWorkingSet": create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": [5, 9, 11],
                "contextStableGaussianIds": [13],
            }
        ),
        "rasterImplementationId": "gsplat-reference-rgb/v1",
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": "complete-contributor/reference-v1",
        "runtimeBuildId": "locked-runtime-build-1",
    }


def artifact(
    value: dict[str, object],
    *,
    positive: list[float],
    negative: list[float],
    visible: list[float],
) -> dict[str, object]:
    admission = admit_gaussian_evidence(value)
    assert admission["status"] == "admitted"
    return create_gaussian_evidence_artifact(
        admission["admission"],
        {
            "positiveMass": positive,
            "negativeMass": negative,
            "visibleMass": visible,
        },
    )


def lift_input(
    *,
    second_participation: str = "included",
    second_stable_mask_digest: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    first_input = current_input("view-1")
    first_artifact = artifact(
        first_input,
        positive=[0.9, 0.0, 0.5, 0.0],
        negative=[0.0, 0.9, 0.5, 0.0],
        visible=[1.0, 1.0, 1.0, 0.0],
    )
    second_input = current_input(
        "view-2",
        participation=second_participation,
        stable_mask_digest=second_stable_mask_digest,
    )
    views: list[dict[str, object]] = [
        {"currentInput": first_input, "artifact": first_artifact},
        {"currentInput": second_input},
    ]
    if second_participation == "included":
        views[1]["artifact"] = artifact(
            second_input,
            positive=[0.8, 0.0, 0.1, 0.0],
            negative=[0.0, 0.8, 0.1, 0.0],
            visible=[1.0, 1.0, 0.2, 0.0],
        )
    aggregation_input = {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "classificationUniverseStableGaussianIds": [5, 9, 11, 13, 42],
        "classificationScopeStableGaussianIds": [5, 9, 11, 13],
        "evidenceWorkingSet": deepcopy(first_input["evidenceWorkingSet"]),
        "views": views,
    }
    aggregation_result = aggregate_reference_gaussian_evidence(
        aggregation_input,
        default_reference_aggregation_policy(),
    )
    return aggregation_input, aggregation_result


class ReferenceCandidatePublicationTests(unittest.TestCase):
    def test_browser_contract_golden_vector_matches_companion_publication(self) -> None:
        aggregation_input, _ = lift_input()
        aggregation_input["views"].append(
            {
                "currentInput": current_input(
                    "视图😀",
                    participation="excluded",
                    stable_mask_digest=digest("3"),
                )
            }
        )
        aggregation_result = aggregate_reference_gaussian_evidence(
            aggregation_input,
            default_reference_aggregation_policy(),
        )
        candidate = create_reference_candidate_artifact(
            aggregation_input,
            aggregation_result,
        )
        fixture = json.loads(
            (
                Path(__file__).parents[2]
                / "test/fixtures/ai-select-reference-candidate-contract-vector.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(candidate, fixture["artifact"])

    def test_candidate_binds_exact_current_inputs_and_keeps_uncertain_separate(
        self,
    ) -> None:
        aggregation_input, aggregation_result = lift_input()

        candidate = create_reference_candidate_artifact(
            aggregation_input,
            aggregation_result,
        )

        self.assertEqual(candidate["candidate"], {"selectedStableGaussianIds": [5]})
        self.assertEqual(candidate["uncertain"], {"stableGaussianIds": [11, 13]})
        self.assertEqual(candidate["publicationKind"], "reference-pre-production")
        self.assertEqual(candidate["productionReadiness"], "reference-only")
        self.assertEqual(
            candidate["publicationBinding"]["requestBinding"], request_binding()
        )
        self.assertEqual(
            candidate["publicationBinding"]["referenceBackendIdentity"],
            {
                "rasterImplementationId": "gsplat-reference-rgb/v1",
                "evidenceBackendKind": "reference-contributor",
                "evidenceBackendId": "complete-contributor/reference-v1",
                "runtimeBuildId": "locked-runtime-build-1",
            },
        )
        self.assertTrue(is_reference_candidate_artifact(candidate))

    def test_stale_or_incompatible_aggregate_fails_before_candidate_creation(
        self,
    ) -> None:
        aggregation_input, aggregation_result = lift_input()
        changed = deepcopy(aggregation_input)
        changed["views"][1]["currentInput"]["view"]["stableMaskDigest"] = digest("9")

        with self.assertRaisesRegex(
            ReferenceCandidatePublicationError,
            "current aggregation inputs",
        ):
            create_reference_candidate_artifact(changed, aggregation_result)

        forged = deepcopy(aggregation_result)
        forged["candidateInputStableGaussianIds"] = [5, 11]
        with self.assertRaisesRegex(
            ReferenceCandidatePublicationError,
            "complete compatible aggregation",
        ):
            create_reference_candidate_artifact(aggregation_input, forged)

    def test_participation_is_part_of_the_stable_input_set_identity(self) -> None:
        included_input, included_result = lift_input()
        included = create_reference_candidate_artifact(included_input, included_result)
        excluded_input, excluded_result = lift_input(second_participation="excluded")
        excluded = create_reference_candidate_artifact(excluded_input, excluded_result)

        self.assertNotEqual(
            included["publicationBinding"]["stableInputSetDigest"],
            excluded["publicationBinding"]["stableInputSetDigest"],
        )
        self.assertNotEqual(included["candidateDigest"], excluded["candidateDigest"])

    def test_excluded_view_without_stable_mask_does_not_block_publication(self) -> None:
        aggregation_input, _ = lift_input(second_participation="excluded")
        aggregation_input["views"][1]["currentInput"]["view"].pop(
            "stableMaskDigest"
        )
        aggregation_result = aggregate_reference_gaussian_evidence(
            aggregation_input,
            default_reference_aggregation_policy(),
        )

        candidate = create_reference_candidate_artifact(
            aggregation_input,
            aggregation_result,
        )

        self.assertTrue(is_reference_candidate_artifact(candidate))

    def test_quality_gate_reports_every_supported_parent_metric(self) -> None:
        _, multi_result = lift_input()
        _, excluded_result = lift_input(second_participation="excluded")
        report = score_reference_candidate_quality(
            {
                "selectedStableGaussianIds": multi_result[
                    "selectedStableGaussianIds"
                ],
                "uncertainStableGaussianIds": multi_result[
                    "uncertainStableGaussianIds"
                ],
                "rejectedStableGaussianIds": multi_result[
                    "rejectedStableGaussianIds"
                ],
                "truthSelectedStableGaussianIds": [5, 11],
                "truthBackgroundStableGaussianIds": [9, 13],
                "singleViewSelectedStableGaussianIds": [5, 9],
                "novelViewPredictedMask": [True, True, False, False],
                "novelViewGroundTruthMask": [True, False, True, False],
                "excludedViewSelectedStableGaussianIds": excluded_result[
                    "selectedStableGaussianIds"
                ],
                "expectedExcludedViewSelectedStableGaussianIds": [5],
                "referenceComparison": {
                    "availableBackendPairs": 0,
                    "thresholdNearCount": 0,
                    "classificationDifferenceCount": 0,
                },
            }
        )

        self.assertEqual(report["gaussianPrecision"], 1.0)
        self.assertEqual(report["gaussianRecall"], 0.5)
        self.assertAlmostEqual(report["novelViewRenderedMaskIoU"], 1 / 3)
        self.assertEqual(report["backgroundContamination"], 0.0)
        self.assertEqual(report["mixedRatio"], 0.5)
        self.assertEqual(report["userAddBurdenProxy"], 1)
        self.assertEqual(report["userRemoveBurdenProxy"], 0)
        self.assertEqual(report["singleVsMultiViewEffect"]["falsePositiveDelta"], -1)
        self.assertTrue(report["viewExclusionCorrect"])
        self.assertEqual(
            report["referenceComparison"]["classificationDifferenceCount"], 0
        )
        self.assertEqual(report["referenceComparison"]["thresholdNearCount"], 0)

    def test_committed_quality_record_comes_from_locked_gpu_reference_output(
        self,
    ) -> None:
        record = json.loads(
            (
                Path(__file__).parents[2]
                / "docs/ai-select/benchmarks/14d-reference-candidate-quality.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            record["fixtureId"],
            "ticket-14d-locked-gpu-reference-quality/v1",
        )
        self.assertEqual(
            record["execution"]["backend"],
            "locked-gpu-reference-contributor",
        )
        self.assertEqual(record["execution"]["runtimeStatus"], "ready")
        self.assertEqual(record["quality"]["novelViewRenderedMaskIoU"], 1.0)
        self.assertEqual(
            record["novelView"]["predictedMaskDigest"],
            record["novelView"]["groundTruthMaskDigest"],
        )
        self.assertEqual(
            record["referenceComparison"]["availableBackendKinds"],
            ["reference-contributor"],
        )
        self.assertEqual(
            record["unavailableReferenceBackends"][0]["evidenceBackendKind"],
            "reference-autograd",
        )


if __name__ == "__main__":
    unittest.main()
