from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from selection_service_companion.depth_classified_negative_evidence_experiment import (
    ProjectedDepthRowsRecord,
    build_depth_classified_negative_evidence_sidecar,
    exact_projected_depth_rows_equal,
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
from selection_service_companion.depth_moment_qualification import (
    DepthMomentExecutionEnvelope,
    DepthMomentInternalCapability,
)
from selection_service_companion.depth_moment_readout import (
    DepthMomentReadoutRecord,
    DepthMomentTelemetry,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import DepthMomentValidityPolicy
from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.depth_classified_negative_evidence_benchmark import (
    DepthClassifiedNegativeEvidenceBenchmarkError,
    create_baseline_run_record,
    create_experiment_input_identity,
    create_variant_run_record,
    load_depth_classified_negative_evidence_configuration,
    load_depth_classified_negative_evidence_prediction_input,
    persist_baseline_run_record,
    persist_sidecar_failure,
    persist_variant_run_record,
    score_depth_classified_negative_evidence_prediction,
    seal_depth_classified_negative_evidence_prediction,
)


def digest(character: str) -> str:
    return "sha256:" + (character * 64)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def file_payload_digest(value: object, field: str) -> dict[str, object]:
    payload = dict(value)
    payload[field] = canonical_json_digest(payload)
    return payload


def prediction_input_manifest() -> dict[str, object]:
    return file_payload_digest(
        {
            "schemaVersion": 1,
            "manifestKind": "test-prediction-input",
        },
        "manifestDigest",
    )


def experiment_identity(manifest: object) -> dict[str, object]:
    manifest_sha = "sha256:" + hashlib.sha256(json_bytes(manifest)).hexdigest()
    return create_experiment_input_identity(
        scene_snapshot_digest=digest("a"),
        camera_bindings_digest=digest("b"),
        stable_masks_digest=digest("c"),
        working_sets_digest=digest("d"),
        renderer_runtime_digest=digest("e"),
        prediction_input_manifest_sha256=manifest_sha,
        prediction_input_manifest_digest=manifest["manifestDigest"],
        deterministic_seed="seed-1",
    )


def measured_stage(stage_id: str, latency: float, peak: int | None) -> dict[str, object]:
    return {
        "stageId": stage_id,
        "costKind": "measured-stage",
        "measurementComposition": "median-of-whole-stage-runs",
        "latencyMilliseconds": latency,
        "startVramBytes": None if peak is None else 128,
        "peakVramBytes": peak,
        "endVramBytes": None if peak is None else 192,
        "retainedInputs": [f"{stage_id}Input"],
        "retainedOutputsThroughReturn": [f"{stage_id}Output"],
        "bufferWrites": {"testElements": 1, "total": 1},
    }


def cost_measurement(*, variant: bool) -> dict[str, object]:
    stage_ids = ["productionBaseline", "baselineCandidateReplay"]
    total_id = "productionBaselineTotal"
    if variant:
        stage_ids.extend(
            [
                "sharedCwedReadoutAcquisition",
                "referenceContributorAndClassificationSidecar",
                "variantCandidateReplay",
            ]
        )
        total_id = "shadowExperimentTotal"
    components = [
        measured_stage(stage_id, float(index + 1), 4096 + index * 256)
        for index, stage_id in enumerate(stage_ids)
    ]
    total_latency = sum(stage["latencyMilliseconds"] for stage in components)
    total_writes = sum(stage["bufferWrites"]["total"] for stage in components)
    return {
        "measurementBoundary": {
            "policyId": "audited-component-cost/experimental-reference-v1",
            "warmupRuns": 1,
            "measuredRuns": 3,
            "latencyStatistic": "median",
            "peakVramStatistic": "maximum",
            "peakResetOwner": "locked-renderer-call",
            "bufferWriteMetric": "logical-output-channel-elements",
            "totalComposition": "derived-sum-of-component-medians/max-of-component-peaks",
        },
        "stages": [
            *components,
            {
                "stageId": total_id,
                "costKind": "derived-total",
                "measurementComposition": "sum-of-components/max-of-components",
                "latencyMilliseconds": total_latency,
                "startVramBytes": None,
                "peakVramBytes": max(stage["peakVramBytes"] for stage in components),
                "endVramBytes": None,
                "retainedInputs": [],
                "retainedOutputsThroughReturn": [],
                "bufferWrites": {
                    "componentStageWrites": total_writes,
                    "total": total_writes,
                },
            },
        ],
    }


def classified_sidecar(view_id: str = "view-1") -> dict[str, object]:
    return file_payload_digest(
        {
            "schemaVersion": 1,
            "artifactKind": "depth-classified-negative-evidence/experimental-reference",
            "relationConfig": {
                "schemaVersion": 1,
                "relationId": "front-near-behind/cwed-variance-v1",
                "absoluteBand": 0.25,
                "relativeCwedBand": 0.0,
                "standardDeviationMultiplier": 0.0,
            },
            "baselineArtifactDigest": digest("3"),
            "acceptedContributionSequenceDigest": digest("4"),
            "exactProjectedDepthRowsDigest": digest("5"),
            "depthMomentReadoutDigest": digest("6"),
            "depthMomentIdentity": {"viewId": view_id},
            "stableGaussianIds": [1, 2],
            "frontNegativeMass": [0.0, 0.0],
            "nearNegativeMass": [0.0, 0.0],
            "behindNegativeMass": [0.0, 0.0],
            "invalidDepthNegativeMass": [0.0, 0.0],
            "baselineMassConservation": {"passed": True},
            "classificationContributionCounts": {
                "frontNegativeMass": 0,
                "nearNegativeMass": 0,
                "behindNegativeMass": 0,
                "invalidDepthNegativeMass": 0,
                "total": 0,
            },
        },
        "artifactDigest",
    )


def variant_replay_artifact(
    *,
    method_id: str,
    selected: list[int],
    rejected: list[int],
    baseline_artifact_digests: list[str],
    sidecar_digests: list[str],
) -> dict[str, object]:
    return file_payload_digest(
        {
            "schemaVersion": 1,
            "artifactKind": "depth-classified-negative-evidence-candidate-replay/experimental-reference",
            "method": {
                "schemaVersion": 1,
                "methodId": method_id,
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            "relationConfig": {
                "schemaVersion": 1,
                "relationId": "front-near-behind/cwed-variance-v1",
                "absoluteBand": 0.25,
                "relativeCwedBand": 0.0,
                "standardDeviationMultiplier": 0.0,
            },
            "aggregationPolicy": {"policyId": "test-aggregation-policy"},
            "aggregationResultDigest": digest("7"),
            "selectedStableGaussianIds": selected,
            "rejectedStableGaussianIds": rejected,
            "uncertainStableGaussianIds": [],
            "candidateInputStableGaussianIds": selected,
            "sourceBaselineArtifactDigests": baseline_artifact_digests,
            "sourceSidecarDigests": sidecar_digests,
        },
        "replayDigest",
    )


def persist_prediction_artifacts(
    prediction: Path,
    *,
    manifest: object,
    baseline_candidate: object,
    baseline_artifact_digests: list[str],
    sidecar: object,
    variant_replay: object,
) -> None:
    (prediction / "sidecars").mkdir(parents=True, exist_ok=True)
    (prediction / "candidate-replays").mkdir(parents=True, exist_ok=True)
    (prediction / "prediction-input-manifest.json").write_bytes(json_bytes(manifest))
    (prediction / "baseline-artifacts.json").write_bytes(
        json_bytes(
            {
                "schemaVersion": 1,
                "methodId": "production-single-negative-mass/baseline-v1",
                "views": [
                    {
                        "currentInput": {"view": {"viewId": "view-1"}},
                        "artifact": {
                            "artifactDigest": baseline_artifact_digests[0]
                        },
                    }
                ],
                "candidateReplay": baseline_candidate,
            }
        )
    )
    (prediction / "sidecars/view-1.json").write_bytes(json_bytes(sidecar))
    (prediction / "candidate-replays/variant-000.json").write_bytes(
        json_bytes(variant_replay)
    )


def seal_test_prediction(prediction: Path) -> dict[str, object]:
    manifest = prediction_input_manifest()
    identity = experiment_identity(manifest)
    runtime = locked_runtime_source()
    baseline_digests = [digest("3")]
    baseline_candidate = {
        "selectedStableGaussianIds": [1],
        "rejectedStableGaussianIds": [2],
        "uncertainStableGaussianIds": [],
        "candidateInputStableGaussianIds": [1],
        "replayDigest": digest("4"),
    }
    sidecar = classified_sidecar()
    method_id = "behind-suppressed/experimental-reference-v1"
    replay = variant_replay_artifact(
        method_id=method_id,
        selected=[1],
        rejected=[2],
        baseline_artifact_digests=baseline_digests,
        sidecar_digests=[sidecar["artifactDigest"]],
    )
    baseline = create_baseline_run_record(
        input_identity=identity,
        baseline_artifact_digests=baseline_digests,
        candidate_replay=baseline_candidate,
        runtime_source=runtime,
        cost_measurement=cost_measurement(variant=False),
    )
    variant = create_variant_run_record(
        input_identity=identity,
        replay_config={
            "schemaVersion": 1,
            "methodId": method_id,
            "frontCoefficient": 1.0,
            "nearCoefficient": 1.0,
            "behindCoefficient": 0.0,
            "invalidDepthCoefficient": 1.0,
        },
        sidecar_digests=[sidecar["artifactDigest"]],
        candidate_replay=replay,
        runtime_source=runtime,
        cost_measurement=cost_measurement(variant=True),
    )
    persist_baseline_run_record(prediction, baseline)
    persist_variant_run_record(prediction, variant, ordinal=0)
    persist_prediction_artifacts(
        prediction,
        manifest=manifest,
        baseline_candidate=baseline_candidate,
        baseline_artifact_digests=baseline_digests,
        sidecar=sidecar,
        variant_replay=replay,
    )
    seal_depth_classified_negative_evidence_prediction(
        prediction,
        expected_variant_method_ids=[method_id],
    )
    return {
        "manifest": manifest,
        "baseline": baseline,
        "variant": variant,
        "sidecar": sidecar,
        "replay": replay,
    }


def locked_runtime_source() -> dict[str, object]:
    return {
        "directEvidenceAbiVersion": "supersimplat-direct-evidence-abi/v3",
        "directEvidenceSourceRevision": digest("1"),
        "directEvidenceRuntimeBuildId": digest("2"),
        "rendererRuntimeDigest": digest("e"),
        "gpuName": "Locked Test GPU",
        "computeCapability": "8.9",
        "benchmarkImplementationDigest": digest("8"),
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
    capability = DepthMomentInternalCapability(
        status="ready",
        reason="test",
        qualification_id="test-depth-moment-capability",
        qualification_digest=digest("9"),
        policy=policy,
        envelope=DepthMomentExecutionEnvelope(
            compute_capabilities=("8.9",),
            max_width=4,
            max_height=1,
            max_pixels=4,
            max_render_gaussian_count=4,
            max_evidence_gaussian_count=4,
            max_intersection_count=16,
            max_concurrent_consumers=1,
        ),
        direct_evidence_abi_version="supersimplat-direct-evidence-abi/v3",
        direct_evidence_source_revision=digest("2"),
        direct_evidence_runtime_build_id=digest("1"),
    )
    identity = create_depth_moment_readout_identity(
        admission,
        render_stable_ids_by_projected_row=(10, 11, 12, 13),
        capability=capability,
        width=4,
        height=1,
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
            projected_depth_rows=ProjectedDepthRowsRecord(
                rows=torch.tensor([1.0, 2.0, 3.0, 2.0], dtype=torch.float32),
                stable_ids_by_projected_row=(10, 11, 12, 13),
            ),
            evidence_stable_ids=(10, 11, 12, 13),
            contributor_row_ids=torch.tensor([[[0], [1], [2], [3]]], dtype=torch.int64),
            contributor_weights=torch.full((1, 4, 1), 0.5, dtype=torch.float32),
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
        self.assertEqual(sidecar["classificationContributionCounts"]["total"], 4)
        self.assertRegex(sidecar["artifactDigest"], r"^sha256:[0-9a-f]{64}$")

    def test_exact_projected_depth_row_equality_rejects_one_ulp_difference(
        self,
    ) -> None:
        import torch

        rows = torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=torch.float32)
        changed = rows.clone()
        changed[2] = torch.nextafter(
            changed[2], torch.tensor(float("inf"), dtype=torch.float32)
        )
        baseline = ProjectedDepthRowsRecord(
            rows=rows,
            stable_ids_by_projected_row=(10, 11, 12, 13),
        )
        one_ulp_different = ProjectedDepthRowsRecord(
            rows=changed,
            stable_ids_by_projected_row=(10, 11, 12, 13),
        )

        self.assertFalse(
            exact_projected_depth_rows_equal(baseline, one_ulp_different)
        )

    def test_rejects_projected_depth_rows_from_a_different_stable_id_mapping(
        self,
    ) -> None:
        import torch

        readout = depth_readout(
            torch.tensor(
                [[[1.0, 2.0, 4.01], [1.0, 2.0, 4.01], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],
                dtype=torch.float32,
            )
        )
        with self.assertRaisesRegex(
            ValueError,
            "projected-row mapping does not match",
        ):
            build_depth_classified_negative_evidence_sidecar(
                relation_config={
                    "schemaVersion": 1,
                    "relationId": "front-near-behind/cwed-variance-v1",
                    "absoluteBand": 0.25,
                    "relativeCwedBand": 0.0,
                    "standardDeviationMultiplier": 0.0,
                },
                depth_readout=readout,
                projected_depth_rows=ProjectedDepthRowsRecord(
                    rows=torch.tensor([1.0, 3.0, 2.0, 2.0], dtype=torch.float32),
                    stable_ids_by_projected_row=(11, 10, 12, 13),
                ),
                evidence_stable_ids=(10, 11, 12, 13),
                contributor_row_ids=torch.tensor(
                    [[[0], [1], [-1], [-1]]], dtype=torch.int64
                ),
                contributor_weights=torch.tensor(
                    [[[0.1], [0.9], [0.0], [0.0]]], dtype=torch.float32
                ),
                negative_pixel_weights=torch.ones(4, dtype=torch.float64),
                baseline_negative_mass=torch.tensor(
                    [0.1, 0.9, 0.0, 0.0], dtype=torch.float32
                ),
                baseline_artifact_digest=digest("3"),
                accepted_contribution_sequence_digest=digest("4"),
            )

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
            projected_depth_rows=ProjectedDepthRowsRecord(
                rows=torch.tensor([1.0, 3.0, 2.0, 2.0], dtype=torch.float32),
                stable_ids_by_projected_row=stable_ids,
            ),
            evidence_stable_ids=stable_ids,
            contributor_row_ids=torch.tensor(
                [[[0], [1], [-1], [-1]]], dtype=torch.int64
            ),
            contributor_weights=torch.tensor(
                [[[0.1], [0.9], [0.0], [0.0]]], dtype=torch.float32
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
        prediction_input = load_depth_classified_negative_evidence_prediction_input(
            fixture,
            scene_id="controlled-front-back-overlap/v2",
        )
        self.assertEqual(
            prediction_input["manifest"]["sceneSnapshot"]["format"],
            "controlled-overlap-ply/no-class-label-v1",
        )
        self.assertNotIn(
            b"benchmark_class",
            prediction_input["sceneSnapshotPath"].read_bytes()[:2048],
        )
        self.assertEqual(
            prediction_input["manifest"]["stableMasks"]["archiveKeys"],
            ["masks"],
        )
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

    def test_rejects_a_ground_truth_bearing_prediction_manifest(self) -> None:
        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "ai-select-v1"
            / "depth-classified-negative-evidence-v1.json"
        )
        source_configuration = json.loads(fixture.read_text(encoding="utf-8"))
        source_manifest_path = (
            fixture.parent
            / source_configuration["scenes"][0]["predictionInputManifest"]
        )
        manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        manifest["targetCount"] = 8192
        manifest["manifestDigest"] = canonical_json_digest(
            {key: value for key, value in manifest.items() if key != "manifestDigest"}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "prediction-input.json"
            manifest_path.write_bytes(json_bytes(manifest))
            configuration = dict(source_configuration)
            configuration["scenes"] = [
                {
                    **source_configuration["scenes"][0],
                    "predictionInputManifest": manifest_path.name,
                    "predictionInputManifestSha256": "sha256:"
                    + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                }
            ]
            configuration["configurationDigest"] = canonical_json_digest(
                {
                    key: value
                    for key, value in configuration.items()
                    if key != "configurationDigest"
                }
            )
            configuration_path = root / "configuration.json"
            configuration_path.write_bytes(json_bytes(configuration))

            with self.assertRaisesRegex(
                DepthClassifiedNegativeEvidenceBenchmarkError,
                "Ground Truth-bearing field",
            ):
                load_depth_classified_negative_evidence_prediction_input(
                    configuration_path,
                    scene_id="controlled-front-back-overlap/v2",
                )


    def test_rejects_extra_arrays_in_the_masks_only_archive(self) -> None:
        import numpy as np

        fixture = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "ai-select-v1"
            / "depth-classified-negative-evidence-v1.json"
        )
        source_configuration = json.loads(fixture.read_text(encoding="utf-8"))
        source_manifest_path = (
            fixture.parent
            / source_configuration["scenes"][0]["predictionInputManifest"]
        )
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        source_scene = fixture.parent / source_manifest["sceneSnapshot"]["path"]
        source_masks = fixture.parent / source_manifest["stableMasks"]["path"]
        with np.load(source_masks, allow_pickle=False) as archive:
            masks = archive["masks"].copy()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scene_path = root / "scene.ply"
            scene_path.write_bytes(source_scene.read_bytes())
            masks_path = root / "masks.npz"
            np.savez(masks_path, masks=masks, hidden_labels=np.zeros(1, dtype=np.uint8))
            manifest = dict(source_manifest)
            manifest["sceneSnapshot"] = {
                **source_manifest["sceneSnapshot"],
                "path": scene_path.name,
            }
            manifest["stableMasks"] = {
                **source_manifest["stableMasks"],
                "path": masks_path.name,
                "sha256": "sha256:" + hashlib.sha256(masks_path.read_bytes()).hexdigest(),
            }
            manifest["manifestDigest"] = canonical_json_digest(
                {key: value for key, value in manifest.items() if key != "manifestDigest"}
            )
            manifest_path = root / "prediction-input.json"
            manifest_path.write_bytes(json_bytes(manifest))
            configuration = dict(source_configuration)
            configuration["scenes"] = [
                {
                    **source_configuration["scenes"][0],
                    "predictionInputManifest": manifest_path.name,
                    "predictionInputManifestSha256": "sha256:"
                    + hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                }
            ]
            configuration["configurationDigest"] = canonical_json_digest(
                {
                    key: value
                    for key, value in configuration.items()
                    if key != "configurationDigest"
                }
            )
            configuration_path = root / "configuration.json"
            configuration_path.write_bytes(json_bytes(configuration))

            with self.assertRaisesRegex(
                DepthClassifiedNegativeEvidenceBenchmarkError,
                "fields other than Stable Masks",
            ):
                load_depth_classified_negative_evidence_prediction_input(
                    configuration_path,
                    scene_id="controlled-front-back-overlap/v2",
                )


class DepthClassifiedNegativeEvidenceRunRecordTests(unittest.TestCase):
    def test_seals_baseline_first_and_scores_variants_without_rescuing_it(
        self,
    ) -> None:
        manifest = prediction_input_manifest()
        identity = experiment_identity(manifest)
        runtime_source = locked_runtime_source()
        baseline_candidate = {
            "selectedStableGaussianIds": [1, 4],
            "rejectedStableGaussianIds": [2, 3],
            "uncertainStableGaussianIds": [],
            "candidateInputStableGaussianIds": [1, 4],
            "replayDigest": digest("4"),
        }
        baseline_digests = [digest("3")]
        sidecar = classified_sidecar()
        method_id = "behind-suppressed/experimental-reference-v1"
        replay = variant_replay_artifact(
            method_id=method_id,
            selected=[1, 2],
            rejected=[3, 4],
            baseline_artifact_digests=baseline_digests,
            sidecar_digests=[sidecar["artifactDigest"]],
        )
        baseline = create_baseline_run_record(
            input_identity=identity,
            baseline_artifact_digests=baseline_digests,
            candidate_replay=baseline_candidate,
            runtime_source=runtime_source,
            cost_measurement=cost_measurement(variant=False),
        )
        variant = create_variant_run_record(
            input_identity=identity,
            replay_config={
                "schemaVersion": 1,
                "methodId": method_id,
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            sidecar_digests=[sidecar["artifactDigest"]],
            candidate_replay=replay,
            runtime_source=runtime_source,
            cost_measurement=cost_measurement(variant=True),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            persist_baseline_run_record(prediction, baseline)
            persist_variant_run_record(prediction, variant, ordinal=0)
            persist_prediction_artifacts(
                prediction,
                manifest=manifest,
                baseline_candidate=baseline_candidate,
                baseline_artifact_digests=baseline_digests,
                sidecar=sidecar,
                variant_replay=replay,
            )
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
            self.assertEqual(
                scores["methods"][0]["costMeasurement"]["stages"][-1][
                    "bufferWrites"
                ]["total"],
                2,
            )
            self.assertEqual(
                scores["methods"][1]["costMeasurement"]["stages"][-1][
                    "bufferWrites"
                ]["total"],
                5,
            )
            self.assertTrue(scores["variantCannotAlterBaselineResult"])
            self.assertEqual(
                scores["methods"][0]["metrics"]["thinOrEdgeRetention"], 0.0
            )
            self.assertEqual(
                scores["methods"][1]["metrics"]["thinOrEdgeRetention"], 1.0
            )
            self.assertTrue((root / "scores.json").is_file())

    def test_variant_failure_cannot_modify_the_sealed_baseline(self) -> None:
        identity = experiment_identity(prediction_input_manifest())
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
            cost_measurement=cost_measurement(variant=False),
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
        manifest = prediction_input_manifest()
        identity = experiment_identity(manifest)
        runtime = locked_runtime_source()
        baseline_candidate = {
            "selectedStableGaussianIds": [1],
            "rejectedStableGaussianIds": [2],
            "uncertainStableGaussianIds": [],
            "candidateInputStableGaussianIds": [1],
            "replayDigest": digest("4"),
        }
        baseline_digests = [digest("3")]
        sidecar = classified_sidecar()
        method_id = "behind-suppressed/experimental-reference-v1"
        replay = variant_replay_artifact(
            method_id=method_id,
            selected=[1],
            rejected=[2],
            baseline_artifact_digests=baseline_digests,
            sidecar_digests=[sidecar["artifactDigest"]],
        )
        baseline = create_baseline_run_record(
            input_identity=identity,
            baseline_artifact_digests=baseline_digests,
            candidate_replay=baseline_candidate,
            runtime_source=runtime,
            cost_measurement=cost_measurement(variant=False),
        )
        variant = create_variant_run_record(
            input_identity=identity,
            replay_config={
                "schemaVersion": 1,
                "methodId": method_id,
                "frontCoefficient": 1.0,
                "nearCoefficient": 1.0,
                "behindCoefficient": 0.0,
                "invalidDepthCoefficient": 1.0,
            },
            sidecar_digests=[sidecar["artifactDigest"]],
            candidate_replay=replay,
            runtime_source=runtime,
            cost_measurement=cost_measurement(variant=True),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            persist_baseline_run_record(prediction, baseline)
            variant_path = persist_variant_run_record(prediction, variant, ordinal=0)
            persist_prediction_artifacts(
                prediction,
                manifest=manifest,
                baseline_candidate=baseline_candidate,
                baseline_artifact_digests=baseline_digests,
                sidecar=sidecar,
                variant_replay=replay,
            )
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

    def test_tampered_sidecar_and_replay_are_rejected_before_ground_truth(self) -> None:
        for relative in (
            "sidecars/view-1.json",
            "candidate-replays/variant-000.json",
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                prediction = root / "prediction"
                seal_test_prediction(prediction)
                (prediction / relative).write_text("{}", encoding="utf-8")
                ground_truth = root / "ground-truth.json"
                ground_truth.write_text("not-json", encoding="utf-8")

                with self.assertRaisesRegex(
                    DepthClassifiedNegativeEvidenceBenchmarkError,
                    "artifact hash does not match",
                ):
                    score_depth_classified_negative_evidence_prediction(
                        prediction,
                        ground_truth_path=ground_truth,
                        output_path=root / "scores.json",
                    )

    def test_unindexed_and_duplicate_artifacts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            seal_test_prediction(prediction)
            (prediction / "sidecars/extra.json").write_bytes(
                json_bytes(classified_sidecar("extra"))
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(
                DepthClassifiedNegativeEvidenceBenchmarkError,
                "unindexed sidecar or replay files",
            ):
                score_depth_classified_negative_evidence_prediction(
                    prediction,
                    ground_truth_path=ground_truth,
                    output_path=root / "scores.json",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prediction = root / "prediction"
            seal_test_prediction(prediction)
            manifest_path = prediction / "prediction-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][-1]["path"] = manifest["artifacts"][-2]["path"]
            manifest_path.write_bytes(json_bytes(manifest))
            seal_path = prediction / "prediction-seal.json"
            seal = json.loads(seal_path.read_text(encoding="utf-8"))
            seal["manifestSha256"] = "sha256:" + hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            seal_path.write_bytes(json_bytes(seal))
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(
                DepthClassifiedNegativeEvidenceBenchmarkError,
                "duplicate paths",
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
