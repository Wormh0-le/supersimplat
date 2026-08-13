from __future__ import annotations

import math
from copy import deepcopy
import json
from pathlib import Path
import unittest

from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.lift_readiness import (
    default_lift_readiness_policy,
    evaluate_lift_readiness,
    is_lift_readiness_result,
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


def camera_binding(yaw_degrees: float) -> dict[str, object]:
    yaw = math.radians(yaw_degrees)
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    return {
        "revision": 0,
        "cameraToWorld": [
            cosine,
            0.0,
            sine,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            -sine,
            0.0,
            cosine,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
        "projection": {
            "model": "pinhole",
            "fx": 100.0,
            "fy": 100.0,
            "cx": 50.0,
            "cy": 50.0,
            "width": 100,
            "height": 100,
            "near": 0.1,
            "far": 100.0,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }


def formal_readiness_input(
    *,
    yaws: list[float],
    visible_by_view: list[list[float]],
    core_ids: list[int] | None = None,
    target_geometry_hint_seed_digest: str | None = None,
    generation_state: str = "complete",
) -> dict[str, object]:
    from selection_service_companion.camera_binding import camera_binding_digest

    core = core_ids or [5, 9, 11, 13]
    working_set_input: dict[str, object] = {
        "targetSplatId": "editor-splat:1",
        "coreTargetStableIds": core,
        "contextStableGaussianIds": [42],
    }
    if target_geometry_hint_seed_digest is not None:
        working_set_input["targetGeometryHintSeedDigest"] = (
            target_geometry_hint_seed_digest
        )
    working_set = create_evidence_working_set(working_set_input)
    stable_ids = list(working_set["stableGaussianIds"])
    views: list[dict[str, object]] = []
    observation_views: list[dict[str, object]] = []
    for index, (yaw, visible_core) in enumerate(
        zip(yaws, visible_by_view, strict=True), start=1
    ):
        if len(visible_core) != len(core):
            raise AssertionError("Fixture Visible Mass must cover every Core Target ID")
        view_id = f"view-{index}"
        camera = camera_binding(yaw)
        current_input = {
            "requestBinding": request_binding(),
            "targetSplatId": "editor-splat:1",
            "view": {
                "viewId": view_id,
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": camera_binding_digest(camera),
                "rgbDigest": digest("b"),
                "stableMaskDigest": digest(str(index)),
            },
            "evidencePolicyDigest": digest("e"),
            "renderWorkingSet": {
                "targetSplatId": "editor-splat:1",
                "dependencyToken": dependency(),
                "cameraBindingDigest": camera_binding_digest(camera),
                "renderWorkingSetToken": digest("d"),
                "stableGaussianIds": stable_ids,
                "completeness": "complete",
            },
            "evidenceWorkingSet": working_set,
            "rasterImplementationId": "gsplat-reference-rgb/v1",
            "evidenceBackendKind": "reference-contributor",
            "evidenceBackendId": "complete-contributor/reference-v1",
            "runtimeBuildId": "locked-runtime-build-1",
        }
        admission = admit_gaussian_evidence(current_input)
        if admission["status"] != "admitted":
            raise AssertionError("Fixture Evidence input must be admitted")
        visible_by_id = dict(zip(core, visible_core, strict=True))
        visible = [visible_by_id.get(stable_id, 0.0) for stable_id in stable_ids]
        artifact = create_gaussian_evidence_artifact(
            admission["admission"],
            {
                "positiveMass": [value * 4.0 for value in visible],
                "negativeMass": [0.0] * len(stable_ids),
                "visibleMass": visible,
            },
        )
        views.append({"currentInput": current_input, "artifact": artifact})
        observation_views.append({"viewId": view_id, "cameraBinding": camera})
    aggregate = aggregate_reference_gaussian_evidence(
        {
            "requestBinding": request_binding(),
            "targetSplatId": "editor-splat:1",
            "classificationUniverseStableGaussianIds": stable_ids,
            "classificationScopeStableGaussianIds": stable_ids,
            "evidenceWorkingSet": working_set,
            "views": views,
        },
        default_reference_aggregation_policy(),
    )
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "evidenceWorkingSet": working_set,
        "aggregationResult": aggregate,
        "observationViews": observation_views,
        "generationState": generation_state,
        "lowCostSupportDiagnostic": None,
    }


class LiftReadinessTests(unittest.TestCase):
    def test_formal_evidence_overrides_a_low_cost_support_diagnostic(self) -> None:
        value = formal_readiness_input(
            yaws=[-15.0, 15.0],
            visible_by_view=[[0.2] * 4, [0.2] * 4],
        )
        first_artifact = value["aggregationResult"]["sourceEvidenceArtifacts"][0]
        value["lowCostSupportDiagnostic"] = {
            "requestBinding": request_binding(),
            "targetSplatId": "editor-splat:1",
            "viewId": first_artifact["viewId"],
            "cameraBindingDigest": first_artifact["cameraBindingDigest"],
            "rgbDigest": first_artifact["rgbDigest"],
            "stableMaskDigest": first_artifact["stableMaskDigest"],
            "supportProbePolicyVersion": "anchor-support-probe/v1",
            "computable": False,
            "observedGaussianCount": 0,
        }

        result = evaluate_lift_readiness(
            value,
            default_lift_readiness_policy(),
        )

        self.assertEqual(result["source"], "formal-evidence")
        self.assertEqual(result["readiness"], "ready")
        self.assertEqual(result["observationCoverage"]["coverageRatio"], 1.0)
        self.assertIsNotNone(result["lowCostSupportDiagnosticDigest"])

    def test_missing_formal_and_low_cost_support_fails_conservatively(self) -> None:
        working_set = create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": [5, 9],
                "contextStableGaussianIds": [42],
            }
        )

        result = evaluate_lift_readiness(
            {
                "requestBinding": request_binding(),
                "targetSplatId": "editor-splat:1",
                "evidenceWorkingSet": working_set,
                "aggregationResult": None,
                "observationViews": [],
                "generationState": "unavailable",
                "lowCostSupportDiagnostic": None,
            },
            default_lift_readiness_policy(),
        )

        self.assertEqual(result["source"], "none")
        self.assertEqual(result["readiness"], "not-ready")
        self.assertNotIn("coverageRatio", result["observationCoverage"])
        self.assertEqual(result["recommendation"], "add-view")

    def test_missing_formal_evidence_still_requires_exact_target_binding(self) -> None:
        working_set = create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": [5, 9],
                "contextStableGaussianIds": [42],
            }
        )
        stale_binding = request_binding()
        stale_binding["dependencyToken"]["splatId"] = "editor-splat:other"

        with self.assertRaisesRegex(ValueError, "input is invalid"):
            evaluate_lift_readiness(
                {
                    "requestBinding": stale_binding,
                    "targetSplatId": "editor-splat:1",
                    "evidenceWorkingSet": working_set,
                    "aggregationResult": None,
                    "observationViews": [],
                    "generationState": "unavailable",
                    "lowCostSupportDiagnostic": None,
                },
                default_lift_readiness_policy(),
            )

        unsafe_revision = request_binding()
        unsafe_revision["contextRevision"] = 2**53
        with self.assertRaisesRegex(ValueError, "input is invalid"):
            evaluate_lift_readiness(
                {
                    "requestBinding": unsafe_revision,
                    "targetSplatId": "editor-splat:1",
                    "evidenceWorkingSet": working_set,
                    "aggregationResult": None,
                    "observationViews": [],
                    "generationState": "unavailable",
                    "lowCostSupportDiagnostic": None,
                },
                default_lift_readiness_policy(),
            )

        wrong_working_set = create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:other",
                "coreTargetStableIds": [5, 9],
                "contextStableGaussianIds": [42],
            }
        )
        with self.assertRaisesRegex(ValueError, "input is invalid"):
            evaluate_lift_readiness(
                {
                    "requestBinding": request_binding(),
                    "targetSplatId": "editor-splat:1",
                    "evidenceWorkingSet": wrong_working_set,
                    "aggregationResult": None,
                    "observationViews": [],
                    "generationState": "unavailable",
                    "lowCostSupportDiagnostic": None,
                },
                default_lift_readiness_policy(),
            )

    def test_browser_contract_golden_vector_matches_companion_result(self) -> None:
        value = formal_readiness_input(
            yaws=[-15.0, 15.0],
            visible_by_view=[[0.2] * 4, [0.2] * 4],
        )
        result = evaluate_lift_readiness(
            value,
            default_lift_readiness_policy(),
        )
        fixture = json.loads(
            (
                Path(__file__).parents[2]
                / "test/fixtures/ai-select-lift-readiness-contract-vector.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(result, fixture["artifact"])

    def test_result_validation_and_evaluation_are_fail_closed_and_immutable(
        self,
    ) -> None:
        value = formal_readiness_input(
            yaws=[-15.0, 15.0],
            visible_by_view=[[0.2] * 4, [0.2] * 4],
        )
        original = deepcopy(value)
        result = evaluate_lift_readiness(
            value,
            default_lift_readiness_policy(),
        )

        self.assertTrue(is_lift_readiness_result(result))
        self.assertEqual(value, original)
        malformed = deepcopy(result)
        malformed["observationCoverage"]["coverageRatio"] = float("nan")
        self.assertFalse(is_lift_readiness_result(malformed))
        malformed_source = deepcopy(result)
        malformed_source["source"] = []
        self.assertFalse(is_lift_readiness_result(malformed_source))
        malformed_reasons = deepcopy(result)
        malformed_reasons["reasons"] = [[]]
        self.assertFalse(is_lift_readiness_result(malformed_reasons))
        contradictory = deepcopy(result)
        contradictory["readiness"] = "limited"
        contradictory["reasons"] = ["weak-gaussian-support"]
        contradictory["recommendation"] = "generate-more"
        contradictory_payload = {
            key: item
            for key, item in contradictory.items()
            if key != "resultDigest"
        }
        from selection_service_companion.digests import route_b_artifact_digest

        contradictory["resultDigest"] = route_b_artifact_digest(
            contradictory_payload
        )
        self.assertFalse(is_lift_readiness_result(contradictory))
        stale_camera = deepcopy(value)
        stale_camera["observationViews"][0]["cameraBinding"]["revision"] = 1
        with self.assertRaisesRegex(
            ValueError, "CameraBinding digest is incompatible"
        ):
            evaluate_lift_readiness(
                stale_camera,
                default_lift_readiness_policy(),
            )

        malformed_input = deepcopy(value)
        malformed_input["generationState"] = []
        with self.assertRaisesRegex(ValueError, "input is invalid"):
            evaluate_lift_readiness(
                malformed_input,
                default_lift_readiness_policy(),
            )

    def test_view_count_does_not_substitute_for_directional_diversity(self) -> None:
        result = evaluate_lift_readiness(
            formal_readiness_input(
                yaws=[0.0, 0.0, 0.0],
                visible_by_view=[[0.2] * 4, [0.2] * 4, [0.2] * 4],
            ),
            default_lift_readiness_policy(),
        )

        self.assertEqual(result["observationCoverage"]["coverageRatio"], 1.0)
        self.assertEqual(result["viewDiversity"]["usefulViewCount"], 3)
        self.assertEqual(
            result["viewDiversity"]["maximumAngularSeparationDegrees"], 0.0
        )
        self.assertEqual(result["readiness"], "limited")
        self.assertEqual(result["reasons"], ["low-view-diversity"])
        self.assertEqual(result["recommendation"], "generate-more")

    def test_low_visible_mass_is_not_rescued_by_more_duplicate_views(self) -> None:
        result = evaluate_lift_readiness(
            formal_readiness_input(
                yaws=[0.0, 0.0, 0.0],
                visible_by_view=[[0.01] * 4, [0.01] * 4, [0.01] * 4],
                generation_state="active",
            ),
            default_lift_readiness_policy(),
        )

        self.assertAlmostEqual(
            result["observationCoverage"]["coverageRatio"], 0.1
        )
        self.assertEqual(result["readiness"], "not-ready")
        self.assertEqual(
            result["reasons"],
            ["low-visible-support", "weak-gaussian-support"],
        )
        self.assertEqual(result["recommendation"], "wait-for-current-views")

    def test_expanded_geometry_seeded_working_set_changes_formal_coverage(
        self,
    ) -> None:
        result = evaluate_lift_readiness(
            formal_readiness_input(
                yaws=[-15.0, 15.0],
                visible_by_view=[[0.2, 0.2, 0.0], [0.2, 0.2, 0.0]],
                core_ids=[5, 9, 11],
                target_geometry_hint_seed_digest=digest("f"),
            ),
            default_lift_readiness_policy(),
        )

        self.assertAlmostEqual(
            result["observationCoverage"]["coverageRatio"], 2.0 / 3.0
        )
        self.assertEqual(
            result["observationCoverage"]["observedCoreGaussianCount"], 2
        )
        self.assertEqual(result["readiness"], "limited")
        self.assertEqual(result["reasons"], ["weak-gaussian-support"])

    def test_low_cost_support_is_only_an_early_signal_not_formal_coverage(
        self,
    ) -> None:
        working_set = create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": [5, 9],
                "contextStableGaussianIds": [42],
            }
        )

        result = evaluate_lift_readiness(
            {
                "requestBinding": request_binding(),
                "targetSplatId": "editor-splat:1",
                "evidenceWorkingSet": working_set,
                "aggregationResult": None,
                "observationViews": [],
                "generationState": "complete",
                "lowCostSupportDiagnostic": {
                    "requestBinding": request_binding(),
                    "targetSplatId": "editor-splat:1",
                    "viewId": "anchor",
                    "cameraBindingDigest": digest("a"),
                    "rgbDigest": digest("b"),
                    "stableMaskDigest": digest("c"),
                    "supportProbePolicyVersion": "anchor-support-probe/v1",
                    "computable": True,
                    "observedGaussianCount": 8,
                },
            },
            default_lift_readiness_policy(),
        )

        self.assertEqual(result["readiness"], "limited")
        self.assertEqual(
            result["observationCoverage"],
            {
                "status": "pending-formal-evidence",
                "totalCoreGaussianCount": 2,
            },
        )
        self.assertNotIn("coverageRatio", result["observationCoverage"])
        self.assertEqual(result["viewDiversity"]["status"], "pending-formal-evidence")
        self.assertEqual(result["reasons"], ["formal-evidence-pending"])

    def test_formal_visible_evidence_drives_coverage_and_directional_readiness(
        self,
    ) -> None:
        from selection_service_companion.camera_binding import camera_binding_digest

        stable_ids = [5, 9, 11, 13]
        working_set = create_evidence_working_set(
            {
                "targetSplatId": "editor-splat:1",
                "coreTargetStableIds": stable_ids,
                "contextStableGaussianIds": [42],
            }
        )
        views: list[dict[str, object]] = []
        observation_views: list[dict[str, object]] = []
        for index, yaw in enumerate((-15.0, 15.0), start=1):
            view_id = f"view-{index}"
            camera = camera_binding(yaw)
            current_input = {
                "requestBinding": request_binding(),
                "targetSplatId": "editor-splat:1",
                "view": {
                    "viewId": view_id,
                    "renderStatus": "ready",
                    "participation": "included",
                    "cameraBindingDigest": camera_binding_digest(camera),
                    "rgbDigest": digest("b"),
                    "stableMaskDigest": digest(str(index)),
                },
                "evidencePolicyDigest": digest("e"),
                "renderWorkingSet": {
                    "targetSplatId": "editor-splat:1",
                    "dependencyToken": dependency(),
                    "cameraBindingDigest": camera_binding_digest(camera),
                    "renderWorkingSetToken": digest("d"),
                    "stableGaussianIds": [5, 9, 11, 13, 42],
                    "completeness": "complete",
                },
                "evidenceWorkingSet": working_set,
                "rasterImplementationId": "gsplat-reference-rgb/v1",
                "evidenceBackendKind": "reference-contributor",
                "evidenceBackendId": "complete-contributor/reference-v1",
                "runtimeBuildId": "locked-runtime-build-1",
            }
            admission = admit_gaussian_evidence(current_input)
            self.assertEqual(admission["status"], "admitted")
            artifact = create_gaussian_evidence_artifact(
                admission["admission"],
                {
                    "positiveMass": [0.8, 0.8, 0.8, 0.8, 0.0],
                    "negativeMass": [0.0, 0.0, 0.0, 0.0, 0.0],
                    "visibleMass": [0.2, 0.2, 0.2, 0.2, 0.0],
                },
            )
            views.append({"currentInput": current_input, "artifact": artifact})
            observation_views.append(
                {"viewId": view_id, "cameraBinding": camera}
            )

        aggregate = aggregate_reference_gaussian_evidence(
            {
                "requestBinding": request_binding(),
                "targetSplatId": "editor-splat:1",
                "classificationUniverseStableGaussianIds": [5, 9, 11, 13, 42],
                "classificationScopeStableGaussianIds": [5, 9, 11, 13, 42],
                "evidenceWorkingSet": working_set,
                "views": views,
            },
            default_reference_aggregation_policy(),
        )

        result = evaluate_lift_readiness(
            {
                "requestBinding": request_binding(),
                "targetSplatId": "editor-splat:1",
                "evidenceWorkingSet": working_set,
                "aggregationResult": aggregate,
                "observationViews": observation_views,
                "generationState": "complete",
                "lowCostSupportDiagnostic": None,
            },
            default_lift_readiness_policy(),
        )

        self.assertEqual(
            {
                "readiness": result["readiness"],
                "coverage": result["observationCoverage"]["coverageRatio"],
                "observed": result["observationCoverage"][
                    "observedCoreGaussianCount"
                ],
                "diversity": result["viewDiversity"][
                    "maximumAngularSeparationDegrees"
                ],
                "reasons": result["reasons"],
                "recommendation": result["recommendation"],
            },
            {
                "readiness": "ready",
                "coverage": 1.0,
                "observed": 4,
                "diversity": 30.0,
                "reasons": [],
                "recommendation": "none",
            },
        )


if __name__ == "__main__":
    unittest.main()
