from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from selection_service_companion.depth_classified_negative_evidence_experiment import (
    build_depth_classified_negative_evidence_sidecar,
    replay_depth_classified_negative_evidence,
)
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.reference_gaussian_evidence_aggregation import (
    default_reference_aggregation_policy,
)
from selection_service_companion.depth_moment_readout import (
    DepthMomentReadoutRecord,
    DepthMomentTelemetry,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import DepthMomentValidityPolicy
from selection_service_companion.depth_classified_negative_evidence_benchmark import (
    DepthClassifiedNegativeEvidenceBenchmarkError,
    create_baseline_run_record,
    create_experiment_input_identity,
    create_variant_run_record,
    load_depth_classified_negative_evidence_configuration,
    persist_baseline_run_record,
    persist_sidecar_failure,
    persist_variant_run_record,
    score_depth_classified_negative_evidence_prediction,
    seal_depth_classified_negative_evidence_prediction,
)


def digest(character: str) -> str:
    return "sha256:" + (character * 64)


def locked_runtime_source() -> dict[str, object]:
    return {
        "directEvidenceAbiVersion": "supersimplat-direct-evidence-abi/v3",
        "directEvidenceSourceRevision": digest("1"),
        "directEvidenceRuntimeBuildId": digest("2"),
        "rendererRuntimeDigest": digest("e"),
        "gpuName": "Locked Test GPU",
        "computeCapability": "8.9",
        "torchVersion": "2.11.0+cu128",
        "cudaVersion": "12.8",
        "gsplatSourceCommit": "7" * 40,
    }


def depth_readout(raw_depth_moments: object) -> DepthMomentReadoutRecord:
    policy = DepthMomentValidityPolicy(
        policy_id="depth-moment-minimum-m0/experimental-reference-v1",
        minimum_m0=0.1,
    )
    admission = {
        "requestBinding": {
            "targetContextId": "experimental-context",
            "contextRevision": 1,
            "dependencyToken": {
                "splatId": "fixture-splat",
                "renderStateToken": "render-1",
                "geometryToken": "geometry-1",
                "gaussianIdentityToken": "gaussians-1",
                "worldTransformToken": "transform-1",
            },
        },
        "targetSplatId": "fixture-splat",
        "viewId": "view-1",
        "cameraBindingDigest": digest("a"),
        "rgbDigest": digest("b"),
        "stableMaskDigest": digest("c"),
        "evidencePolicyDigest": digest("d"),
        "renderWorkingSetToken": digest("e"),
        "evidenceWorkingSetToken": digest("f"),
        "stableGaussianIds": [10, 11, 12, 13],
        "rasterImplementationId": "supersimplat-gsplat-direct-evidence/v1",
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": "global-atomic/direct-v1",
        "runtimeBuildId": digest("1"),
    }
    identity = create_depth_moment_readout_identity(
        admission,
        render_stable_ids_by_projected_row=(10, 11, 12, 13),
        policy=policy,
        width=4,
        height=1,
        direct_evidence_abi_version="supersimplat-direct-evidence-abi/v3",
        direct_evidence_source_revision=digest("2"),
        direct_evidence_runtime_build_id=digest("1"),
    )
    return DepthMomentReadoutRecord(
        identity=identity,
        raw_depth_moments=raw_depth_moments,
        policy=policy,
        telemetry=DepthMomentTelemetry(
            depth_moment_buffer_bytes=48,
            peak_vram_bytes=4096,
        ),
    )


class DepthClassifiedNegativeEvidenceTests(unittest.TestCase):
    def test_classifies_front_near_behind_and_invalid_without_losing_baseline_mass(
        self,
    ) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch is unavailable outside the locked renderer runtime")

        readout = depth_readout(
            torch.tensor(
                [
                    [
                        [1.0, 2.0, 4.01],
                        [1.0, 2.0, 4.01],
                        [1.0, 2.0, 4.01],
                        [0.0, 0.0, 0.0],
                    ]
                ],
                dtype=torch.float32,
            )
        )

        sidecar = build_depth_classified_negative_evidence_sidecar(
            relation_config={
                "schemaVersion": 1,
                "relationId": "front-near-behind/cwed-variance-v1",
                "absoluteBand": 0.25,
                "relativeCwedBand": 0.0,
                "standardDeviationMultiplier": 0.0,
            },
            depth_readout=readout,
            stable_ids_by_projected_row=(10, 11, 12, 13),
            evidence_stable_ids=(10, 11, 12, 13),
            contributor_row_ids=torch.tensor([[[0], [1], [2], [3]]], dtype=torch.int64),
            contributor_weights=torch.full((1, 4, 1), 0.5, dtype=torch.float32),
            projected_depth_by_row=torch.tensor(
                [1.0, 2.0, 3.0, 2.0], dtype=torch.float32
            ),
            negative_pixel_weights=torch.ones(4, dtype=torch.float64),
            baseline_negative_mass=torch.full((4,), 0.5, dtype=torch.float32),
            baseline_artifact_digest=digest("3"),
            accepted_contribution_sequence_digest=digest("4"),
        )

        self.assertEqual(
            sidecar["artifactKind"],
            "depth-classified-negative-evidence/experimental-reference",
        )
        self.assertEqual(sidecar["stableGaussianIds"], [10, 11, 12, 13])
        self.assertEqual(sidecar["frontNegativeMass"], [0.5, 0.0, 0.0, 0.0])
        self.assertEqual(sidecar["nearNegativeMass"], [0.0, 0.5, 0.0, 0.0])
        self.assertEqual(sidecar["behindNegativeMass"], [0.0, 0.0, 0.5, 0.0])
        self.assertEqual(sidecar["invalidDepthNegativeMass"], [0.0, 0.0, 0.0, 0.5])
        self.assertTrue(sidecar["baselineMassConservation"]["passed"])
        self.assertEqual(sidecar["bufferWrites"]["total"], 4)
        self.assertRegex(sidecar["artifactDigest"], r"^sha256:[0-9a-f]{64}$")

    def test_replays_variant_coefficients_through_the_existing_candidate_policy(
        self,
    ) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch is unavailable outside the locked renderer runtime")

        stable_ids = [10, 11, 12, 13]
        evidence_working_set = create_evidence_working_set(
            {
                "targetSplatId": "fixture-splat",
                "coreTargetStableIds": [10, 11, 12],
                "contextStableGaussianIds": [13],
            }
        )
        current_input = {
            "requestBinding": {
                "targetContextId": "experimental-context",
                "contextRevision": 1,
                "dependencyToken": {
                    "splatId": "fixture-splat",
                    "renderStateToken": "render-1",
                    "geometryToken": "geometry-1",
                    "gaussianIdentityToken": "gaussians-1",
                    "worldTransformToken": "transform-1",
                },
            },
            "targetSplatId": "fixture-splat",
            "view": {
                "viewId": "view-1",
                "renderStatus": "ready",
                "participation": "included",
                "cameraBindingDigest": digest("a"),
                "rgbDigest": digest("b"),
                "stableMaskDigest": digest("c"),
            },
            "evidencePolicyDigest": digest("d"),
            "renderWorkingSet": {
                "targetSplatId": "fixture-splat",
                "dependencyToken": {
                    "splatId": "fixture-splat",
                    "renderStateToken": "render-1",
                    "geometryToken": "geometry-1",
                    "gaussianIdentityToken": "gaussians-1",
                    "worldTransformToken": "transform-1",
                },
                "cameraBindingDigest": digest("a"),
                "renderWorkingSetToken": digest("e"),
                "stableGaussianIds": stable_ids,
                "completeness": "complete",
            },
            "evidenceWorkingSet": evidence_working_set,
            "rasterImplementationId": "supersimplat-gsplat-direct-evidence/v1",
            "evidenceBackendKind": "production-direct",
            "evidenceBackendId": "global-atomic/direct-v1",
            "runtimeBuildId": digest("1"),
        }
        admitted = admit_gaussian_evidence(current_input)
        self.assertEqual(admitted["status"], "admitted")
        baseline = create_gaussian_evidence_artifact(
            admitted["admission"],
            {
                "positiveMass": [0.9, 0.0, 0.0, 0.0],
                "negativeMass": [0.1, 0.9, 0.0, 0.0],
                "visibleMass": [1.0, 1.0, 0.0, 0.0],
                "boundaryMass": [0.0, 0.0, 0.0, 0.0],
            },
        )
        readout = depth_readout(
            torch.tensor(
                [
                    [
                        [1.0, 2.0, 4.01],
                        [1.0, 2.0, 4.01],
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ]
                ],
                dtype=torch.float32,
            )
        )
        sidecar = build_depth_classified_negative_evidence_sidecar(
            relation_config={
                "schemaVersion": 1,
                "relationId": "front-near-behind/cwed-variance-v1",
                "absoluteBand": 0.25,
                "relativeCwedBand": 0.0,
                "standardDeviationMultiplier": 0.0,
            },
            depth_readout=readout,
            stable_ids_by_projected_row=stable_ids,
            evidence_stable_ids=stable_ids,
            contributor_row_ids=torch.tensor(
                [[[0], [1], [-1], [-1]]], dtype=torch.int64
            ),
            contributor_weights=torch.tensor(
                [[[0.1], [0.9], [0.0], [0.0]]], dtype=torch.float32
            ),
            projected_depth_by_row=torch.tensor(
                [1.0, 3.0, 2.0, 2.0], dtype=torch.float32
            ),
            negative_pixel_weights=torch.ones(4, dtype=torch.float64),
            baseline_negative_mass=torch.tensor(
                [0.1, 0.9, 0.0, 0.0], dtype=torch.float32
            ),
            baseline_artifact_digest=baseline["artifactDigest"],
            accepted_contribution_sequence_digest=digest("4"),
        )
        aggregation_input = {
            "requestBinding": current_input["requestBinding"],
            "targetSplatId": "fixture-splat",
            "classificationUniverseStableGaussianIds": stable_ids,
            "classificationScopeStableGaussianIds": stable_ids,
            "evidenceWorkingSet": evidence_working_set,
            "views": [{"currentInput": current_input, "artifact": baseline}],
        }

        replay = replay_depth_classified_negative_evidence(
            aggregation_input=aggregation_input,
            sidecars_by_view_id={"view-1": sidecar},
            replay_config={
                "schemaVersion": 1,
                "methodId": "behind-suppressed/experimental-reference-v1",
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            aggregation_policy=default_reference_aggregation_policy(),
        )

        self.assertEqual(replay["selectedStableGaussianIds"], [10])
        self.assertEqual(replay["rejectedStableGaussianIds"], [])
        self.assertEqual(replay["uncertainStableGaussianIds"], [11, 12, 13])
        self.assertEqual(
            replay["sourceBaselineArtifactDigests"], [baseline["artifactDigest"]]
        )
        self.assertEqual(replay["sourceSidecarDigests"], [sidecar["artifactDigest"]])
        self.assertEqual(
            replay["artifactKind"],
            "depth-classified-negative-evidence-candidate-replay/experimental-reference",
        )
        self.assertRegex(replay["replayDigest"], r"^sha256:[0-9a-f]{64}$")


class DepthClassifiedNegativeEvidenceConfigurationTests(unittest.TestCase):
    def test_loads_the_finite_sealed_experiment_configuration(self) -> None:
        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "ai-select-v1"
            / "depth-classified-negative-evidence-v1.json"
        )

        configuration = load_depth_classified_negative_evidence_configuration(fixture)

        self.assertEqual(
            configuration["experimentId"],
            "v2ax-depth-classified-negative-evidence/experimental-reference-v1",
        )
        self.assertEqual(configuration["status"], "sealed-configuration")
        self.assertEqual(len(configuration["relationConfigs"]), 1)
        self.assertEqual(len(configuration["variantMethods"]), 3)
        self.assertEqual(
            configuration["recommendationChoices"],
            ["retain-experimental", "propose-promotion-issue", "delete"],
        )
        self.assertNotIn("groundTruthPath", json.dumps(configuration))
        self.assertRegex(configuration["configurationDigest"], r"^sha256:[0-9a-f]{64}$")
        report = (
            Path(__file__).resolve().parents[1]
            / "benchmarks/depth-classified-negative-evidence-v1-report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("**Recommendation: `retain-experimental`.**", report)
        self.assertIn("**Trial validity: `invalid-incomplete-for-promotion`.**", report)
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts/benchmark_depth_classified_negative_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("backend._", script)


class DepthClassifiedNegativeEvidenceRunRecordTests(unittest.TestCase):
    def test_seals_baseline_first_and_scores_variants_without_rescuing_it(
        self,
    ) -> None:
        identity = create_experiment_input_identity(
            scene_snapshot_digest=digest("a"),
            camera_bindings_digest=digest("b"),
            stable_masks_digest=digest("c"),
            working_sets_digest=digest("d"),
            renderer_runtime_digest=digest("e"),
            deterministic_seed="seed-1",
        )
        runtime_source = locked_runtime_source()
        baseline = create_baseline_run_record(
            input_identity=identity,
            baseline_artifact_digests=[digest("3")],
            candidate_replay={
                "selectedStableGaussianIds": [1, 4],
                "rejectedStableGaussianIds": [2, 3],
                "uncertainStableGaussianIds": [],
                "candidateInputStableGaussianIds": [1, 4],
                "replayDigest": digest("4"),
            },
            runtime_source=runtime_source,
            timing_and_vram={"latencyMilliseconds": 2.0, "peakVramBytes": 4096},
            buffer_writes={
                "productionNegativeMass": 10,
                "classifiedSidecar": 0,
                "total": 10,
            },
        )
        variant = create_variant_run_record(
            input_identity=identity,
            replay_config={
                "schemaVersion": 1,
                "methodId": "behind-suppressed/experimental-reference-v1",
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            sidecar_digests=[digest("5")],
            candidate_replay={
                "selectedStableGaussianIds": [1, 2],
                "rejectedStableGaussianIds": [3, 4],
                "uncertainStableGaussianIds": [],
                "candidateInputStableGaussianIds": [1, 2],
                "replayDigest": digest("6"),
            },
            runtime_source=runtime_source,
            timing_and_vram={"latencyMilliseconds": 3.0, "peakVramBytes": 4608},
            buffer_writes={
                "productionNegativeMass": 10,
                "front": 2,
                "near": 3,
                "behind": 4,
                "invalidDepth": 1,
                "classifiedSidecar": 10,
                "total": 20,
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            persist_baseline_run_record(prediction, baseline)
            persist_variant_run_record(prediction, variant, ordinal=0)
            seal = seal_depth_classified_negative_evidence_prediction(
                prediction,
                expected_variant_method_ids=[
                    "behind-suppressed/experimental-reference-v1"
                ],
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2],
                        "rejectedStableGaussianIds": [3, 4],
                        "ambiguousStableGaussianIds": [],
                        "distractorStableGaussianIds": [4],
                        "thinOrEdgeStableGaussianIds": [2],
                    }
                ),
                encoding="utf-8",
            )

            scores = score_depth_classified_negative_evidence_prediction(
                prediction,
                ground_truth_path=ground_truth,
                output_path=root / "scores.json",
            )

            manifest = json.loads(
                (prediction / "prediction-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["records"][0]["kind"], "baseline")
            self.assertEqual(manifest["records"][1]["kind"], "variant")
            self.assertEqual(seal["status"], "sealed-before-ground-truth")
            self.assertFalse(
                any("ground" in path.name.lower() for path in prediction.rglob("*"))
            )
            self.assertFalse(scores["baselineGatePassed"])
            self.assertEqual(scores["baselineResult"], "failed")
            self.assertTrue(scores["methods"][1]["qualityGatePassed"])
            self.assertEqual(scores["methods"][0]["bufferWrites"]["total"], 10)
            self.assertEqual(scores["methods"][1]["bufferWrites"]["total"], 20)
            self.assertTrue(scores["variantCannotAlterBaselineResult"])
            self.assertEqual(
                scores["methods"][0]["metrics"]["thinOrEdgeRetention"], 0.0
            )
            self.assertEqual(
                scores["methods"][1]["metrics"]["thinOrEdgeRetention"], 1.0
            )
            self.assertTrue((root / "scores.json").is_file())

    def test_variant_failure_cannot_modify_the_sealed_baseline(self) -> None:
        identity = create_experiment_input_identity(
            scene_snapshot_digest=digest("a"),
            camera_bindings_digest=digest("b"),
            stable_masks_digest=digest("c"),
            working_sets_digest=digest("d"),
            renderer_runtime_digest=digest("e"),
            deterministic_seed="seed-1",
        )
        baseline = create_baseline_run_record(
            input_identity=identity,
            baseline_artifact_digests=[digest("3")],
            candidate_replay={
                "selectedStableGaussianIds": [1],
                "rejectedStableGaussianIds": [2],
                "uncertainStableGaussianIds": [],
                "candidateInputStableGaussianIds": [1],
                "replayDigest": digest("4"),
            },
            runtime_source=locked_runtime_source(),
            timing_and_vram={"latencyMilliseconds": 2.0, "peakVramBytes": 4096},
            buffer_writes={
                "productionNegativeMass": 1,
                "classifiedSidecar": 0,
                "total": 1,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            prediction = Path(directory) / "prediction"
            baseline_path = persist_baseline_run_record(prediction, baseline)
            baseline_bytes = baseline_path.read_bytes()
            invalid_variant = {"recordKind": "invalid"}

            with self.assertRaises(DepthClassifiedNegativeEvidenceBenchmarkError):
                persist_variant_run_record(prediction, invalid_variant, ordinal=0)

            failure_path = persist_sidecar_failure(
                prediction,
                error=MemoryError("injected sidecar OOM"),
                baseline_record_digest=baseline["recordDigest"],
            )

            self.assertEqual(baseline_path.read_bytes(), baseline_bytes)
            self.assertTrue((prediction / "baseline-seal.json").is_file())
            self.assertFalse((prediction / "variant-000-run-record.json").exists())
            self.assertFalse((prediction / "prediction-seal.json").exists())
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "baseline-sealed-sidecar-failed")
            self.assertEqual(failure["baselineRecordDigest"], baseline["recordDigest"])

    def test_tampered_variant_is_rejected_before_ground_truth_is_opened(self) -> None:
        identity = create_experiment_input_identity(
            scene_snapshot_digest=digest("a"),
            camera_bindings_digest=digest("b"),
            stable_masks_digest=digest("c"),
            working_sets_digest=digest("d"),
            renderer_runtime_digest=digest("e"),
            deterministic_seed="seed-1",
        )
        runtime = locked_runtime_source()
        candidate = {
            "selectedStableGaussianIds": [1],
            "rejectedStableGaussianIds": [2],
            "uncertainStableGaussianIds": [],
            "candidateInputStableGaussianIds": [1],
            "replayDigest": digest("4"),
        }
        baseline = create_baseline_run_record(
            input_identity=identity,
            baseline_artifact_digests=[digest("3")],
            candidate_replay=candidate,
            runtime_source=runtime,
            timing_and_vram={"latencyMilliseconds": 2.0, "peakVramBytes": 4096},
            buffer_writes={
                "productionNegativeMass": 1,
                "classifiedSidecar": 0,
                "total": 1,
            },
        )
        variant = create_variant_run_record(
            input_identity=identity,
            replay_config={
                "schemaVersion": 1,
                "methodId": "behind-suppressed/experimental-reference-v1",
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            sidecar_digests=[digest("5")],
            candidate_replay=candidate,
            runtime_source=runtime,
            timing_and_vram={"latencyMilliseconds": 3.0, "peakVramBytes": 4608},
            buffer_writes={
                "productionNegativeMass": 1,
                "front": 1,
                "near": 0,
                "behind": 0,
                "invalidDepth": 0,
                "classifiedSidecar": 1,
                "total": 2,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            persist_baseline_run_record(prediction, baseline)
            variant_path = persist_variant_run_record(prediction, variant, ordinal=0)
            seal_depth_classified_negative_evidence_prediction(
                prediction,
                expected_variant_method_ids=[
                    "behind-suppressed/experimental-reference-v1"
                ],
            )
            variant_path.write_text("{}", encoding="utf-8")
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("not-json", encoding="utf-8")

            with self.assertRaisesRegex(
                DepthClassifiedNegativeEvidenceBenchmarkError,
                "hash does not match",
            ):
                score_depth_classified_negative_evidence_prediction(
                    prediction,
                    ground_truth_path=ground_truth,
                    output_path=root / "scores.json",
                )


class DepthClassifiedNegativeEvidenceProductionBoundaryTests(unittest.TestCase):
    def test_classified_channels_are_absent_from_production_schemas_and_readiness(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        production_sources = (
            repository_root
            / "selection-service-companion/src/selection_service_companion/gaussian_evidence_contract.py",
            repository_root
            / "selection-service-companion/src/selection_service_companion/state.py",
            repository_root
            / "selection-service-companion/src/selection_service_companion/server.py",
            repository_root / "src/ai-select/gaussian-evidence-contract.ts",
            repository_root / "src/ai-select/candidate-publication.ts",
            repository_root / "src/selection-service-readiness.ts",
        )
        forbidden = (
            "frontNegativeMass",
            "nearNegativeMass",
            "behindNegativeMass",
            "invalidDepthNegativeMass",
            "depth-classified-negative-evidence",
        )

        for path in production_sources:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                for token in forbidden:
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
