from __future__ import annotations

import json
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
    build_controlled_overlap_snapshot,
    seal_preview_prediction,
)


class PocRunRecordTests(unittest.TestCase):
    def complete_artifacts(self, root: Path) -> dict[str, Path]:
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
            artifact.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            artifacts[name] = artifact
        return artifacts

    def test_seals_a_complete_prediction_before_ground_truth_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)

            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings={
                    "trialId": "controlled-overlap-seed-1",
                    "protocolVersion": "1",
                    "deterministicSeed": "controlled-seed-1",
                    "terminalState": "complete",
                },
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
                    bindings={
                        "trialId": "trial-1",
                        "protocolVersion": "1",
                        "deterministicSeed": "seed-1",
                        "terminalState": "complete",
                    },
                )

    def test_seals_but_does_not_score_a_terminally_failed_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "failed-trial",
                artifacts=self.complete_artifacts(root),
                bindings={
                    "trialId": "failed-trial",
                    "protocolVersion": "1",
                    "deterministicSeed": "seed-1",
                    "terminalState": "rendererMassMismatch",
                },
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
                bindings={
                    "trialId": "controlled-overlap-seed-1",
                    "protocolVersion": "1",
                    "deterministicSeed": "controlled-seed-1",
                    "terminalState": "complete",
                },
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
                bindings={
                    "trialId": "trial-1",
                    "protocolVersion": "1",
                    "deterministicSeed": "seed-1",
                    "terminalState": "complete",
                },
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

    def test_seals_a_preview_with_internal_generated_view_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_file = root / "uv.lock"
            lock_file.write_text("locked", encoding="utf-8")
            publication = SimpleNamespace(
                bindings={"requestId": "request-1", "frameSetVersion": "frames-final"},
                frame_set={"frameSetVersion": "frames-final"},
                mask_set={"status": "complete"},
                evidence_snapshot={
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
                scene_snapshot={"sceneId": "controlled-overlap"},
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
                bindings={
                    "trialId": "controlled-overlap-seed-1",
                    "protocolVersion": "1",
                    "deterministicSeed": "controlled-seed-1",
                    "terminalState": "complete",
                },
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
