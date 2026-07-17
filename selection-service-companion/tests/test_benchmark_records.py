from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from selection_service_companion.benchmark import (
    REQUIRED_PREDICTION_ARTIFACTS,
    PocRunRecordError,
    score_prediction,
    seal_prediction,
)
from selection_service_companion.controlled_overlap_benchmark import (
    _preview_render_policy,
    build_controlled_overlap_snapshot,
    seal_preview_prediction,
)


class PocRunRecordTests(unittest.TestCase):
    def complete_bindings(self, **overrides: object) -> dict[str, object]:
        bindings: dict[str, object] = {
            "trialId": "controlled-overlap-seed-1",
            "protocolVersion": "1",
            "deterministicSeed": "controlled-seed-1",
            "terminalState": "complete",
            "requestId": "request-1",
            "sessionId": "session-1",
            "targetSplatId": "controlled-overlap",
            "sceneId": "controlled-overlap",
            "sceneVersion": "sha256:scene",
            "operation": "New",
            "correctionRound": 0,
            "promptLogRevision": 1,
            "frameSetVersion": "frames-final",
            "renderConfigVersion": "render-v1",
            "modelManifestDigest": "sha256:model",
        }
        bindings.update(overrides)
        return bindings

    def complete_artifacts(
        self,
        root: Path,
        *,
        render_policy: dict[str, object] | None = None,
        evidence_snapshot_policy: dict[str, object] | None = None,
    ) -> dict[str, Path]:
        if render_policy is None:
            render_policy = {
                "renderConfigVersion": "render-v1",
                "evidencePolicy": {"renderConfigVersion": "render-v1"},
            }
        if evidence_snapshot_policy is None:
            evidence_snapshot_policy = {"renderConfigVersion": "render-v1"}
        inputs = root / "inputs"
        inputs.mkdir()
        artifacts: dict[str, Path] = {}
        for name in REQUIRED_PREDICTION_ARTIFACTS:
            artifact = inputs / f"{name}.json"
            value: object = {"artifact": name}
            if name == "candidateObjectSelection":
                value = {
                    "selectedStableGaussianIds": [1, 2, 4],
                    "rejectedStableGaussianIds": [3, 5],
                    "uncertainStableGaussianIds": [],
                }
            elif name == "sceneSnapshot":
                value = {
                    "sceneId": "controlled-overlap",
                    "sceneVersion": "sha256:scene",
                }
            elif name == "frameSet":
                value = {"frameSetVersion": "frames-final"}
            elif name == "maskSet":
                value = {
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "promptLogRevision": 1,
                    "frameSetVersion": "frames-final",
                    "modelManifestDigest": "sha256:model",
                }
            elif name == "renderPolicy":
                value = render_policy
            elif name == "evidenceSnapshot":
                value = {
                    **{
                        name: value
                        for name, value in self.complete_bindings().items()
                        if name not in {"trialId", "terminalState"}
                    },
                    "policy": evidence_snapshot_policy,
                }
            elif name == "modelManifest":
                value = {"digest": "sha256:model"}
            if isinstance(value, dict):
                value = {**value, "recordBindings": self.complete_bindings()}
            artifact.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            artifacts[name] = artifact
        lock_digest = "sha256:" + hashlib.sha256(
            artifacts["dependencyLock"].read_bytes()
        ).hexdigest()
        runtime = json.loads(artifacts["runtimeManifest"].read_text(encoding="utf-8"))
        runtime["release"] = {"lockDigest": lock_digest}
        artifacts["runtimeManifest"].write_text(
            json.dumps(runtime, sort_keys=True), encoding="utf-8"
        )
        return artifacts

    def test_seals_a_complete_prediction_before_ground_truth_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)

            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )

            manifest = json.loads(record.manifest_path.read_text(encoding="utf-8"))
            seal = json.loads(record.seal_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "prediction-complete")
            self.assertEqual(
                set(manifest["artifacts"]), set(REQUIRED_PREDICTION_ARTIFACTS)
            )
            self.assertEqual(seal["status"], "sealed-before-ground-truth")
            self.assertEqual(seal["manifestSha256"], record.manifest_sha256)
            self.assertFalse(
                any(
                    "ground" in path.name.lower()
                    for path in record.directory.rglob("*")
                )
            )

    def test_refuses_to_seal_a_prediction_with_ground_truth_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "ground-truth.json"
            artifact.write_text("{}", encoding="utf-8")
            artifacts = {name: artifact for name in REQUIRED_PREDICTION_ARTIFACTS}

            with self.assertRaisesRegex(PocRunRecordError, "Ground Truth"):
                seal_prediction(
                    root / "trial-1",
                    artifacts=artifacts,
                    bindings=self.complete_bindings(trialId="trial-1"),
                )

    def test_refuses_to_seal_a_complete_prediction_without_identity_bindings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = self.complete_bindings()
            del bindings["sceneVersion"]

            with self.assertRaisesRegex(PocRunRecordError, "sceneVersion"):
                seal_prediction(
                    root / "trial-1",
                    artifacts=self.complete_artifacts(root),
                    bindings=bindings,
                )

    def test_seals_but_does_not_score_a_terminally_failed_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "failed-trial",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(
                    trialId="failed-trial",
                    deterministicSeed="seed-1",
                    terminalState="rendererMassMismatch",
                ),
            )
            manifest = json.loads(record.manifest_path.read_text(encoding="utf-8"))
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("{}", encoding="utf-8")

            self.assertEqual(manifest["status"], "prediction-failed")
            with self.assertRaisesRegex(PocRunRecordError, "not complete"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_scores_only_after_verifying_the_sealed_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "controlled-overlap-ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 3],
                        "rejectedStableGaussianIds": [4, 5],
                        "ambiguousStableGaussianIds": [],
                        "rearSurfaceStableGaussianIds": [2, 3],
                        "distractorStableGaussianIds": [4, 5],
                    }
                ),
                encoding="utf-8",
            )

            result = score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
            )

            self.assertEqual(result["metrics"]["intersectionOverUnion"], 0.5)
            self.assertEqual(result["metrics"]["precision"], 2 / 3)
            self.assertEqual(result["metrics"]["recall"], 2 / 3)
            self.assertEqual(result["metrics"]["rearSurfaceRecall"], 0.5)
            self.assertEqual(result["metrics"]["selectedDistractorCount"], 1)
            self.assertFalse(result["controlledOverlapGatePassed"])
            self.assertTrue((root / "score.json").is_file())

    def test_invalidates_a_trial_if_a_sealed_prediction_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(
                    trialId="trial-1", deterministicSeed="seed-1"
                ),
            )
            candidate = record.directory / "artifacts" / "candidateObjectSelection.json"
            candidate.write_text("{}", encoding="utf-8")
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1],
                        "rejectedStableGaussianIds": [],
                        "ambiguousStableGaussianIds": [],
                        "rearSurfaceStableGaussianIds": [1],
                        "distractorStableGaussianIds": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PocRunRecordError, "hash mismatch"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_invalidates_a_trial_if_identity_does_not_match_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(sceneVersion="sha256:other-scene"),
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(PocRunRecordError, "sceneVersion"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_invalidates_a_trial_if_the_sealed_evidence_policy_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(
                    root,
                    render_policy={
                        "renderConfigVersion": "render-v1",
                        "evidencePolicy": {"renderConfigVersion": "render-v0"},
                    },
                ),
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(PocRunRecordError, "evidencePolicy"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_invalidates_a_trial_if_the_evidence_snapshot_policy_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(
                    root,
                    evidence_snapshot_policy={"renderConfigVersion": "render-v0"},
                ),
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(PocRunRecordError, "Evidence Snapshot policy"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_refuses_to_seal_a_failed_trial_without_evidence_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(PocRunRecordError, "evidencePolicy"):
                seal_prediction(
                    root / "failed-trial",
                    artifacts=self.complete_artifacts(
                        root,
                        render_policy={"renderConfigVersion": "render-v1"},
                    ),
                    bindings=self.complete_bindings(
                        trialId="failed-trial",
                        terminalState="rendererMassMismatch",
                    ),
                )

    def test_refuses_a_non_string_failed_trial_render_config_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(PocRunRecordError, "renderConfigVersion"):
                seal_prediction(
                    root / "failed-trial",
                    artifacts=self.complete_artifacts(
                        root,
                        render_policy={
                            "renderConfigVersion": 1,
                            "evidencePolicy": {"renderConfigVersion": 1},
                        },
                    ),
                    bindings=self.complete_bindings(
                        trialId="failed-trial",
                        terminalState="rendererMassMismatch",
                        renderConfigVersion=1,
                    ),
                )

    def test_binds_the_sealed_render_policy_to_the_render_config_version(self) -> None:
        policy = _preview_render_policy("supersplat-effective-rgb-v1")

        self.assertEqual(policy["renderConfigVersion"], "supersplat-effective-rgb-v1")
        self.assertEqual(policy["generatedViewResolutionBaseline"], 1008)
        self.assertEqual(
            policy["contributorReconciliationPolicy"],
            "gsplat-boundary-contributor-reconciliation/v2",
        )
        evidence_policy = policy["evidencePolicy"]
        self.assertIsInstance(evidence_policy, dict)
        self.assertEqual(
            evidence_policy["renderConfigVersion"],
            "supersplat-effective-rgb-v1",
        )

    def test_refuses_to_seal_a_render_policy_without_a_render_config_version(
        self,
    ) -> None:
        with self.assertRaisesRegex(PocRunRecordError, "render config version"):
            _preview_render_policy(None)

    def test_builds_a_supported_snapshot_from_the_exact_controlled_overlap_ply(
        self,
    ) -> None:
        fixture = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "benchmarks"
            / "fixtures"
            / "controlled-overlap"
            / "controlled_front_back_overlap.ply"
        )

        snapshot = build_controlled_overlap_snapshot(fixture)

        self.assertEqual(snapshot["protocolVersion"], "1")
        self.assertEqual(snapshot["gaussianCount"], 16384)
        self.assertEqual(snapshot["gaussians"][0]["stableId"], 0)
        self.assertEqual(snapshot["gaussians"][-1]["stableId"], 16383)
        self.assertEqual(snapshot["gaussians"][0]["rotation"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(
            snapshot["renderConfiguration"]["rasterizer"],
            "playcanvas-gsplat-classic",
        )

    def test_rejects_a_modified_controlled_overlap_fixture(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "benchmarks"
            / "fixtures"
            / "controlled-overlap"
            / "controlled_front_back_overlap.ply"
        )
        with tempfile.TemporaryDirectory() as directory:
            modified = Path(directory) / fixture.name
            payload = bytearray(fixture.read_bytes())
            payload[-1] ^= 1
            modified.write_bytes(payload)

            with self.assertRaisesRegex(PocRunRecordError, "frozen fixture digest"):
                build_controlled_overlap_snapshot(modified)

    def test_seals_a_preview_with_internal_generated_view_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_file = root / "uv.lock"
            lock_file.write_text("locked", encoding="utf-8")
            publication = SimpleNamespace(
                bindings={"requestId": "request-1", "frameSetVersion": "frames-final"},
                frame_set={"frameSetVersion": "frames-final"},
                mask_set={
                    "status": "complete",
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "promptLogRevision": 1,
                    "frameSetVersion": "frames-final",
                    "modelManifestDigest": "sha256:model",
                },
                evidence_snapshot={
                    **{
                        name: value
                        for name, value in self.complete_bindings().items()
                        if name not in {"trialId", "terminalState"}
                    },
                    "records": [
                        {"stableId": 1, "classification": "selected"},
                        {"stableId": 2, "classification": "rejected"},
                        {"stableId": 3, "classification": "uncertain"},
                    ]
                },
                coverage_report={
                    "status": "complete",
                    "qualityDiagnostics": {"attempts": [{"viewId": "generated-00"}]},
                },
            )

            record = seal_preview_prediction(
                root / "trial",
                publication=publication,
                scene_snapshot={
                    "sceneId": "controlled-overlap",
                    "sceneVersion": "sha256:scene",
                },
                prompt_log=[{"operation": "New"}],
                model_manifest={"digest": "sha256:model"},
                runtime_manifest={"gpu": "locked-gpu"},
                dependency_lock=lock_file,
                render_policy={"renderConfigVersion": "supersplat-effective-rgb-v1"},
                correction_outcomes=[{"round": 0, "terminalState": "complete"}],
                timing_and_vram={"previewSeconds": 1.25, "peakVramBytes": 1024},
                internal_diagnostics={
                    "oomRetries": [],
                    "attempts": [{"viewId": "generated-00"}],
                },
                bindings=self.complete_bindings(),
            )

            candidate = json.loads(
                (
                    record.directory / "artifacts" / "candidateObjectSelection.json"
                ).read_text(encoding="utf-8")
            )
            diagnostics = json.loads(
                (record.directory / "artifacts" / "internalDiagnostics.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(candidate["selectedStableGaussianIds"], [1])
            self.assertEqual(candidate["rejectedStableGaussianIds"], [2])
            self.assertEqual(candidate["uncertainStableGaussianIds"], [3])
            self.assertEqual(diagnostics["attempts"][0]["viewId"], "generated-00")


if __name__ == "__main__":
    unittest.main()
