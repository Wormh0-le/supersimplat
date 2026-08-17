from __future__ import annotations

from copy import deepcopy
import math
import unittest

from selection_service_companion.candidate_re_lift import (
    CandidateReLiftError,
    produce_production_candidate_re_lift,
    produce_reference_candidate_re_lift,
    validate_candidate_re_lift_snapshot_binding,
)
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.camera_binding import camera_binding_digest
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.reference_gaussian_evidence import (
    ReferenceGaussianEvidenceError,
    default_reference_evidence_policy,
)


def digest(letter: str) -> str:
    return f"sha256:{letter * 64}"


def request_binding() -> dict[str, object]:
    return {
        "targetContextId": "ai-target-context-1",
        "contextRevision": 3,
        "dependencyToken": {
            "splatId": "editor-splat:1",
            "renderStateToken": "render-v1",
            "geometryToken": "geometry-v1",
            "gaussianIdentityToken": "gaussians-v1",
            "worldTransformToken": "transform-v1",
        },
    }


def current_input(view_id: str, participation: str = "included") -> dict[str, object]:
    camera = camera_binding(view_id)
    camera_digest = camera_binding_digest(camera)
    working_set = create_evidence_working_set(
        {
            "targetSplatId": "editor-splat:1",
            "coreTargetStableIds": [5, 9, 11],
            "contextStableGaussianIds": [13],
        }
    )
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": participation,
            "cameraBindingDigest": camera_digest,
            "rgbDigest": digest("b"),
            "stableMaskDigest": digest("c"),
        },
        "evidencePolicyDigest": default_reference_evidence_policy()[
            "evidencePolicyDigest"
        ],
        "renderWorkingSet": {
            "targetSplatId": "editor-splat:1",
            "dependencyToken": request_binding()["dependencyToken"],
            "cameraBindingDigest": camera_digest,
            "renderWorkingSetToken": digest("d"),
            "stableGaussianIds": [5, 9, 11, 13, 42],
            "completeness": "complete",
        },
        "evidenceWorkingSet": working_set,
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": "complete-contributor/reference-v1",
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    }


def artifact(value: dict[str, object]) -> dict[str, object]:
    admitted = admit_gaussian_evidence(value)
    assert admitted["status"] == "admitted"
    return create_gaussian_evidence_artifact(
        admitted["admission"],
        {
            "positiveMass": [0.9, 0.0, 0.5, 0.0],
            "negativeMass": [0.0, 0.9, 0.5, 0.0],
            "visibleMass": [1.0, 1.0, 1.0, 0.0],
        },
    )


