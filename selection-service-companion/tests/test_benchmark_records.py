from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from selection_service_companion.benchmark import (
    REQUIRED_PREDICTION_ARTIFACTS,
    PocRunRecordError,
    _OfficeGroundTruthSource,
    _load_poc_trial_registry,
    _seal_scored_run,
    _validate_benchmark_prompt_log,
    _validate_office_ground_truth_scene,
    _verified_prediction,
    assess_registered_trials,
    canonical_prompt_entries_sha256,
    score_and_seal_prediction,
    score_prediction,
    seal_prediction,
)
from selection_service_companion.controlled_overlap_benchmark import (
    _apply_trial_seed,
    _preview_render_policy,
    build_controlled_overlap_snapshot,
    load_frozen_benchmark_prompt_log,
    materialize_frozen_benchmark_prompt_log,
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

    def test_materializes_initial_new_points_as_one_session_new_operation(self) -> None:
        frozen_entries = load_frozen_benchmark_prompt_log(
            FROZEN_PROMPT_LOG, image_size=1008
        )

        prompt_log = materialize_frozen_benchmark_prompt_log(
            frozen_entries,
            anchor_digest="sha256:anchor",
            image_size=1008,
        )

        self.assertEqual(
            [entry["operation"] for entry in prompt_log],
            ["New", "Refine", "Refine", "Refine", "Refine"],
        )
        self.assertEqual(
            [entry["prompt"]["promptId"] for entry in prompt_log],
            [
                "controlled-overlap-center",
                "controlled-overlap-north",
                "controlled-overlap-south",
                "controlled-overlap-west",
                "controlled-overlap-east",
            ],
        )
        for entry in prompt_log:
            self.assertEqual(entry["prompt"]["frameDigest"], "sha256:anchor")
            self.assertEqual(entry["prompt"]["frameWidth"], 1008)
            self.assertEqual(entry["prompt"]["frameHeight"], 1008)
        self.assertEqual([entry["operation"] for entry in frozen_entries], ["New"] * 5)

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


class OfficeRecordTrustBoundaryTests(unittest.TestCase):
    def test_rejects_non_integral_or_boolean_office_scene_count(self) -> None:
        source = _OfficeGroundTruthSource(
            source_path="office.ply",
            sha256="a" * 64,
            gaussian_count=5,
        )
        for gaussian_count in (5.0, True):
            with self.subTest(gaussian_count=gaussian_count):
                with self.assertRaisesRegex(
                    PocRunRecordError, "sealed Scene Snapshot identity"
                ):
                    _validate_office_ground_truth_scene(
                        source,
                        {
                            "sceneVersion": f"sha256:{source.sha256}",
                            "gaussianCount": gaussian_count,
                            "stableIdSchema": "uint32",
                        },
                    )

    def test_rejects_office_prompt_log_without_frozen_point_entries(self) -> None:
        with self.assertRaisesRegex(PocRunRecordError, "frozen entries"):
            _validate_benchmark_prompt_log(
                {
                    "targetId": "gift_box",
                    "frozenSource": {
                        "file": "gift-box-point-log-v1.json",
                        "sha256": "sha256:" + "a" * 64,
                    },
                    "frozenEntries": [],
                    "entries": [],
                },
                expected_target_id="gift_box",
                frame_set={
                    "orderedViews": [
                        {
                            "viewId": "anchor-view",
                            "frameDigest": "sha256:" + "a" * 64,
                            "width": 1008,
                            "height": 1008,
                        }
                    ]
                },
            )

    def test_rejects_a_second_session_new_operation(self) -> None:
        frame_digest = "sha256:" + "a" * 64
        prompt = {
            "viewId": "anchor-view",
            "frameDigest": frame_digest,
            "frameWidth": 1008,
            "frameHeight": 1008,
            "xPx": 100,
            "yPx": 200,
            "polarity": "include",
        }
        with self.assertRaisesRegex(PocRunRecordError, "one initial New"):
            _validate_benchmark_prompt_log(
                {
                    "targetId": "controlled-overlap",
                    "frozenSource": {
                        "file": "benchmark-prompt-log-v1.json",
                        "sha256": frame_digest,
                    },
                    "frozenEntries": [
                        {"operation": "New", "prompt": {**prompt, "promptId": "one"}},
                        {"operation": "New", "prompt": {**prompt, "promptId": "two"}},
                    ],
                    "entries": [
                        {"operation": "New", "prompt": {**prompt, "promptId": "one"}},
                        {"operation": "New", "prompt": {**prompt, "promptId": "two"}},
                    ],
                },
                expected_target_id="controlled-overlap",
                frame_set={
                    "orderedViews": [
                        {
                            "viewId": "anchor-view",
                            "frameDigest": frame_digest,
                            "width": 1008,
                            "height": 1008,
                        }
                    ]
                },
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
            "sceneVersion": "sha256:" + "d" * 64,
            "operation": "New",
            "correctionRound": 0,
            "promptLogRevision": 1,
            "frameSetVersion": "frames-final",
            "renderConfigVersion": "render-v1",
            "modelManifestDigest": "sha256:" + "c" * 64,
        }
        bindings.update(overrides)
        return bindings

    def complete_artifacts(
        self,
        root: Path,
        *,
        bindings: dict[str, object] | None = None,
        render_policy: dict[str, object] | None = None,
        evidence_snapshot_policy: dict[str, object] | None = None,
    ) -> dict[str, Path]:
        if bindings is None:
            bindings = self.complete_bindings()
        if render_policy is None:
            render_policy = {
                "renderConfigVersion": "render-v1",
                "evidencePolicy": {
                    "id": "selection-evidence-policy/v1",
                    "renderConfigVersion": "render-v1",
                },
            }
        if evidence_snapshot_policy is None:
            evidence_snapshot_policy = {
                "id": "selection-evidence-policy/v1",
                "renderConfigVersion": "render-v1",
            }
        inputs = root / "inputs"
        inputs.mkdir()
        frame_digest = "sha256:" + "a" * 64
        frozen_prompt = {
            "promptId": "controlled-center",
            "viewId": "anchor-view",
            "xPx": 100,
            "yPx": 200,
            "polarity": "include",
        }
        frozen_entries = [{"operation": "New", "prompt": frozen_prompt}]
        session_entries = [
            {
                "operation": "New",
                "prompt": {
                    **frozen_prompt,
                    "frameDigest": frame_digest,
                    "frameWidth": 1008,
                    "frameHeight": 1008,
                },
            }
        ]
        frozen_entries_sha256 = canonical_prompt_entries_sha256(frozen_entries)
        session_entries_sha256 = canonical_prompt_entries_sha256(session_entries)
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
                    "sceneId": bindings["sceneId"],
                    "sceneVersion": bindings["sceneVersion"],
                    "gaussianCount": 5,
                    "stableIdSchema": "uint32",
                }
            elif name == "frameSet":
                value = {
                    "frameSetVersion": bindings["frameSetVersion"],
                    "orderedViews": [
                        {
                            "viewId": "anchor-view",
                            "frameDigest": frame_digest,
                            "width": 1008,
                            "height": 1008,
                        }
                    ],
                }
            elif name == "benchmarkPromptLog":
                value = {
                    "targetId": "controlled-overlap",
                    "frozenSource": {
                        "file": "benchmark-prompt-log-v1.json",
                        "sha256": frame_digest,
                    },
                    "frozenEntries": frozen_entries,
                    "frozenEntriesSha256": frozen_entries_sha256,
                    "entries": session_entries,
                    "sessionEntriesSha256": session_entries_sha256,
                }
            elif name == "maskSet":
                value = {
                    "requestId": bindings["requestId"],
                    "sessionId": bindings["sessionId"],
                    "promptLogRevision": bindings["promptLogRevision"],
                    "promptLogEntriesSha256": session_entries_sha256,
                    "frameSetVersion": bindings["frameSetVersion"],
                    "modelManifestDigest": bindings["modelManifestDigest"],
                }
            elif name == "coverageReport":
                value = {"status": "sufficient"}
            elif name == "renderPolicy":
                value = render_policy
            elif name == "evidenceSnapshot":
                value = {
                    **{
                        name: value
                        for name, value in bindings.items()
                        if name not in {"trialId", "terminalState"}
                    },
                    "policy": evidence_snapshot_policy,
                    "records": [],
                }
            elif name == "modelManifest":
                value = {
                    "adapterId": "sam3.1",
                    "checkpointDigest": "sha256:" + "b" * 64,
                    "digest": bindings["modelManifestDigest"],
                }
            elif name == "runtimeManifest":
                effective_seed = int.from_bytes(
                    hashlib.sha256(
                        str(bindings["deterministicSeed"]).encode("utf-8")
                    ).digest()[:4],
                    "big",
                )
                value = {
                    "companionVersion": "0.1.0",
                    "serviceBuild": "selection-service-companion/0.1.0+test",
                    "protocolVersion": bindings["protocolVersion"],
                    "randomness": {
                        "declaredSeed": bindings["deterministicSeed"],
                        "effectiveSeed": effective_seed,
                        "seedDerivation": "sha256-utf8-first-u32be/v1",
                        "pythonRandomSeeded": True,
                        "numpyRandomSeeded": True,
                        "torchCpuSeeded": True,
                        "torchCudaSeeded": True,
                        "algorithmDeterminism": "not-forced",
                    },
                    "executionProfile": {
                        "browser": {"family": "Chromium", "version": "123.0"},
                        "transport": {
                            "kind": "fetch",
                            "endpointScope": "loopback",
                        },
                    },
                }
            elif name == "correctionOutcomes":
                value = {
                    "outcomes": [
                        {
                            "operation": "New",
                            "correctionRound": 0,
                            "requestId": bindings["requestId"],
                            "promptLogRevision": bindings["promptLogRevision"],
                            "promptLogEntriesSha256": session_entries_sha256,
                            "terminalState": "complete",
                        }
                    ]
                }
            elif name == "timingAndVram":
                value = {
                    "stageSeconds": {"previewPublicationSeconds": 1.0},
                    "peakVramBytes": 1024,
                    "peakVramMeasurement": "test sampler",
                }
            if isinstance(value, dict):
                value = {**value, "recordBindings": bindings}
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

    def controlled_ground_truth(self, root: Path) -> Path:
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
        return ground_truth

    def registered_trial_registry(self, root: Path, ground_truth: Path) -> Path:
        registry = root / "poc-trial-registry.json"
        inputs = root / "inputs"
        if not inputs.is_dir():
            raise AssertionError("complete_artifacts must run before registry setup")
        prompt_log_path = root / "inputs" / "benchmarkPromptLog.json"
        prompt_log = json.loads(prompt_log_path.read_text(encoding="utf-8"))
        scene = json.loads((inputs / "sceneSnapshot.json").read_text(encoding="utf-8"))
        model = json.loads((inputs / "modelManifest.json").read_text(encoding="utf-8"))
        runtime = json.loads((inputs / "runtimeManifest.json").read_text(encoding="utf-8"))
        render_policy = json.loads(
            (inputs / "renderPolicy.json").read_text(encoding="utf-8")
        )
        bindings = model["recordBindings"]
        registry.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "benchmarkId": "test-poc/v1",
                    "targets": [
                        {
                            "targetId": "controlled-overlap",
                            "benchmarkKind": "controlled-overlap",
                            "availability": "ready",
                            "sceneSnapshot": {
                                "targetSplatId": bindings["targetSplatId"],
                                "sceneId": scene["sceneId"],
                                "sceneVersion": scene["sceneVersion"],
                                "gaussianCount": scene["gaussianCount"],
                                "stableIdSchema": scene["stableIdSchema"],
                            },
                            "executionProfile": {
                                "protocolVersion": bindings["protocolVersion"],
                                "model": {
                                    "adapterId": model["adapterId"],
                                    "digest": model["digest"],
                                    "checkpointDigest": model["checkpointDigest"],
                                },
                                "runtime": {
                                    "lockDigest": runtime["release"]["lockDigest"],
                                },
                                "seedPolicy": {
                                    "seedDerivation": runtime["randomness"][
                                        "seedDerivation"
                                    ],
                                    "algorithmDeterminism": runtime["randomness"][
                                        "algorithmDeterminism"
                                    ],
                                },
                                "render": {
                                    "renderConfigVersion": render_policy[
                                        "renderConfigVersion"
                                    ],
                                    "evidencePolicy": {
                                        "id": render_policy["evidencePolicy"]["id"],
                                        "renderConfigVersion": render_policy[
                                            "evidencePolicy"
                                        ]["renderConfigVersion"],
                                    },
                                },
                            },
                            "groundTruth": {
                                "path": ground_truth.name,
                                "sha256": "sha256:"
                                + hashlib.sha256(ground_truth.read_bytes()).hexdigest()
                            },
                            "promptLog": {
                                "status": "frozen-point-only",
                                "sha256": "sha256:" + "a" * 64,
                                "entriesSha256": canonical_prompt_entries_sha256(
                                    prompt_log["frozenEntries"]
                                ),
                            },
                            "requiredSeeds": [
                                "controlled-seed-1",
                                "controlled-seed-2",
                                "controlled-seed-3",
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return registry

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
                benchmark_registry_path=self.registered_trial_registry(
                    root, ground_truth
                ),
            )

            self.assertEqual(result["metrics"]["intersectionOverUnion"], 0.5)
            self.assertEqual(result["metrics"]["precision"], 2 / 3)
            self.assertEqual(result["metrics"]["recall"], 2 / 3)
            self.assertEqual(result["metrics"]["rearSurfaceRecall"], 0.5)
            self.assertEqual(result["metrics"]["selectedDistractorCount"], 1)
            self.assertFalse(result["controlledOverlapGatePassed"])
            self.assertEqual(
                result["gateReport"]["gates"]["defaultPathCorrectness"]["status"],
                "fail",
            )
            self.assertEqual(
                result["gateReport"]["gates"]["recordCompleteness"]["status"],
                "pass",
            )
            self.assertEqual(result["gateReport"]["overallStatus"], "fail")
            self.assertTrue((root / "score.json").is_file())

    def test_marks_missing_browser_transport_evidence_as_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            runtime = json.loads(
                artifacts["runtimeManifest"].read_text(encoding="utf-8")
            )
            runtime["executionProfile"] = {
                "browser": "not-applicable (standalone CLI benchmark)",
                "transport": "in-process CompanionState; no network transport",
            }
            artifacts["runtimeManifest"].write_text(
                json.dumps(runtime), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )

            result = score_prediction(
                record.directory,
                ground_truth_path=self.controlled_ground_truth(root),
                output_path=root / "score.json",
            )

            completeness = result["gateReport"]["gates"]["recordCompleteness"]
            self.assertEqual(completeness["status"], "fail")
            self.assertIn(
                "reference browser/version and non-secret transport profile",
                completeness["reasons"],
            )

    def test_rejects_a_substituted_registered_ground_truth_or_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ground_truth = self.controlled_ground_truth(root)
            artifacts = self.complete_artifacts(root)
            registry = self.registered_trial_registry(root, ground_truth)
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            ground_truth.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(PocRunRecordError, "registered fixture"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                    benchmark_registry_path=registry,
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ground_truth = self.controlled_ground_truth(root)
            bindings = self.complete_bindings(deterministicSeed="cherry-picked")
            artifacts = self.complete_artifacts(root, bindings=bindings)
            registry = self.registered_trial_registry(root, ground_truth)
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=bindings,
            )

            with self.assertRaisesRegex(PocRunRecordError, "prescribed fixed seed"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                    benchmark_registry_path=registry,
                )

    def test_marks_an_unbound_prompt_log_or_outcome_prefix_as_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            prompt_log = json.loads(
                artifacts["benchmarkPromptLog"].read_text(encoding="utf-8")
            )
            del prompt_log["sessionEntriesSha256"]
            artifacts["benchmarkPromptLog"].write_text(
                json.dumps(prompt_log), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            ground_truth = self.controlled_ground_truth(root)

            result = score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
                benchmark_registry_path=self.registered_trial_registry(
                    root, ground_truth
                ),
            )
            self.assertIn(
                "frozen Prompt Log execution binding",
                result["gateReport"]["gates"]["recordCompleteness"]["reasons"],
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            correction_outcomes = json.loads(
                artifacts["correctionOutcomes"].read_text(encoding="utf-8")
            )
            correction_outcomes["outcomes"][0]["promptLogEntriesSha256"] = (
                "sha256:" + "0" * 64
            )
            artifacts["correctionOutcomes"].write_text(
                json.dumps(correction_outcomes), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            ground_truth = self.controlled_ground_truth(root)

            result = score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
                benchmark_registry_path=self.registered_trial_registry(
                    root, ground_truth
                ),
            )
            self.assertEqual(
                result["gateReport"]["gates"]["correctionRoundBound"]["status"],
                "fail",
            )

    def test_aggregate_requires_every_registered_target_and_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ground_truth = self.controlled_ground_truth(root)
            artifacts = self.complete_artifacts(root)
            registry = self.registered_trial_registry(root, ground_truth)
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=self.complete_bindings(),
            )
            _, final_record = score_and_seal_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
                final_record_directory=root / "trial-1-final",
                benchmark_registry_path=registry,
            )

            assessment = assess_registered_trials(
                registry,
                final_record_directories=[final_record.directory],
                output_path=root / "assessment.json",
            )

            self.assertEqual(assessment["acceptanceStatus"], "fail")
            self.assertEqual(len(assessment["trials"]), 3)
            self.assertTrue(
                any(
                    trial.get("reason") == "required final scored Run Record is missing"
                    for trial in assessment["trials"]
                )
            )
            self.assertTrue((root / "assessment.json").is_file())
            with self.assertRaisesRegex(PocRunRecordError, "scored Run Record"):
                assess_registered_trials(
                    registry,
                    final_record_directories=[final_record.directory],
                    output_path=final_record.directory / "assessment.json",
                )

    def test_rejects_score_outputs_that_alias_consumed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = seal_prediction(
                root / "trial-1",
                artifacts=self.complete_artifacts(root),
                bindings=self.complete_bindings(),
            )
            ground_truth = self.controlled_ground_truth(root)
            ground_truth_before = ground_truth.read_bytes()

            with self.assertRaisesRegex(
                PocRunRecordError, "must not overwrite Benchmark Ground Truth"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=ground_truth,
                )
            self.assertEqual(ground_truth.read_bytes(), ground_truth_before)

            hard_link_output = root / "ground-truth-hard-link.json"
            hard_link_output.hardlink_to(ground_truth)
            with self.assertRaisesRegex(
                PocRunRecordError, "must not overwrite Benchmark Ground Truth"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=hard_link_output,
                )
            self.assertEqual(ground_truth.read_bytes(), ground_truth_before)

            candidate = record.directory / "artifacts" / "candidateObjectSelection.json"
            candidate_before = candidate.read_bytes()
            candidate_output = root / "candidate-hard-link.json"
            candidate_output.hardlink_to(candidate)
            with self.assertRaisesRegex(
                PocRunRecordError, "must not overwrite sealed prediction input"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=candidate_output,
                )
            self.assertEqual(candidate.read_bytes(), candidate_before)

            predictable_ground_truth = root / "sealed-score.json.tmp"
            predictable_ground_truth.write_bytes(ground_truth_before)
            score_prediction(
                record.directory,
                ground_truth_path=predictable_ground_truth,
                output_path=root / "sealed-score.json",
            )
            self.assertEqual(
                predictable_ground_truth.read_bytes(), ground_truth_before
            )

            predictable_candidate = root / "candidate-score.json.tmp"
            predictable_candidate.hardlink_to(candidate)
            score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "candidate-score.json",
            )
            self.assertEqual(candidate.read_bytes(), candidate_before)

    def test_correction_gate_requires_contiguous_bound_successes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = self.complete_bindings(operation="Refine", correctionRound=5)
            artifacts = self.complete_artifacts(root, bindings=bindings)
            correction_outcomes = json.loads(
                artifacts["correctionOutcomes"].read_text(encoding="utf-8")
            )
            correction_outcomes["outcomes"].append(
                {
                    "operation": "Refine",
                    "correctionRound": 5,
                    "requestId": bindings["requestId"],
                    "terminalState": "complete",
                }
            )
            artifacts["correctionOutcomes"].write_text(
                json.dumps(correction_outcomes), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial-1", artifacts=artifacts, bindings=bindings
            )

            result = score_prediction(
                record.directory,
                ground_truth_path=self.controlled_ground_truth(root),
                output_path=root / "score.json",
            )

            self.assertEqual(
                result["gateReport"]["gates"]["correctionRoundBound"]["status"],
                "fail",
            )
            self.assertEqual(
                result["gateReport"]["gates"]["recordCompleteness"]["status"],
                "fail",
            )

    def test_correction_gate_binds_the_final_success_to_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = self.complete_bindings(operation="Refine", correctionRound=1)
            artifacts = self.complete_artifacts(root, bindings=bindings)
            correction_outcomes = json.loads(
                artifacts["correctionOutcomes"].read_text(encoding="utf-8")
            )
            correction_outcomes["outcomes"].append(
                {
                    "operation": "Refine",
                    "correctionRound": 1,
                    "requestId": "another-request",
                    "terminalState": "complete",
                }
            )
            artifacts["correctionOutcomes"].write_text(
                json.dumps(correction_outcomes), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial-1", artifacts=artifacts, bindings=bindings
            )

            result = score_prediction(
                record.directory,
                ground_truth_path=self.controlled_ground_truth(root),
                output_path=root / "score.json",
            )

            self.assertEqual(
                result["gateReport"]["gates"]["correctionRoundBound"]["status"],
                "fail",
            )

    def test_seals_independent_score_as_the_final_run_record(self) -> None:
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
            score_path = root / "score.json"
            registry_path = self.registered_trial_registry(root, ground_truth)
            result, final_record = score_and_seal_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=score_path,
                final_record_directory=root / "trial-1-final",
                benchmark_registry_path=registry_path,
            )

            final_manifest = json.loads(
                final_record.manifest_path.read_text(encoding="utf-8")
            )
            final_seal = json.loads(final_record.seal_path.read_text(encoding="utf-8"))
            copied_score = json.loads(
                (
                    final_record.directory
                    / final_manifest["score"]["path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(final_manifest["status"], "scored")
            self.assertEqual(
                final_manifest["prediction"]["manifestSha256"],
                record.manifest_sha256,
            )
            self.assertEqual(
                copied_score["predictionManifestSha256"], record.manifest_sha256
            )
            self.assertEqual(
                final_manifest["score"]["sha256"],
                "sha256:"
                + hashlib.sha256(
                    (
                        final_record.directory / final_manifest["score"]["path"]
                    ).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(final_seal["status"], "sealed-after-ground-truth")
            self.assertEqual(
                copied_score["controlledOverlapGatePassed"],
                result["controlledOverlapGatePassed"],
            )
            injected_score = final_record.directory / "injected-score.json"
            with self.assertRaisesRegex(
                PocRunRecordError, "scored Run Record"
            ):
                score_and_seal_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=injected_score,
                    final_record_directory=final_record.directory,
                    benchmark_registry_path=registry_path,
                )
            self.assertFalse(injected_score.exists())
            with self.assertRaisesRegex(
                PocRunRecordError, "outside an existing scored Run Record"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=injected_score,
                    benchmark_registry_path=registry_path,
                )
            with self.assertRaisesRegex(
                PocRunRecordError, "outside an existing scored Run Record"
            ):
                score_and_seal_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=injected_score,
                    final_record_directory=root / "different-final-record",
                    benchmark_registry_path=registry_path,
                )
            self.assertFalse((root / "different-final-record").exists())

            tampered_final = root / "tampered-final"
            shutil.copytree(final_record.directory, tampered_final)
            tampered_score_path = tampered_final / final_manifest["score"]["path"]
            tampered_score = json.loads(tampered_score_path.read_text(encoding="utf-8"))
            tampered_score["metrics"] = {
                "intersectionOverUnion": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "rearSurfaceRecall": 1.0,
                "selectedDistractorCount": 0,
            }
            tampered_score["controlledOverlapGatePassed"] = True
            tampered_score_path.write_text(
                json.dumps(tampered_score, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered_manifest_path = tampered_final / "scored-run-manifest.json"
            tampered_manifest = json.loads(
                tampered_manifest_path.read_text(encoding="utf-8")
            )
            tampered_manifest["score"]["bytes"] = tampered_score_path.stat().st_size
            tampered_manifest["score"]["sha256"] = "sha256:" + hashlib.sha256(
                tampered_score_path.read_bytes()
            ).hexdigest()
            tampered_manifest_path.write_text(
                json.dumps(tampered_manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered_seal_path = tampered_final / "scored-run-seal.json"
            tampered_seal = json.loads(tampered_seal_path.read_text(encoding="utf-8"))
            tampered_seal["manifestSha256"] = "sha256:" + hashlib.sha256(
                tampered_manifest_path.read_bytes()
            ).hexdigest()
            tampered_seal_path.write_text(
                json.dumps(tampered_seal, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            assessment = assess_registered_trials(
                registry_path,
                final_record_directories=[tampered_final],
            )
            self.assertEqual(assessment["acceptanceStatus"], "fail")
            self.assertIn(
                "frozen evaluator",
                assessment["invalidRecords"][0]["reason"],
            )

            external_prediction = root / "external-prediction"
            shutil.copytree(final_record.directory / "prediction", external_prediction)
            symlinked_final = root / "symlinked-final"
            shutil.copytree(final_record.directory, symlinked_final)
            shutil.rmtree(symlinked_final / "prediction")
            (symlinked_final / "prediction").symlink_to(
                external_prediction, target_is_directory=True
            )
            assessment = assess_registered_trials(
                registry_path,
                final_record_directories=[symlinked_final],
            )
            self.assertIn(
                "copied prediction escapes",
                assessment["invalidRecords"][0]["reason"],
            )

            forged_score = json.loads(json.dumps(result))
            forged_score["controlledOverlapGatePassed"] = True
            with self.assertRaisesRegex(PocRunRecordError, "gate is inconsistent"):
                _seal_scored_run(
                    root / "forged-final",
                    prediction=_verified_prediction(record.directory),
                    score=forged_score,
                    registry=_load_poc_trial_registry(registry_path),
                )

    def test_registry_binds_frozen_prompt_entries_and_scene_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ground_truth = self.controlled_ground_truth(root)
            artifacts = self.complete_artifacts(root)
            registry = self.registered_trial_registry(root, ground_truth)
            prompt_log = json.loads(
                artifacts["benchmarkPromptLog"].read_text(encoding="utf-8")
            )
            prompt_log["frozenEntries"][0]["prompt"]["xPx"] = 101
            prompt_log["entries"][0]["prompt"]["xPx"] = 101
            prompt_log["frozenEntriesSha256"] = canonical_prompt_entries_sha256(
                prompt_log["frozenEntries"]
            )
            session_sha256 = canonical_prompt_entries_sha256(prompt_log["entries"])
            prompt_log["sessionEntriesSha256"] = session_sha256
            artifacts["benchmarkPromptLog"].write_text(
                json.dumps(prompt_log), encoding="utf-8"
            )
            mask_set = json.loads(artifacts["maskSet"].read_text(encoding="utf-8"))
            mask_set["promptLogEntriesSha256"] = session_sha256
            artifacts["maskSet"].write_text(json.dumps(mask_set), encoding="utf-8")
            outcomes = json.loads(
                artifacts["correctionOutcomes"].read_text(encoding="utf-8")
            )
            outcomes["outcomes"][0]["promptLogEntriesSha256"] = session_sha256
            artifacts["correctionOutcomes"].write_text(
                json.dumps(outcomes), encoding="utf-8"
            )
            record = seal_prediction(
                root / "mutated-prompt", artifacts=artifacts, bindings=self.complete_bindings()
            )
            with self.assertRaisesRegex(PocRunRecordError, "frozen entries"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "score.json",
                    benchmark_registry_path=registry,
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical_root = root / "canonical"
            canonical_root.mkdir()
            ground_truth = self.controlled_ground_truth(canonical_root)
            self.complete_artifacts(canonical_root)
            registry = self.registered_trial_registry(canonical_root, ground_truth)
            trial_root = root / "substitute"
            trial_root.mkdir()
            bindings = self.complete_bindings(sceneVersion="sha256:" + "e" * 64)
            artifacts = self.complete_artifacts(trial_root, bindings=bindings)
            record = seal_prediction(
                trial_root / "trial", artifacts=artifacts, bindings=bindings
            )
            with self.assertRaisesRegex(PocRunRecordError, "canonical Scene Snapshot"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=trial_root / "score.json",
                    benchmark_registry_path=registry,
                )

    def test_recomputes_the_registered_effective_runtime_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ground_truth = self.controlled_ground_truth(root)
            artifacts = self.complete_artifacts(root)
            registry = self.registered_trial_registry(root, ground_truth)
            runtime = json.loads(
                artifacts["runtimeManifest"].read_text(encoding="utf-8")
            )
            runtime["randomness"]["effectiveSeed"] += 1
            artifacts["runtimeManifest"].write_text(
                json.dumps(runtime), encoding="utf-8"
            )
            record = seal_prediction(
                root / "trial", artifacts=artifacts, bindings=self.complete_bindings()
            )

            result = score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
                benchmark_registry_path=registry,
            )

            self.assertIn(
                "effective runtime seed and determinism policy",
                result["gateReport"]["gates"]["recordCompleteness"]["reasons"],
            )

    def test_browser_claims_cannot_make_a_formal_gate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = self.complete_artifacts(root)
            browser_claim = root / "browser-acceptance.json"
            browser_claim.write_text(
                json.dumps(
                    {
                        "producer": "browser",
                        "gates": {
                            "blindReadyJudgment": {"status": "pass"},
                            "uncertaintyDisclosure": {"status": "pass"},
                            "editorCompatibility": {"status": "pass"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            artifacts["browserAcceptance"] = browser_claim
            record = seal_prediction(
                root / "trial", artifacts=artifacts, bindings=self.complete_bindings()
            )
            result = score_prediction(
                record.directory,
                ground_truth_path=self.controlled_ground_truth(root),
                output_path=root / "score.json",
            )
            gate = result["gateReport"]["gates"]["blindReadyJudgment"]
            self.assertEqual(gate["status"], "fail")
            self.assertEqual(gate["evidenceStatus"], "unverified")

    def test_applies_distinct_effective_runtime_seeds(self) -> None:
        class FakeCuda:
            def __init__(self) -> None:
                self.seeds: list[int] = []

            def manual_seed_all(self, seed: int) -> None:
                self.seeds.append(seed)

        class FakeTorch:
            def __init__(self) -> None:
                self.cpu_seeds: list[int] = []
                self.cuda = FakeCuda()

            def manual_seed(self, seed: int) -> None:
                self.cpu_seeds.append(seed)

            def are_deterministic_algorithms_enabled(self) -> bool:
                return False

        torch = FakeTorch()
        first = _apply_trial_seed(torch, "controlled-overlap-seed-1")
        second = _apply_trial_seed(torch, "controlled-overlap-seed-2")

        self.assertNotEqual(first["effectiveSeed"], second["effectiveSeed"])
        self.assertEqual(torch.cpu_seeds, [first["effectiveSeed"], second["effectiveSeed"]])
        self.assertEqual(torch.cuda.seeds, [first["effectiveSeed"], second["effectiveSeed"]])

    def test_scores_hashed_office_labels_within_the_frozen_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_ply = root / "office.ply"
            source_ply.write_bytes(b"frozen office fixture")
            source_sha256 = hashlib.sha256(source_ply.read_bytes()).hexdigest()
            bindings = self.complete_bindings(
                sceneId="office",
                sceneVersion=f"sha256:{source_sha256}",
                targetSplatId="office",
                trialId="gift-box-seed-1",
                promptLogRevision=2,
            )
            artifacts = self.complete_artifacts(root, bindings=bindings)
            frozen_entries = [
                {
                    "operation": "New",
                    "prompt": {
                        "promptId": "gift-box-center",
                        "viewId": "anchor-view",
                        "xPx": 100,
                        "yPx": 200,
                        "polarity": "include",
                    },
                },
                {
                    "operation": "New",
                    "prompt": {
                        "promptId": "gift-box-lower",
                        "viewId": "anchor-view",
                        "xPx": 110,
                        "yPx": 220,
                        "polarity": "include",
                    },
                },
            ]
            session_entries = [
                {
                    "operation": "New",
                    "prompt": {
                        **frozen_entries[0]["prompt"],
                        "frameDigest": "sha256:" + "a" * 64,
                        "frameWidth": 1008,
                        "frameHeight": 1008,
                    },
                },
                {
                    "operation": "Refine",
                    "prompt": {
                        **frozen_entries[1]["prompt"],
                        "frameDigest": "sha256:" + "a" * 64,
                        "frameWidth": 1008,
                        "frameHeight": 1008,
                    },
                },
            ]
            session_entries_sha256 = canonical_prompt_entries_sha256(session_entries)
            artifacts["benchmarkPromptLog"].write_text(
                json.dumps(
                    {
                        "targetId": "gift_box",
                        "frozenSource": {
                            "file": "gift-box-point-log-v1.json",
                            "sha256": "sha256:" + "a" * 64,
                        },
                        "frozenEntries": frozen_entries,
                        "frozenEntriesSha256": canonical_prompt_entries_sha256(
                            frozen_entries
                        ),
                        "entries": session_entries,
                        "sessionEntriesSha256": session_entries_sha256,
                        "sessionMaterialization": {
                            "kind": "initial-new-points-to-primary-track/v1"
                        },
                        "recordBindings": bindings,
                    }
                ),
                encoding="utf-8",
            )
            mask_set = json.loads(artifacts["maskSet"].read_text(encoding="utf-8"))
            mask_set["promptLogEntriesSha256"] = session_entries_sha256
            artifacts["maskSet"].write_text(json.dumps(mask_set), encoding="utf-8")
            correction_outcomes = json.loads(
                artifacts["correctionOutcomes"].read_text(encoding="utf-8")
            )
            correction_outcomes["outcomes"][0].update(
                {
                    "promptLogRevision": 2,
                    "promptLogEntriesSha256": session_entries_sha256,
                }
            )
            artifacts["correctionOutcomes"].write_text(
                json.dumps(correction_outcomes), encoding="utf-8"
            )
            artifacts["candidateObjectSelection"].write_text(
                json.dumps(
                    {
                        "selectedStableGaussianIds": [1, 2, 3, 99],
                        "rejectedStableGaussianIds": [4, 5],
                        "uncertainStableGaussianIds": [],
                        "recordBindings": bindings,
                    }
                ),
                encoding="utf-8",
            )
            record = seal_prediction(
                root / "trial-1",
                artifacts=artifacts,
                bindings=bindings,
            )
            labels = root / "office-ground-truth.npz"
            np.savez(
                labels,
                selected_ids=np.array([1, 2, 3], dtype=np.uint32),
                rejected_ids=np.array([4, 5], dtype=np.uint32),
                ambiguous_ids=np.array([], dtype=np.uint32),
                scope_ids=np.array([1, 2, 3, 4, 5], dtype=np.uint32),
            )
            ground_truth = root / "office-ground-truth.json"
            ground_truth_value = {
                "schema_version": 1,
                "status": "frozen",
                "target_id": "gift_box",
                "source_ply": {
                    "path": "office.ply",
                    "sha256": source_sha256,
                    "gaussian_count": 5,
                },
                "labels": {
                    "artifact": labels.name,
                    "artifact_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
                    "scope_stable_gaussians": 5,
                    "selected_stable_gaussians": 3,
                    "rejected_stable_gaussians": 2,
                    "ambiguous_stable_gaussians": 0,
                },
            }
            ground_truth.write_text(
                json.dumps(ground_truth_value), encoding="utf-8"
            )

            with self.assertRaisesRegex(PocRunRecordError, "source PLY path"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "unassessed-score.json",
                )
            wrong_source_ply = root / "wrong-office.ply"
            wrong_source_ply.write_bytes(b"different office fixture")
            with self.assertRaisesRegex(PocRunRecordError, "source PLY hash"):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=root / "wrong-source-score.json",
                    office_source_ply_path=wrong_source_ply,
                )

            source_before = source_ply.read_bytes()
            with self.assertRaisesRegex(
                PocRunRecordError, "must not overwrite office source PLY"
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=source_ply,
                    office_source_ply_path=source_ply,
                )
            self.assertEqual(source_ply.read_bytes(), source_before)

            labels_before = labels.read_bytes()
            with self.assertRaisesRegex(
                PocRunRecordError,
                "must not overwrite office Benchmark Ground Truth labels",
            ):
                score_prediction(
                    record.directory,
                    ground_truth_path=ground_truth,
                    output_path=labels,
                    office_source_ply_path=source_ply,
                )
            self.assertEqual(labels.read_bytes(), labels_before)

            result = score_prediction(
                record.directory,
                ground_truth_path=ground_truth,
                output_path=root / "score.json",
                office_source_ply_path=source_ply,
            )

            self.assertEqual(result["benchmarkKind"], "office")
            self.assertEqual(result["targetId"], "gift_box")
            self.assertEqual(result["metrics"]["intersectionOverUnion"], 1.0)
            self.assertEqual(result["metrics"]["precision"], 1.0)
            self.assertEqual(result["metrics"]["recall"], 1.0)
            self.assertEqual(
                result["officeSourcePlySha256"], f"sha256:{source_sha256}"
            )
            self.assertTrue(result["officeGatePassed"])
            self.assertEqual(
                result["gateReport"]["gates"]["blindReadyJudgment"]["status"],
                "fail",
            )
            self.assertEqual(
                result["gateReport"]["gates"]["blindReadyJudgment"][
                    "evidenceStatus"
                ],
                "unassessed",
            )
            self.assertEqual(result["gateReport"]["overallStatus"], "fail")

            ground_truth_value["target_id"] = "microwave"
            mismatched_target_ground_truth = root / "mismatched-target-ground-truth.json"
            mismatched_target_ground_truth.write_text(
                json.dumps(ground_truth_value), encoding="utf-8"
            )
            with self.assertRaisesRegex(PocRunRecordError, "benchmark target"):
                score_prediction(
                    record.directory,
                    ground_truth_path=mismatched_target_ground_truth,
                    output_path=root / "mismatched-target-score.json",
                    office_source_ply_path=source_ply,
                )

            ground_truth_value["target_id"] = "gift_box"
            ground_truth_value["source_ply"]["sha256"] = "0" * 64
            mismatched_ground_truth = root / "mismatched-office-ground-truth.json"
            mismatched_ground_truth.write_text(
                json.dumps(ground_truth_value), encoding="utf-8"
            )
            with self.assertRaisesRegex(PocRunRecordError, "Scene Snapshot"):
                score_prediction(
                    record.directory,
                    ground_truth_path=mismatched_ground_truth,
                    output_path=root / "mismatched-score.json",
                    office_source_ply_path=source_ply,
                )

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

            with self.assertRaisesRegex(
                PocRunRecordError, "(byte count|hash) mismatch"
            ):
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
                prompt_log=[{"operation": "New"}, {"operation": "Refine"}],
                frozen_prompt_log=[
                    {"operation": "New"},
                    {"operation": "New"},
                ],
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
                benchmark_target_id="controlled-overlap",
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
            self.assertEqual(
                sealed_prompt_log["frozenEntries"],
                [{"operation": "New"}, {"operation": "New"}],
            )
            self.assertEqual(
                sealed_prompt_log["sessionMaterialization"],
                {
                    "kind": "initial-new-points-to-primary-track/v1",
                    "reason": "The session contract allows exactly one New operation.",
                },
            )
            self.assertEqual(sealed_prompt_log["targetId"], "controlled-overlap")


if __name__ == "__main__":
    unittest.main()
