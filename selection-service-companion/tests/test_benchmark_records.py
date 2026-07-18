from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from selection_service_companion.benchmark import (
    REQUIRED_PREDICTION_ARTIFACTS,
    PocRunRecordError,
    score_prediction,
    seal_prediction,
)
from selection_service_companion.controlled_overlap_benchmark import (
    _preview_render_policy,
    build_controlled_overlap_snapshot,
    load_frozen_benchmark_prompt_log,
    seal_preview_prediction,
)


FROZEN_PROMPT_LOG = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "benchmarks"
    / "fixtures"
    / "controlled-overlap"
    / "benchmark-prompt-log-v1.json"
)

# Filled by the ADR-0011 Ground Truth re-freeze; any drift turns this suite red.
EXPECTED_GROUND_TRUTH_JSON_SHA256 = (
    "740e2a6a3080a6828aa14ff5fc7e0c9741af50e89b53b2480c26ba1021027dc0"
)

# The frozen fixture's mechanical z>0 rear half before the ADR-0011 re-scope:
# the redefined observable rear plus the ambiguous enclosed cap must rebuild it.
MECHANICAL_REAR_Z_POSITIVE_COUNT = 4095


class FrozenBenchmarkPromptLogTests(unittest.TestCase):
    def write_variant(self, directory: Path, mutate) -> Path:
        document = json.loads(FROZEN_PROMPT_LOG.read_text(encoding="utf-8"))
        mutate(document)
        variant = directory / "benchmark-prompt-log-variant.json"
        variant.write_text(json.dumps(document), encoding="utf-8")
        return variant

    def test_loads_the_repository_frozen_prompt_log(self) -> None:
        entries = load_frozen_benchmark_prompt_log(FROZEN_PROMPT_LOG, image_size=1008)

        self.assertEqual(len(entries), 5)
        self.assertEqual(
            [entry["prompt"]["promptId"] for entry in entries],
            [
                "controlled-overlap-center",
                "controlled-overlap-north",
                "controlled-overlap-south",
                "controlled-overlap-west",
                "controlled-overlap-east",
            ],
        )
        self.assertEqual(
            [(entry["prompt"]["xPx"], entry["prompt"]["yPx"]) for entry in entries],
            [(504, 504), (504, 300), (504, 700), (320, 504), (688, 504)],
        )
        for entry in entries:
            self.assertEqual(entry["operation"], "New")
            self.assertEqual(entry["prompt"]["viewId"], "anchor-view")
            self.assertEqual(entry["prompt"]["polarity"], "include")

    def test_rejects_a_missing_prompt_log(self) -> None:
        with self.assertRaisesRegex(PocRunRecordError, "unavailable or invalid JSON"):
            load_frozen_benchmark_prompt_log(
                FROZEN_PROMPT_LOG.parent / "does-not-exist.json", image_size=1008
            )

    def test_rejects_anchor_camera_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document["anchorView"]["camera"].__setitem__(
                    "nearPlane", 0.02
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "camera does not match"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)

    def test_rejects_a_frame_size_mismatch(self) -> None:
        with self.assertRaisesRegex(PocRunRecordError, "does not match the trial frame"):
            load_frozen_benchmark_prompt_log(FROZEN_PROMPT_LOG, image_size=768)

    def test_rejects_a_non_new_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document["entries"][0].__setitem__(
                    "operation", "Add"
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "New point prompts only"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)

    def test_rejects_a_duplicate_prompt_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document["entries"][1]["prompt"].__setitem__(
                    "promptId", "controlled-overlap-center"
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "unique non-empty"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)

    def test_rejects_an_out_of_frame_point(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document["entries"][0]["prompt"].__setitem__(
                    "xPx", 1008
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "inside the Anchor frame"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)

    def test_rejects_an_unsupported_polarity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document["entries"][0]["prompt"].__setitem__(
                    "polarity", "emphasize"
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "include or exclude"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)

    def test_rejects_declared_correction_rounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            variant = self.write_variant(
                Path(directory),
                lambda document: document.__setitem__(
                    "correctionSequence", [{"operation": "Add"}]
                ),
            )
            with self.assertRaisesRegex(PocRunRecordError, "correction rounds"):
                load_frozen_benchmark_prompt_log(variant, image_size=1008)


class FrozenControlledOverlapGroundTruthTests(unittest.TestCase):
    """Bind the re-frozen controlled-overlap Ground Truth (ADR 0011).

    The distractor-enclosed target cap is ambiguous Ground Truth under the
    geometric sight-line screening rule; accuracy excludes it, the rear
    surface keeps only the honestly observable subset, and the PLY plus
    frozen Benchmark Prompt Log stay byte-identical.
    """

    fixture_root = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "benchmarks"
        / "fixtures"
        / "controlled-overlap"
    )

    def load_frozen(self) -> tuple[dict, dict, dict]:
        manifest = json.loads(
            (self.fixture_root / "controlled_front_back_overlap.json").read_text(
                encoding="utf-8"
            )
        )
        truth = json.loads(
            (
                self.fixture_root / "controlled_front_back_overlap_ground_truth.json"
            ).read_text(encoding="utf-8")
        )
        npz = np.load(
            self.fixture_root / "controlled_front_back_overlap_ground_truth.npz"
        )
        return manifest, truth, npz

    def id_set(self, value: object) -> set[int]:
        if isinstance(value, dict):
            start, end = value["inclusiveRange"]
            return set(range(start, end + 1))
        return set(value)

    def test_fixture_file_digests_match_the_manifest(self) -> None:
        manifest, _, _ = self.load_frozen()
        for name, record in manifest["files"].items():
            digest = hashlib.sha256(
                (self.fixture_root / name).read_bytes()
            ).hexdigest()
            self.assertEqual(digest, record["sha256"], name)
        # The Ground Truth re-freeze leaves the scene PLY and the frozen
        # Benchmark Prompt Log byte-identical.
        self.assertEqual(
            manifest["files"]["controlled_front_back_overlap.ply"]["sha256"],
            "cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8f2177964ad36aa6e",
        )
        self.assertEqual(
            manifest["files"]["benchmark-prompt-log-v1.json"]["sha256"],
            "8cce1991dea0e5bdf7a3ee7a32fe720daa5bb47d486a298849cbf0541bbd082b",
        )

    def test_ground_truth_json_digest_is_frozen(self) -> None:
        digest = hashlib.sha256(
            (
                self.fixture_root / "controlled_front_back_overlap_ground_truth.json"
            ).read_bytes()
        ).hexdigest()
        self.assertEqual(digest, EXPECTED_GROUND_TRUTH_JSON_SHA256)

    def test_ground_truth_partitions_the_fixture_universe(self) -> None:
        manifest, truth, npz = self.load_frozen()
        selected = self.id_set(truth["selectedStableGaussianIds"])
        rejected = self.id_set(truth["rejectedStableGaussianIds"])
        ambiguous = self.id_set(truth["ambiguousStableGaussianIds"])
        self.assertTrue(ambiguous)
        self.assertFalse(
            selected & rejected or selected & ambiguous or rejected & ambiguous
        )
        self.assertEqual(selected | rejected | ambiguous, set(range(16384)))
        self.assertTrue(ambiguous <= set(range(8192)))
        self.assertEqual({int(value) for value in npz["selected_ids"]}, selected)
        self.assertEqual({int(value) for value in npz["rejected_ids"]}, rejected)
        self.assertEqual({int(value) for value in npz["ambiguous_ids"]}, ambiguous)
        ground_truth_block = manifest["groundTruth"]
        self.assertEqual(ground_truth_block["selectedCount"], len(selected))
        self.assertEqual(ground_truth_block["ambiguousCount"], len(ambiguous))
        self.assertEqual(
            ground_truth_block["rearSurfaceCount"],
            MECHANICAL_REAR_Z_POSITIVE_COUNT - len(ambiguous),
        )

    def test_rear_surface_excludes_the_enclosed_ambiguous_cap(self) -> None:
        _, truth, _ = self.load_frozen()
        selected = self.id_set(truth["selectedStableGaussianIds"])
        ambiguous = self.id_set(truth["ambiguousStableGaussianIds"])
        rear = self.id_set(truth["rearSurfaceStableGaussianIds"])
        self.assertTrue(rear <= selected)
        self.assertFalse(rear & ambiguous)
        self.assertEqual(
            len(rear) + len(ambiguous), MECHANICAL_REAR_Z_POSITIVE_COUNT
        )

    def test_observability_rule_discloses_the_screening(self) -> None:
        manifest, truth, _ = self.load_frozen()
        rule = truth["observabilityRule"]
        self.assertEqual(rule["id"], "geometric-sight-line-screening/v1")
        self.assertEqual(rule["directionCount"], 1024)
        self.assertGreater(rule["occlusionRadius"], 0)
        self.assertEqual(rule["measuredEnclosedCapCount"], 482)
        self.assertIn("unobstructed sight line", rule["rule"])
        self.assertEqual(
            manifest["groundTruth"]["observabilityRule"],
            "geometric-sight-line-screening/v1",
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

    def test_excludes_ambiguous_truth_from_accuracy_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            # The candidate classifies the ambiguous truth ID as selected; the
            # scorer must exclude ambiguous truth from accuracy rather than
            # force it into either class.
            artifacts["candidateObjectSelection"].write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 4, 6],
                        "rejectedStableGaussianIds": [3, 5],
                        "uncertainStableGaussianIds": [],
                        "recordBindings": self.complete_bindings(),
                    }
                ),
                encoding="utf-8",
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "controlled-overlap-ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 3],
                        "rejectedStableGaussianIds": [4, 5],
                        "ambiguousStableGaussianIds": [6],
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

    def test_rejects_a_rear_surface_outside_selected_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            artifacts["candidateObjectSelection"].write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2],
                        "rejectedStableGaussianIds": [3, 4, 5, 6],
                        "uncertainStableGaussianIds": [],
                        "recordBindings": self.complete_bindings(),
                    }
                ),
                encoding="utf-8",
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 3],
                        "rejectedStableGaussianIds": [4, 5],
                        "ambiguousStableGaussianIds": [6],
                        "rearSurfaceStableGaussianIds": [2, 6],
                        "distractorStableGaussianIds": [4, 5],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PocRunRecordError, "subset of selected truth"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

    def test_rejects_a_candidate_that_omits_ambiguous_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(),
            )
            ground_truth = root / "ground-truth.json"
            ground_truth.write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 3],
                        "rejectedStableGaussianIds": [4, 5],
                        "ambiguousStableGaussianIds": [6],
                        "rearSurfaceStableGaussianIds": [2, 3],
                        "distractorStableGaussianIds": [4, 5],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PocRunRecordError, "does not completely classify"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                )

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
                prompt_log_source={
                    "file": "benchmark-prompt-log-v1.json",
                    "sha256": "sha256:prompt-log",
                },
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
            sealed_prompt_log = json.loads(
                (record.directory / "artifacts" / "benchmarkPromptLog.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                sealed_prompt_log["frozenSource"],
                {
                    "file": "benchmark-prompt-log-v1.json",
                    "sha256": "sha256:prompt-log",
                },
            )


if __name__ == "__main__":
    unittest.main()