def camera_binding(view_id: str) -> dict[str, object]:
    yaw = math.radians(-15.0 if view_id == "view-1" else 15.0)
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    return {
        "revision": 0,
        "cameraToWorld": [
            cosine, 0.0, sine, 0.0,
            0.0, 1.0, 0.0, 0.0,
            -sine, 0.0, cosine, 0.0,
            0.0, 0.0, 0.0, 1.0,
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


def view_record(
    view_id: str,
    participation: str = "included",
    *,
    cached: dict[str, object] | None = None,
) -> dict[str, object]:
    result = {
        "currentInput": current_input(view_id, participation),
        "cameraBinding": camera_binding(view_id),
        "stableMask": {"digest": digest("c")},
    }
    if cached is not None:
        result["cachedArtifact"] = cached
    return result


def request(views: list[dict[str, object]]) -> dict[str, object]:
    first = views[0]["currentInput"]
    return {
        "liftAttemptId": "re-lift-1",
        "sceneId": "scene-1",
        "sceneVersion": digest("1"),
        "renderConfigVersion": "render-config-v1",
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:1",
        "classificationUniverseStableGaussianIds": [5, 9, 11, 13, 42],
        "classificationScopeStableGaussianIds": [5, 9, 11, 13],
        "evidenceWorkingSet": deepcopy(first["evidenceWorkingSet"]),
        "views": views,
    }


def production_record(view_id: str) -> dict[str, object]:
    current = current_input(view_id)
    current["evidenceBackendKind"] = "production-direct"
    current["evidenceBackendId"] = "global-atomic/direct-v1"
    return view_record(view_id, cached=artifact(current)) | {
        "currentInput": current
    }


def production_request(views: list[dict[str, object]]) -> dict[str, object]:
    value = request(views)
    value["productionIdentityDigest"] = digest("a")
    value["generationState"] = "complete"
    value["classificationUniverseStableGaussianIds"] = [5, 9, 11, 13]
    value["classificationScopeStableGaussianIds"] = [5, 9, 11, 13]
    return value


class CandidateReLiftTests(unittest.TestCase):
    def test_production_re_lift_publishes_only_from_complete_direct_evidence(self) -> None:
        response = produce_production_candidate_re_lift(
            production_request(
                [production_record("view-1"), production_record("view-2")]
            )
        )

        self.assertEqual(response["candidate"]["productionReadiness"], "production-ready")
        self.assertEqual(response["liftReadiness"]["readiness"], "ready")
        self.assertEqual(
            response["candidate"]["publicationBinding"]["evidenceBackendIdentity"][
                "evidenceBackendKind"
            ],
            "production-direct",
        )
        self.assertEqual(
            response["candidate"]["publicationBinding"][
                "productionIdentityDigest"
            ],
            digest("a"),
        )
        self.assertEqual(
            response["candidate"]["candidate"]["selectedStableGaussianIds"],
            [5],
        )

    def test_production_re_lift_rejects_missing_evidence_without_partial_candidate(self) -> None:
        missing = production_record("view-1")
        missing.pop("cachedArtifact")
        with self.assertRaisesRegex(CandidateReLiftError, "incomplete or stale"):
            produce_production_candidate_re_lift(
                production_request([missing])
            )

    def test_production_re_lift_publishes_not_ready_without_a_candidate(self) -> None:
        current = current_input("view-1")
        current["evidenceBackendKind"] = "production-direct"
        current["evidenceBackendId"] = "global-atomic/direct-v1"
        admitted = admit_gaussian_evidence(current)
        self.assertEqual(admitted["status"], "admitted")
        weak = create_gaussian_evidence_artifact(
            admitted["admission"],
            {
                "positiveMass": [0.01, 0.01, 0.01, 0.0],
                "negativeMass": [0.0, 0.0, 0.0, 0.0],
                "visibleMass": [0.01, 0.01, 0.01, 0.0],
            },
        )
        record = view_record("view-1") | {
            "currentInput": current,
            "cachedArtifact": weak,
        }

        response = produce_production_candidate_re_lift(
            production_request([record])
        )

        self.assertEqual(response["status"], "not-ready")
        self.assertEqual(response["liftReadiness"]["readiness"], "not-ready")
        self.assertNotIn("candidate", response)

    def test_reuses_only_exact_current_included_evidence(self) -> None:
        first_input = current_input("view-1")
        cached = artifact(first_input)
        produced: list[str] = []

        response = produce_reference_candidate_re_lift(
            request(
                [
                    view_record("view-1", cached=cached),
                    view_record("view-2"),
                ]
            ),
            lambda current, _mask, _camera: (
                produced.append(current["view"]["viewId"]) or artifact(current)
            ),
        )

        self.assertEqual(produced, ["view-2"])
        self.assertEqual(
            [(item["viewId"], item["reused"]) for item in response["evidence"]],
            [("view-1", True), ("view-2", False)],
        )
        self.assertEqual(
            response["candidate"]["candidate"]["selectedStableGaussianIds"],
            [5],
        )
        self.assertEqual(
            response["candidate"]["uncertain"]["stableGaussianIds"],
            [11, 13],
        )
        self.assertNotIn("readiness", response)

    def test_excluded_view_never_produces_or_contributes_evidence(self) -> None:
        produced: list[str] = []
        response = produce_reference_candidate_re_lift(
            request(
                [
                    view_record("view-1"),
                    view_record("view-2", "excluded"),
                ]
            ),
            lambda current, _mask, _camera: (
                produced.append(current["view"]["viewId"]) or artifact(current)
            ),
        )

        self.assertEqual(produced, ["view-1"])
        self.assertEqual([item["viewId"] for item in response["evidence"]], ["view-1"])

    def test_stale_cached_evidence_is_recomputed(self) -> None:
        stale_input = current_input("view-1")
        stale_artifact = artifact(stale_input)
        changed = view_record("view-1", cached=stale_artifact)
        changed["currentInput"]["view"]["stableMaskDigest"] = digest("9")
        changed["stableMask"]["digest"] = digest("9")
        produced: list[str] = []

        response = produce_reference_candidate_re_lift(
            request([changed]),
            lambda current, _mask, _camera: (
                produced.append(current["view"]["viewId"]) or artifact(current)
            ),
        )

        self.assertEqual(produced, ["view-1"])
        self.assertFalse(response["evidence"][0]["reused"])

    def test_failure_publishes_no_partial_candidate(self) -> None:
        with self.assertRaisesRegex(CandidateReLiftError, "view-2"):
            produce_reference_candidate_re_lift(
                request([view_record("view-1"), view_record("view-2")]),
                lambda current, _mask, _camera: (
                    artifact(current)
                    if current["view"]["viewId"] == "view-1"
                    else (_ for _ in ()).throw(RuntimeError("GPU failed"))
                ),
            )

    def test_evidence_failure_preserves_the_actionable_service_code(self) -> None:
        def fail_evidence(*_args: object) -> dict[str, object]:
            raise ReferenceGaussianEvidenceError(
                "Contributor rendering failed (rendererMassMismatch).",
                code="referenceRenderFailed",
                cause_code="rendererMassMismatch",
            )

        with self.assertRaises(CandidateReLiftError) as raised:
            produce_reference_candidate_re_lift(
                request([view_record("view-1")]),
                fail_evidence,
            )

        self.assertEqual(raised.exception.code, "referenceRenderFailed")
        self.assertIn("rendererMassMismatch", str(raised.exception))

    def test_rejects_an_unlocked_reference_runtime_before_reuse(self) -> None:
        record = view_record("view-1")
        record["currentInput"]["runtimeBuildId"] = "unlocked-runtime"

        with self.assertRaisesRegex(CandidateReLiftError, "unsupported"):
            produce_reference_candidate_re_lift(
                request([record]),
                lambda current, _mask, _camera: artifact(current),
            )

    def test_snapshot_binding_is_required_even_when_all_evidence_is_reused(
        self,
    ) -> None:
        current = current_input("view-1")
        cached = artifact(current)
        value = request([view_record("view-1", cached=cached)])

        with self.assertRaisesRegex(CandidateReLiftError, "Scene Snapshot"):
            validate_candidate_re_lift_snapshot_binding(
                value,
                scene_content_digest=digest("9"),
                scene_stable_ids=[5, 9, 11, 13, 42],
            )

    def test_rejects_duplicate_view_ids(self) -> None:
        with self.assertRaisesRegex(CandidateReLiftError, "incompatible"):
            produce_reference_candidate_re_lift(
                request([view_record("view-1"), view_record("view-1")]),
                lambda current, _mask, _camera: artifact(current),
            )

    def test_rejects_camera_or_stable_mask_binding_mismatch(self) -> None:
        record = view_record("view-1")
        record["stableMask"]["digest"] = digest("9")

        with self.assertRaisesRegex(CandidateReLiftError, "Camera/Mask"):
            produce_reference_candidate_re_lift(
                request([record]),
                lambda current, _mask, _camera: artifact(current),
            )


if __name__ == "__main__":
    unittest.main()
