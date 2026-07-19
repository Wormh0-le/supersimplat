"""Blind PoC Trial records and independent scoring.

Prediction sealing deliberately has no Ground Truth parameter.  The scorer is
the first boundary that accepts Ground Truth, and it verifies the immutable
prediction seal before opening it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence
import uuid


REQUIRED_PREDICTION_ARTIFACTS = (
    "sceneSnapshot",
    "benchmarkPromptLog",
    "frameSet",
    "maskSet",
    "candidateObjectSelection",
    "evidenceSnapshot",
    "coverageReport",
    "modelManifest",
    "runtimeManifest",
    "dependencyLock",
    "renderPolicy",
    "correctionOutcomes",
    "timingAndVram",
    "internalDiagnostics",
)
# Reserved for a future verified browser-side producer. It remains optional so
# older sealed predictions can still be independently scored and reported as
# failed; the current scorer never treats it as sufficient acceptance proof.
OPTIONAL_PREDICTION_ARTIFACTS = ("browserAcceptance",)
REQUIRED_BINDINGS = (
    "trialId",
    "protocolVersion",
    "deterministicSeed",
    "terminalState",
)
COMPLETE_REQUIRED_BINDINGS = REQUIRED_BINDINGS + (
    "requestId",
    "sessionId",
    "targetSplatId",
    "sceneId",
    "sceneVersion",
    "operation",
    "correctionRound",
    "promptLogRevision",
    "frameSetVersion",
    "renderConfigVersion",
    "modelManifestDigest",
)


class PocRunRecordError(ValueError):
    """A PoC Trial cannot be sealed or independently scored."""


@dataclass(frozen=True)
class SealedPrediction:
    directory: Path
    manifest_path: Path
    seal_path: Path
    manifest_sha256: str


@dataclass(frozen=True)
class SealedScoredRun:
    """Immutable final record that binds one score to one blind prediction."""

    directory: Path
    manifest_path: Path
    seal_path: Path
    manifest_sha256: str


@dataclass(frozen=True)
class _VerifiedPrediction:
    """Byte snapshots verified before the scorer opens Ground Truth."""

    directory: Path
    manifest: dict[str, object]
    manifest_sha256: str
    seal_sha256: str
    artifacts: Mapping[str, dict[str, object]]


@dataclass(frozen=True)
class _PromptLogBinding:
    """Canonical hashes that bind each completed request to a log prefix."""

    entry_count: int
    frozen_entries_sha256: str
    session_entries_sha256: str
    prefix_sha256s: tuple[str, ...]
    canonical_hashes_bound: bool


@dataclass(frozen=True)
class _RegisteredTrial:
    target_id: str
    benchmark_kind: str
    ground_truth_path: Path
    ground_truth_sha256: str
    prompt_log_sha256: str | None
    prompt_log_entries_sha256: str | None
    scene_snapshot: Mapping[str, object] | None
    execution_profile: Mapping[str, object] | None
    required_seeds: frozenset[str]
    availability: str
    blocked_reason: str | None


@dataclass(frozen=True)
class _PocTrialRegistry:
    sha256: str
    targets: Mapping[str, _RegisteredTrial]


def seal_prediction(
    output_directory: Path,
    *,
    artifacts: Mapping[str, Path],
    bindings: Mapping[str, object],
) -> SealedPrediction:
    """Atomically persist and seal all blind prediction artifacts."""

    allowed_artifacts = set(REQUIRED_PREDICTION_ARTIFACTS) | set(
        OPTIONAL_PREDICTION_ARTIFACTS
    )
    missing_artifacts = sorted(set(REQUIRED_PREDICTION_ARTIFACTS) - set(artifacts))
    unexpected_artifacts = sorted(set(artifacts) - allowed_artifacts)
    if missing_artifacts or unexpected_artifacts:
        raise PocRunRecordError(
            "prediction artifacts must match the required set; "
            f"missing={missing_artifacts}, unexpected={unexpected_artifacts}"
        )
    missing_bindings = [
        name
        for name in COMPLETE_REQUIRED_BINDINGS
        if not _nonempty_binding(bindings.get(name))
    ]
    if missing_bindings:
        raise PocRunRecordError(
            f"prediction bindings are missing required fields: {', '.join(missing_bindings)}"
        )
    for source in artifacts.values():
        if "ground" in source.name.lower() and "truth" in source.name.lower():
            raise PocRunRecordError(
                "Ground Truth cannot enter the blind prediction sealing boundary"
            )
        if not source.is_file():
            raise PocRunRecordError(f"prediction artifact does not exist: {source}")
    # A complete record's nested policy identities are checked again by the
    # independent scorer.  Failed and cancelled records are never scored, so
    # require their sealed Render Policy to retain the same binding here.
    if bindings.get("terminalState") != "complete":
        _validate_policy_bindings(
            bindings,
            render_policy=_read_json_object(
                artifacts["renderPolicy"], "renderPolicy artifact"
            ),
        )
    if output_directory.exists():
        raise PocRunRecordError(
            f"refusing to overwrite an existing PoC Run Record: {output_directory}"
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = (
        output_directory.parent / f".{output_directory.name}.staging-{uuid.uuid4().hex}"
    )
    artifact_directory = staging / "artifacts"
    artifact_directory.mkdir(parents=True)
    try:
        artifact_records: dict[str, dict[str, object]] = {}
        for name in (*REQUIRED_PREDICTION_ARTIFACTS, *OPTIONAL_PREDICTION_ARTIFACTS):
            if name not in artifacts:
                continue
            source = artifacts[name]
            suffix = source.suffix if source.suffix else ".bin"
            destination = artifact_directory / f"{name}{suffix}"
            shutil.copyfile(source, destination)
            artifact_records[name] = {
                "path": destination.relative_to(staging).as_posix(),
                "sha256": f"sha256:{_sha256(destination)}",
                "bytes": destination.stat().st_size,
            }

        manifest_path = staging / "prediction-manifest.json"
        _write_json(
            manifest_path,
            {
                "schemaVersion": 1,
                "status": (
                    "prediction-complete"
                    if bindings["terminalState"] == "complete"
                    else "prediction-failed"
                ),
                "bindings": dict(bindings),
                "artifacts": artifact_records,
            },
        )
        manifest_sha256 = f"sha256:{_sha256(manifest_path)}"
        seal_path = staging / "prediction-seal.json"
        _write_json(
            seal_path,
            {
                "schemaVersion": 1,
                "status": "sealed-before-ground-truth",
                "manifest": manifest_path.name,
                "manifestSha256": manifest_sha256,
            },
        )
        os.replace(staging, output_directory)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return SealedPrediction(
        directory=output_directory,
        manifest_path=output_directory / manifest_path.name,
        seal_path=output_directory / seal_path.name,
        manifest_sha256=manifest_sha256,
    )


def score_prediction(
    prediction_directory: Path,
    *,
    ground_truth_path: Path,
    output_path: Path,
    office_source_ply_path: Path | None = None,
    benchmark_registry_path: Path | None = None,
) -> dict[str, object]:
    """Verify a sealed blind prediction, then independently open and score truth."""

    output_path = output_path.resolve()
    _reject_output_inside_scored_record(output_path)
    result, _ = _score_prediction_snapshot(
        prediction_directory,
        ground_truth_path=ground_truth_path,
        output_path=output_path,
        office_source_ply_path=office_source_ply_path,
        benchmark_registry_path=benchmark_registry_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, result)
    return result


def score_and_seal_prediction(
    prediction_directory: Path,
    *,
    ground_truth_path: Path,
    output_path: Path,
    final_record_directory: Path,
    benchmark_registry_path: Path,
    office_source_ply_path: Path | None = None,
) -> tuple[dict[str, object], SealedScoredRun]:
    """Independently score a prediction and atomically seal the final record."""

    output_path = output_path.resolve()
    prediction_directory = prediction_directory.resolve()
    final_record_directory = final_record_directory.resolve()
    _reject_output_inside_scored_record(output_path)
    if final_record_directory.exists():
        raise PocRunRecordError(
            f"refusing to overwrite an existing scored PoC Run Record: {final_record_directory}"
        )
    if final_record_directory.is_relative_to(prediction_directory) or (
        prediction_directory.is_relative_to(final_record_directory)
    ):
        raise PocRunRecordError(
            "final scored Run Record must be separate from the blind prediction"
        )
    if (
        output_path == final_record_directory
        or output_path.is_relative_to(final_record_directory)
        or final_record_directory.is_relative_to(output_path)
    ):
        raise PocRunRecordError(
            "independent score output must remain outside the final scored Run Record"
        )
    result, prediction = _score_prediction_snapshot(
        prediction_directory,
        ground_truth_path=ground_truth_path,
        output_path=output_path,
        office_source_ply_path=office_source_ply_path,
        benchmark_registry_path=benchmark_registry_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, result)
    return result, _seal_scored_run(
        final_record_directory,
        prediction=prediction,
        score=result,
        registry=_load_poc_trial_registry(benchmark_registry_path),
    )


def _score_prediction_snapshot(
    prediction_directory: Path,
    *,
    ground_truth_path: Path,
    output_path: Path,
    office_source_ply_path: Path | None,
    benchmark_registry_path: Path | None,
) -> tuple[dict[str, object], _VerifiedPrediction]:
    prediction_directory = prediction_directory.resolve()
    ground_truth_path = ground_truth_path.resolve()
    output_path = output_path.resolve()
    if ground_truth_path.is_relative_to(prediction_directory):
        raise PocRunRecordError(
            "Ground Truth must remain outside the sealed prediction"
        )
    if output_path.is_relative_to(prediction_directory):
        raise PocRunRecordError(
            "independent scores must not modify the sealed prediction"
        )
    _reject_output_collision(
        output_path, ground_truth_path, "Benchmark Ground Truth"
    )
    _reject_prediction_output_collisions(output_path, prediction_directory)

    prediction = _verified_prediction(prediction_directory)
    registry = None
    if benchmark_registry_path is not None:
        _reject_output_collision(
            output_path, benchmark_registry_path, "PoC Trial registry"
        )
        registry = _load_poc_trial_registry(benchmark_registry_path)
    candidate = prediction.artifacts["candidateObjectSelection"]
    scene_snapshot = prediction.artifacts["sceneSnapshot"]
    benchmark_prompt_log = prediction.artifacts["benchmarkPromptLog"]
    frame_set = prediction.artifacts["frameSet"]

    # This read intentionally occurs only after every prediction hash passed.
    ground_truth_bytes = _read_file_bytes(ground_truth_path, "Benchmark Ground Truth")
    ground_truth = _read_json_bytes(ground_truth_bytes, "Benchmark Ground Truth")
    ground_truth_sha256 = f"sha256:{_sha256_bytes(ground_truth_bytes)}"
    selected, rejected, uncertain = _classification_sets(
        candidate,
        selected_key="selectedStableGaussianIds",
        rejected_key="rejectedStableGaussianIds",
        uncertain_key="uncertainStableGaussianIds",
        label="Candidate Object Selection",
    )
    if "labels" in ground_truth:
        target_id = _office_target_id(ground_truth)
        prompt_log_binding = _validate_benchmark_prompt_log(
            benchmark_prompt_log,
            expected_target_id=target_id,
            frame_set=frame_set,
        )
        if registry is not None:
            _validate_registered_trial(
                registry,
                prediction=prediction,
                target_id=target_id,
                benchmark_kind="office",
                ground_truth_sha256=ground_truth_sha256,
                benchmark_prompt_log=benchmark_prompt_log,
                prompt_log_binding=prompt_log_binding,
            )
        result = _score_office_prediction(
            manifest_sha256=prediction.manifest_sha256,
            ground_truth_path=ground_truth_path,
            ground_truth_sha256=ground_truth_sha256,
            ground_truth=ground_truth,
            scene_snapshot=scene_snapshot,
            office_source_ply_path=office_source_ply_path,
            output_path=output_path,
            selected=selected,
            rejected=rejected,
            uncertain=uncertain,
        )
        default_path_gate = result["officeGatePassed"]
    else:
        target_id = "controlled-overlap"
        prompt_log_binding = _validate_benchmark_prompt_log(
            benchmark_prompt_log,
            expected_target_id=target_id,
            frame_set=frame_set,
        )
        if registry is not None:
            _validate_registered_trial(
                registry,
                prediction=prediction,
                target_id=target_id,
                benchmark_kind="controlled-overlap",
                ground_truth_sha256=ground_truth_sha256,
                benchmark_prompt_log=benchmark_prompt_log,
                prompt_log_binding=prompt_log_binding,
            )
        result = _score_controlled_overlap_prediction(
            manifest_sha256=prediction.manifest_sha256,
            ground_truth_sha256=ground_truth_sha256,
            ground_truth=ground_truth,
            selected=selected,
            rejected=rejected,
            uncertain=uncertain,
        )
        default_path_gate = result["controlledOverlapGatePassed"]
    if not isinstance(default_path_gate, bool):
        raise PocRunRecordError("independent score did not declare a benchmark gate")
    if registry is not None:
        result["benchmarkRegistrySha256"] = registry.sha256
        result["benchmarkTargetId"] = target_id
    result["gateReport"] = _trial_gate_report(
        prediction,
        default_path_gate_passed=default_path_gate,
        prompt_log_binding=prompt_log_binding,
        registry_bound=registry is not None,
        seed_policy=(
            _registered_seed_policy(registry.targets.get(target_id))
            if registry is not None
            else None
        ),
    )
    return result, prediction


def _load_poc_trial_registry(path: Path) -> _PocTrialRegistry:
    """Load the frozen target, Ground Truth, prompt, and seed contract."""

    registry_bytes = _read_file_bytes(path, "PoC Trial registry")
    registry = _read_json_bytes(registry_bytes, "PoC Trial registry")
    if registry.get("schemaVersion") != 1:
        raise PocRunRecordError("PoC Trial registry schema is unsupported")
    if not _nonempty_string(registry.get("benchmarkId")):
        raise PocRunRecordError("PoC Trial registry benchmark ID is invalid")
    targets = registry.get("targets")
    if not isinstance(targets, list) or not targets:
        raise PocRunRecordError("PoC Trial registry targets are invalid")
    parsed_targets: dict[str, _RegisteredTrial] = {}
    for value in targets:
        if not isinstance(value, Mapping):
            raise PocRunRecordError("PoC Trial registry targets are invalid")
        target_id = value.get("targetId")
        benchmark_kind = value.get("benchmarkKind")
        availability = value.get("availability")
        ground_truth = value.get("groundTruth")
        prompt_log = value.get("promptLog")
        scene_snapshot = value.get("sceneSnapshot")
        execution_profile = value.get("executionProfile")
        required_seeds = value.get("requiredSeeds")
        if (
            not _nonempty_string(target_id)
            or target_id in parsed_targets
            or benchmark_kind not in {"controlled-overlap", "office"}
            or availability not in {"ready", "blocked"}
            or not isinstance(ground_truth, Mapping)
            or not _nonempty_string(ground_truth.get("path"))
            or not _sha256_reference(ground_truth.get("sha256"))
            or not isinstance(prompt_log, Mapping)
            or not isinstance(required_seeds, list)
            or len(required_seeds) != 3
            or any(not _nonempty_string(seed) for seed in required_seeds)
            or len(set(required_seeds)) != len(required_seeds)
        ):
            raise PocRunRecordError("PoC Trial registry target is invalid")
        prompt_log_sha256 = prompt_log.get("sha256")
        prompt_log_entries_sha256 = prompt_log.get("entriesSha256")
        blocked_reason = value.get("blockedReason")
        if availability == "ready":
            if (
                prompt_log.get("status") != "frozen-point-only"
                or not _sha256_reference(prompt_log_sha256)
                or not _sha256_reference(prompt_log_entries_sha256)
                or not _valid_registered_scene_snapshot(scene_snapshot)
                or not _valid_registered_execution_profile(execution_profile)
                or blocked_reason is not None
            ):
                raise PocRunRecordError("ready PoC Trial registry target is invalid")
        elif (
            prompt_log.get("status") != "missing-frozen-point-only"
            or prompt_log_sha256 is not None
            or prompt_log_entries_sha256 is not None
            or scene_snapshot is not None
            or execution_profile is not None
            or not _nonempty_string(blocked_reason)
        ):
            raise PocRunRecordError("blocked PoC Trial registry target is invalid")
        parsed_targets[target_id] = _RegisteredTrial(
            target_id=target_id,
            benchmark_kind=benchmark_kind,
            ground_truth_path=_registered_fixture_path(
                path, ground_truth["path"], "Benchmark Ground Truth"
            ),
            ground_truth_sha256=ground_truth["sha256"],
            prompt_log_sha256=prompt_log_sha256,
            prompt_log_entries_sha256=prompt_log_entries_sha256,
            scene_snapshot=dict(scene_snapshot)
            if isinstance(scene_snapshot, Mapping)
            else None,
            execution_profile=dict(execution_profile)
            if isinstance(execution_profile, Mapping)
            else None,
            required_seeds=frozenset(required_seeds),
            availability=availability,
            blocked_reason=blocked_reason,
        )
    return _PocTrialRegistry(
        sha256=f"sha256:{_sha256_bytes(registry_bytes)}",
        targets=parsed_targets,
    )


def _registered_fixture_path(
    registry_path: Path, value: object, label: str
) -> Path:
    if not _nonempty_string(value):
        raise PocRunRecordError(f"PoC Trial registry {label} path is invalid")
    fixture_path = (registry_path.parent / value).resolve()
    if not fixture_path.is_relative_to(registry_path.parent.resolve()):
        raise PocRunRecordError(f"PoC Trial registry {label} path escapes its directory")
    return fixture_path


def _valid_registered_scene_snapshot(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    return (
        _nonempty_string(value.get("targetSplatId"))
        and _nonempty_string(value.get("sceneId"))
        and _sha256_reference(value.get("sceneVersion"))
        and _positive_int(value.get("gaussianCount"))
        and value.get("stableIdSchema") == "uint32"
    )


def _valid_registered_execution_profile(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    model = value.get("model")
    runtime = value.get("runtime")
    render = value.get("render")
    seed_policy = value.get("seedPolicy")
    evidence_policy = render.get("evidencePolicy") if isinstance(render, Mapping) else None
    return (
        _nonempty_string(value.get("protocolVersion"))
        and isinstance(model, Mapping)
        and _nonempty_string(model.get("adapterId"))
        and _sha256_reference(model.get("digest"))
        and _sha256_reference(model.get("checkpointDigest"))
        and isinstance(runtime, Mapping)
        and _sha256_reference(runtime.get("lockDigest"))
        and isinstance(render, Mapping)
        and _nonempty_string(render.get("renderConfigVersion"))
        and isinstance(evidence_policy, Mapping)
        and _nonempty_string(evidence_policy.get("id"))
        and evidence_policy.get("renderConfigVersion")
        == render.get("renderConfigVersion")
        and _valid_registered_seed_policy(seed_policy)
    )


def _valid_registered_seed_policy(value: object) -> bool:
    """Accept only the versioned derivation the scorer can independently replay."""

    return (
        isinstance(value, Mapping)
        and value.get("seedDerivation") == "sha256-utf8-first-u32be/v1"
        and value.get("algorithmDeterminism") in {"enforced", "not-forced"}
    )


def _registered_seed_policy(
    target: _RegisteredTrial | None,
) -> Mapping[str, object] | None:
    if target is None or not isinstance(target.execution_profile, Mapping):
        return None
    seed_policy = target.execution_profile.get("seedPolicy")
    return seed_policy if isinstance(seed_policy, Mapping) else None


def _validate_registered_trial(
    registry: _PocTrialRegistry,
    *,
    prediction: _VerifiedPrediction,
    target_id: str,
    benchmark_kind: str,
    ground_truth_sha256: str,
    benchmark_prompt_log: Mapping[str, object],
    prompt_log_binding: _PromptLogBinding,
) -> None:
    target = registry.targets.get(target_id)
    if target is None or target.benchmark_kind != benchmark_kind:
        raise PocRunRecordError("trial target is not in the canonical PoC registry")
    if target.availability != "ready":
        raise PocRunRecordError(
            f"canonical PoC target is blocked: {target.blocked_reason}"
        )
    if ground_truth_sha256 != target.ground_truth_sha256:
        raise PocRunRecordError("Benchmark Ground Truth is not the registered fixture")
    bindings = prediction.manifest.get("bindings")
    if not isinstance(bindings, Mapping) or bindings.get("deterministicSeed") not in (
        target.required_seeds
    ):
        raise PocRunRecordError("trial does not use a prescribed fixed seed")
    frozen_source = benchmark_prompt_log.get("frozenSource")
    if not isinstance(frozen_source, Mapping) or frozen_source.get("sha256") != (
        target.prompt_log_sha256
    ):
        raise PocRunRecordError("Benchmark Prompt Log is not the registered frozen input")
    if prompt_log_binding.frozen_entries_sha256 != target.prompt_log_entries_sha256:
        raise PocRunRecordError(
            "Benchmark Prompt Log frozen entries are not the registered input"
        )
    if not _registered_scene_matches(target, prediction, bindings):
        raise PocRunRecordError("trial does not use the canonical Scene Snapshot")
    if not _registered_execution_profile_matches(target, prediction, bindings):
        raise PocRunRecordError(
            "trial does not use the canonical default execution profile"
        )


def _registered_scene_matches(
    target: _RegisteredTrial,
    prediction: _VerifiedPrediction,
    bindings: Mapping[str, object],
) -> bool:
    expected = target.scene_snapshot
    scene = prediction.artifacts.get("sceneSnapshot")
    if not isinstance(expected, Mapping) or not isinstance(scene, Mapping):
        return False
    return (
        bindings.get("targetSplatId") == expected.get("targetSplatId")
        and bindings.get("sceneId") == expected.get("sceneId")
        and bindings.get("sceneVersion") == expected.get("sceneVersion")
        and scene.get("sceneId") == expected.get("sceneId")
        and scene.get("sceneVersion") == expected.get("sceneVersion")
        and scene.get("gaussianCount") == expected.get("gaussianCount")
        and scene.get("stableIdSchema") == expected.get("stableIdSchema")
    )


def _registered_execution_profile_matches(
    target: _RegisteredTrial,
    prediction: _VerifiedPrediction,
    bindings: Mapping[str, object],
) -> bool:
    expected = target.execution_profile
    model = prediction.artifacts.get("modelManifest")
    runtime = prediction.artifacts.get("runtimeManifest")
    render_policy = prediction.artifacts.get("renderPolicy")
    if not (
        isinstance(expected, Mapping)
        and isinstance(model, Mapping)
        and isinstance(runtime, Mapping)
        and isinstance(render_policy, Mapping)
    ):
        return False
    expected_model = expected.get("model")
    expected_runtime = expected.get("runtime")
    expected_render = expected.get("render")
    expected_policy = (
        expected_render.get("evidencePolicy")
        if isinstance(expected_render, Mapping)
        else None
    )
    runtime_release = runtime.get("release")
    policy = render_policy.get("evidencePolicy")
    return (
        isinstance(expected_model, Mapping)
        and isinstance(expected_runtime, Mapping)
        and isinstance(expected_render, Mapping)
        and isinstance(expected_policy, Mapping)
        and isinstance(runtime_release, Mapping)
        and isinstance(policy, Mapping)
        and bindings.get("protocolVersion") == expected.get("protocolVersion")
        and runtime.get("protocolVersion") == expected.get("protocolVersion")
        and bindings.get("modelManifestDigest") == expected_model.get("digest")
        and model.get("adapterId") == expected_model.get("adapterId")
        and model.get("digest") == expected_model.get("digest")
        and model.get("checkpointDigest") == expected_model.get("checkpointDigest")
        and runtime_release.get("lockDigest") == expected_runtime.get("lockDigest")
        and bindings.get("renderConfigVersion")
        == expected_render.get("renderConfigVersion")
        and render_policy.get("renderConfigVersion")
        == expected_render.get("renderConfigVersion")
        and policy.get("id") == expected_policy.get("id")
        and policy.get("renderConfigVersion")
        == expected_policy.get("renderConfigVersion")
    )


def _recompute_registered_score(
    target: _RegisteredTrial,
    prediction: _VerifiedPrediction,
    *,
    registry: _PocTrialRegistry,
    prompt_log_binding: _PromptLogBinding,
) -> dict[str, object]:
    """Re-score a final record from the registry's frozen Ground Truth."""

    ground_truth_bytes = _read_file_bytes(
        target.ground_truth_path, "registered Benchmark Ground Truth"
    )
    ground_truth_sha256 = f"sha256:{_sha256_bytes(ground_truth_bytes)}"
    if ground_truth_sha256 != target.ground_truth_sha256:
        raise PocRunRecordError("registered Benchmark Ground Truth hash drifted")
    ground_truth = _read_json_bytes(
        ground_truth_bytes, "registered Benchmark Ground Truth"
    )
    candidate = prediction.artifacts.get("candidateObjectSelection")
    if not isinstance(candidate, Mapping):
        raise PocRunRecordError("copied Candidate Object Selection is invalid")
    selected, rejected, uncertain = _classification_sets(
        candidate,
        selected_key="selectedStableGaussianIds",
        rejected_key="rejectedStableGaussianIds",
        uncertain_key="uncertainStableGaussianIds",
        label="Candidate Object Selection",
    )
    if target.benchmark_kind != "controlled-overlap":
        raise PocRunRecordError(
            "registered office scoring requires its unavailable point-only trial path"
        )
    result = _score_controlled_overlap_prediction(
        manifest_sha256=prediction.manifest_sha256,
        ground_truth_sha256=ground_truth_sha256,
        ground_truth=ground_truth,
        selected=selected,
        rejected=rejected,
        uncertain=uncertain,
    )
    default_path_gate = result["controlledOverlapGatePassed"]
    if not isinstance(default_path_gate, bool):
        raise PocRunRecordError("registered independent score has no benchmark gate")
    result["benchmarkRegistrySha256"] = registry.sha256
    result["benchmarkTargetId"] = target.target_id
    result["gateReport"] = _trial_gate_report(
        prediction,
        default_path_gate_passed=default_path_gate,
        prompt_log_binding=prompt_log_binding,
        registry_bound=True,
        seed_policy=_registered_seed_policy(target),
    )
    return result


def assess_registered_trials(
    benchmark_registry_path: Path,
    *,
    final_record_directories: Sequence[Path],
    output_path: Path | None = None,
) -> dict[str, object]:
    """Apply the all-target, all-seed PoC rule without averages or rescue runs."""

    if output_path is not None:
        output_path = output_path.resolve()
        _reject_output_inside_scored_record(output_path)
    registry = _load_poc_trial_registry(benchmark_registry_path)
    records: dict[tuple[str, str], dict[str, object]] = {}
    invalid_records: list[dict[str, str]] = []
    duplicate_keys: set[tuple[str, str]] = set()
    for directory in final_record_directories:
        try:
            score, bindings = _verified_scored_run(directory, registry=registry)
            target_id = score.get("benchmarkTargetId")
            deterministic_seed = bindings.get("deterministicSeed")
            if not _nonempty_string(target_id) or not _nonempty_string(
                deterministic_seed
            ):
                raise PocRunRecordError("scored Run Record target or seed is invalid")
            key = (target_id, deterministic_seed)
            if key in records:
                duplicate_keys.add(key)
            records[key] = {
                "directory": str(directory),
                "score": score,
            }
        except PocRunRecordError as error:
            invalid_records.append({"directory": str(directory), "reason": str(error)})

    trials: list[dict[str, object]] = []
    for target in registry.targets.values():
        for seed in sorted(target.required_seeds):
            key = (target.target_id, seed)
            record = records.get(key)
            if target.availability != "ready":
                trials.append(
                    {
                        "targetId": target.target_id,
                        "deterministicSeed": seed,
                        "status": "fail",
                        "reason": target.blocked_reason,
                    }
                )
            elif key in duplicate_keys:
                trials.append(
                    {
                        "targetId": target.target_id,
                        "deterministicSeed": seed,
                        "status": "fail",
                        "reason": "multiple final records were supplied for one target and seed",
                    }
                )
            elif record is None:
                trials.append(
                    {
                        "targetId": target.target_id,
                        "deterministicSeed": seed,
                        "status": "fail",
                        "reason": "required final scored Run Record is missing",
                    }
                )
            else:
                score = record["score"]
                gate_report = score.get("gateReport") if isinstance(score, Mapping) else None
                status = (
                    "pass"
                    if isinstance(gate_report, Mapping)
                    and gate_report.get("overallStatus") == "pass"
                    else "fail"
                )
                trials.append(
                    {
                        "targetId": target.target_id,
                        "deterministicSeed": seed,
                        "status": status,
                        "finalRecord": record["directory"],
                    }
                )

    unexpected_records = [
        record
        for (target_id, seed), record in records.items()
        if target_id not in registry.targets
        or seed not in registry.targets[target_id].required_seeds
    ]
    acceptance_status = (
        "pass"
        if not invalid_records
        and not unexpected_records
        and all(trial["status"] == "pass" for trial in trials)
        else "fail"
    )
    result: dict[str, object] = {
        "schemaVersion": 1,
        "benchmarkRegistrySha256": registry.sha256,
        "trials": trials,
        "invalidRecords": invalid_records,
        "unexpectedRecords": unexpected_records,
        "acceptanceStatus": acceptance_status,
    }
    if output_path is not None:
        _reject_output_collision(output_path, benchmark_registry_path, "PoC Trial registry")
        for directory in final_record_directories:
            resolved_directory = directory.resolve()
            if output_path.is_relative_to(resolved_directory):
                raise PocRunRecordError(
                    "assessment output must remain outside a scored Run Record"
                )
            _reject_prediction_output_collisions(output_path, resolved_directory)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output_path, result)
    return result


def _verified_scored_run(
    directory: Path, *, registry: _PocTrialRegistry
) -> tuple[dict[str, object], Mapping[str, object]]:
    """Verify a final score together with its copied blind prediction record."""

    directory = directory.resolve()
    seal_bytes = _read_file_bytes(directory / "scored-run-seal.json", "scored Run Record seal")
    seal = _read_json_bytes(seal_bytes, "scored Run Record seal")
    if (
        seal.get("schemaVersion") != 1
        or seal.get("status") != "sealed-after-ground-truth"
        or seal.get("manifest") != "scored-run-manifest.json"
        or not _sha256_reference(seal.get("manifestSha256"))
    ):
        raise PocRunRecordError("scored Run Record seal is malformed")
    manifest_path = directory / "scored-run-manifest.json"
    manifest_bytes = _read_file_bytes(manifest_path, "scored Run Record manifest")
    manifest_sha256 = f"sha256:{_sha256_bytes(manifest_bytes)}"
    if manifest_sha256 != seal.get("manifestSha256"):
        raise PocRunRecordError("scored Run Record manifest hash mismatch")
    manifest = _read_json_bytes(manifest_bytes, "scored Run Record manifest")
    prediction = manifest.get("prediction")
    score_record = manifest.get("score")
    if (
        manifest.get("schemaVersion") != 1
        or manifest.get("status") != "scored"
        or not isinstance(prediction, Mapping)
        or prediction.get("path") != "prediction"
        or not _sha256_reference(prediction.get("manifestSha256"))
        or not _sha256_reference(prediction.get("sealSha256"))
        or not isinstance(prediction.get("bindings"), Mapping)
        or not isinstance(score_record, Mapping)
    ):
        raise PocRunRecordError("scored Run Record manifest is malformed")
    copied_prediction_path = (directory / "prediction").resolve()
    if not copied_prediction_path.is_relative_to(directory):
        raise PocRunRecordError("scored Run Record copied prediction escapes its directory")
    copied_prediction = _verified_prediction(copied_prediction_path)
    if (
        copied_prediction.manifest_sha256 != prediction.get("manifestSha256")
        or copied_prediction.seal_sha256 != prediction.get("sealSha256")
        or copied_prediction.manifest.get("bindings") != prediction.get("bindings")
    ):
        raise PocRunRecordError("scored Run Record copied prediction binding mismatch")
    score_path = score_record.get("path")
    if score_path != "artifacts/independent-score.json":
        raise PocRunRecordError("scored Run Record score path is invalid")
    resolved_score_path = (directory / score_path).resolve()
    if not resolved_score_path.is_relative_to(directory):
        raise PocRunRecordError("scored Run Record score escapes its directory")
    score_bytes = _read_file_bytes(resolved_score_path, "independent score")
    if (
        score_record.get("bytes") != len(score_bytes)
        or score_record.get("sha256") != f"sha256:{_sha256_bytes(score_bytes)}"
    ):
        raise PocRunRecordError("scored Run Record score hash mismatch")
    score = _read_json_bytes(score_bytes, "independent score")
    _validate_scored_run_score(score, copied_prediction.manifest_sha256)
    if score.get("groundTruthSha256") != score_record.get("groundTruthSha256"):
        raise PocRunRecordError("scored Run Record Ground Truth hash mismatch")
    if score.get("benchmarkRegistrySha256") != registry.sha256:
        raise PocRunRecordError(
            "scored Run Record does not bind the requested PoC Trial registry"
        )
    target_id = score.get("benchmarkTargetId")
    benchmark_prompt_log = copied_prediction.artifacts.get("benchmarkPromptLog")
    frame_set = copied_prediction.artifacts.get("frameSet")
    if not (
        isinstance(target_id, str)
        and isinstance(benchmark_prompt_log, Mapping)
        and isinstance(frame_set, Mapping)
    ):
        raise PocRunRecordError("scored Run Record has no bound Benchmark Prompt Log")
    prompt_log_binding = _validate_benchmark_prompt_log(
        benchmark_prompt_log,
        expected_target_id=target_id,
        frame_set=frame_set,
    )
    _validate_registered_trial(
        registry,
        prediction=copied_prediction,
        target_id=target_id,
        benchmark_kind=(
            "controlled-overlap" if "controlledOverlapGatePassed" in score else "office"
        ),
        ground_truth_sha256=score["groundTruthSha256"],
        benchmark_prompt_log=benchmark_prompt_log,
        prompt_log_binding=prompt_log_binding,
    )
    target = registry.targets.get(target_id)
    if target is None:
        raise PocRunRecordError("scored Run Record has an unregistered target")
    if score != _recompute_registered_score(
        target,
        copied_prediction,
        registry=registry,
        prompt_log_binding=prompt_log_binding,
    ):
        raise PocRunRecordError("scored Run Record score does not match the frozen evaluator")
    return score, copied_prediction.manifest["bindings"]


def _seal_scored_run(
    output_directory: Path,
    *,
    prediction: _VerifiedPrediction,
    score: Mapping[str, object],
    registry: _PocTrialRegistry,
) -> SealedScoredRun:
    """Atomically link an independent score to its immutable blind prediction.

    The prediction record remains immutable after Ground Truth opens.  This
    separate final record carries copies of the independent score and the
    exact prediction identities needed to audit their binding.
    """

    output_directory = output_directory.resolve()
    if output_directory.is_relative_to(prediction.directory) or (
        prediction.directory.is_relative_to(output_directory)
    ):
        raise PocRunRecordError(
            "final scored Run Record must be separate from the blind prediction"
        )
    _validate_scored_run_score(score, prediction.manifest_sha256)
    if score.get("benchmarkRegistrySha256") != registry.sha256:
        raise PocRunRecordError("independent score does not bind the canonical registry")
    expected_target_id = score.get("benchmarkTargetId")
    benchmark_prompt_log = prediction.artifacts.get("benchmarkPromptLog")
    if not isinstance(expected_target_id, str) or not isinstance(
        benchmark_prompt_log, Mapping
    ):
        raise PocRunRecordError("independent score has no canonical trial target")
    frame_set = prediction.artifacts.get("frameSet")
    if not isinstance(frame_set, Mapping):
        raise PocRunRecordError("independent score has no bound Benchmark Prompt Log")
    prompt_log_binding = _validate_benchmark_prompt_log(
        benchmark_prompt_log,
        expected_target_id=expected_target_id,
        frame_set=frame_set,
    )
    _validate_registered_trial(
        registry,
        prediction=prediction,
        target_id=expected_target_id,
        benchmark_kind=(
            "controlled-overlap"
            if "controlledOverlapGatePassed" in score
            else "office"
        ),
        ground_truth_sha256=score["groundTruthSha256"],
        benchmark_prompt_log=benchmark_prompt_log,
        prompt_log_binding=prompt_log_binding,
    )
    default_path_gate = score.get(
        "controlledOverlapGatePassed", score.get("officeGatePassed")
    )
    if not isinstance(default_path_gate, bool) or score.get("gateReport") != (
        _trial_gate_report(
            prediction,
            default_path_gate_passed=default_path_gate,
            prompt_log_binding=prompt_log_binding,
            registry_bound=True,
            seed_policy=_registered_seed_policy(registry.targets.get(expected_target_id)),
        )
    ):
        raise PocRunRecordError("independent score gate report is inconsistent")
    if output_directory.exists():
        raise PocRunRecordError(
            f"refusing to overwrite an existing scored PoC Run Record: {output_directory}"
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = (
        output_directory.parent
        / f".{output_directory.name}.staging-{uuid.uuid4().hex}"
    )
    score_directory = staging / "artifacts"
    score_destination = score_directory / "independent-score.json"
    try:
        copied_prediction_directory = staging / "prediction"
        shutil.copytree(prediction.directory, copied_prediction_directory)
        copied_prediction = _verified_prediction(copied_prediction_directory)
        if (
            copied_prediction.manifest_sha256 != prediction.manifest_sha256
            or copied_prediction.seal_sha256 != prediction.seal_sha256
            or copied_prediction.manifest.get("bindings")
            != prediction.manifest.get("bindings")
        ):
            raise PocRunRecordError(
                "sealed prediction changed while creating the final Run Record"
            )
        score_directory.mkdir(parents=True)
        _write_json(score_destination, score)
        score_sha256 = f"sha256:{_sha256(score_destination)}"
        manifest_path = staging / "scored-run-manifest.json"
        _write_json(
            manifest_path,
            {
                "schemaVersion": 1,
                "status": "scored",
                "prediction": {
                    "path": copied_prediction_directory.relative_to(staging).as_posix(),
                    "manifestSha256": prediction.manifest_sha256,
                    "sealSha256": prediction.seal_sha256,
                    "bindings": prediction.manifest["bindings"],
                },
                "score": {
                    "path": score_destination.relative_to(staging).as_posix(),
                    "sha256": score_sha256,
                    "bytes": score_destination.stat().st_size,
                    "groundTruthSha256": score["groundTruthSha256"],
                },
            },
        )
        manifest_sha256 = f"sha256:{_sha256(manifest_path)}"
        seal_path = staging / "scored-run-seal.json"
        _write_json(
            seal_path,
            {
                "schemaVersion": 1,
                "status": "sealed-after-ground-truth",
                "manifest": manifest_path.name,
                "manifestSha256": manifest_sha256,
            },
        )
        os.replace(staging, output_directory)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return SealedScoredRun(
        directory=output_directory,
        manifest_path=output_directory / manifest_path.name,
        seal_path=output_directory / seal_path.name,
        manifest_sha256=manifest_sha256,
    )


def _validate_scored_run_score(
    score: Mapping[str, object], prediction_manifest_sha256: str
) -> None:
    if score.get("schemaVersion") != 1:
        raise PocRunRecordError("independent score schema is unsupported")
    if score.get("predictionManifestSha256") != prediction_manifest_sha256:
        raise PocRunRecordError(
            "independent score does not bind the sealed prediction manifest"
        )
    if not _sha256_reference(score.get("groundTruthSha256")):
        raise PocRunRecordError("independent score Ground Truth hash is invalid")
    if not _sha256_reference(score.get("benchmarkRegistrySha256")) or not _nonempty_string(
        score.get("benchmarkTargetId")
    ):
        raise PocRunRecordError("independent score has no canonical benchmark binding")
    metrics = score.get("metrics")
    if not isinstance(metrics, Mapping):
        raise PocRunRecordError("independent score metrics are invalid")
    if "controlledOverlapGatePassed" in score:
        _validate_controlled_score(score, metrics)
        return
    if "officeGatePassed" in score:
        _validate_office_score(score, metrics)
        return
    raise PocRunRecordError("independent score must declare one benchmark gate")


def _validate_controlled_score(
    score: Mapping[str, object], metrics: Mapping[str, object]
) -> None:
    if set(score) != {
        "schemaVersion",
        "benchmarkRegistrySha256",
        "benchmarkTargetId",
        "predictionManifestSha256",
        "groundTruthSha256",
        "metrics",
        "controlledOverlapGatePassed",
        "gateReport",
    } or set(metrics) != {
        "intersectionOverUnion",
        "precision",
        "recall",
        "rearSurfaceRecall",
        "selectedDistractorCount",
    }:
        raise PocRunRecordError("controlled independent score schema is invalid")
    if (
        not _finite_probability(metrics["intersectionOverUnion"])
        or not _finite_probability(metrics["precision"])
        or not _finite_probability(metrics["recall"])
        or not _finite_probability(metrics["rearSurfaceRecall"])
        or not _nonnegative_int(metrics["selectedDistractorCount"])
        or not isinstance(score["controlledOverlapGatePassed"], bool)
    ):
        raise PocRunRecordError("controlled independent score metrics are invalid")
    expected_gate = (
        metrics["intersectionOverUnion"] >= 0.9
        and metrics["precision"] >= 0.9
        and metrics["recall"] >= 0.9
        and metrics["rearSurfaceRecall"] >= 0.9
        and metrics["selectedDistractorCount"] <= 81
    )
    if score["controlledOverlapGatePassed"] != expected_gate:
        raise PocRunRecordError("controlled independent score gate is inconsistent")


def _validate_office_score(
    score: Mapping[str, object], metrics: Mapping[str, object]
) -> None:
    if set(score) != {
        "schemaVersion",
        "benchmarkKind",
        "targetId",
        "benchmarkRegistrySha256",
        "benchmarkTargetId",
        "predictionManifestSha256",
        "groundTruthSha256",
        "groundTruthLabelsSha256",
        "officeSourcePlySha256",
        "metrics",
        "officeGatePassed",
        "gateReport",
    } or set(metrics) != {
        "intersectionOverUnion",
        "precision",
        "recall",
        "truthSelectedUncertainCount",
        "truthSelectedUncertainRate",
        "scopeUncertainCount",
        "scopeUncertainRate",
    }:
        raise PocRunRecordError("office independent score schema is invalid")
    if (
        score.get("benchmarkKind") != "office"
        or not isinstance(score.get("targetId"), str)
        or not score["targetId"].strip()
        or score.get("benchmarkTargetId") != score.get("targetId")
        or not _sha256_reference(score.get("groundTruthLabelsSha256"))
        or not _sha256_reference(score.get("officeSourcePlySha256"))
        or not _finite_probability(metrics["intersectionOverUnion"])
        or not _finite_probability(metrics["precision"])
        or not _finite_probability(metrics["recall"])
        or not _nonnegative_int(metrics["truthSelectedUncertainCount"])
        or not _finite_probability(metrics["truthSelectedUncertainRate"])
        or not _nonnegative_int(metrics["scopeUncertainCount"])
        or not _finite_probability(metrics["scopeUncertainRate"])
        or not isinstance(score["officeGatePassed"], bool)
    ):
        raise PocRunRecordError("office independent score metrics are invalid")
    if score["officeGatePassed"] != (metrics["intersectionOverUnion"] >= 0.8):
        raise PocRunRecordError("office independent score gate is inconsistent")


def _trial_gate_report(
    prediction: _VerifiedPrediction,
    *,
    default_path_gate_passed: bool,
    prompt_log_binding: _PromptLogBinding,
    registry_bound: bool,
    seed_policy: Mapping[str, object] | None,
) -> dict[str, object]:
    """Report every acceptance axis as pass or fail.

    Missing browser-owned evidence remains diagnostically unassessed, but its
    formal gate is fail: a trial cannot pass by omitting an acceptance axis.
    """

    correction_status, successful_rounds = _correction_round_gate(
        prediction,
        prompt_log_binding=prompt_log_binding,
    )
    completeness_errors = _record_completeness_errors(
        prediction,
        correction_status=correction_status,
        prompt_log_binding=prompt_log_binding,
        registry_bound=registry_bound,
        seed_policy=seed_policy,
    )
    gates: dict[str, dict[str, object]] = {
        "recordCompleteness": {
            "status": "pass" if not completeness_errors else "fail",
            **(
                {}
                if not completeness_errors
                else {"reasons": completeness_errors}
            ),
        },
        "defaultPathCorrectness": {
            "status": "pass" if default_path_gate_passed else "fail"
        },
        "correctionRoundBound": {
            "status": correction_status,
            "successfulCorrectionRounds": successful_rounds,
        },
        "blindReadyJudgment": _browser_acceptance_gate(
            prediction,
            "blindReadyJudgment",
            "the Companion record has no blinded operator Ready judgment",
        ),
        "uncertaintyDisclosure": _browser_acceptance_gate(
            prediction,
            "uncertaintyDisclosure",
            "the Companion record has no editor acknowledgement evidence",
        ),
        "editorCompatibility": _browser_acceptance_gate(
            prediction,
            "editorCompatibility",
            "the Companion record has no Confirm/Cancel editor exercise",
        ),
    }
    statuses = [gate["status"] for gate in gates.values()]
    overall_status = "pass" if all(status == "pass" for status in statuses) else "fail"
    return {"gates": gates, "overallStatus": overall_status}


def _browser_acceptance_gate(
    prediction: _VerifiedPrediction, gate_name: str, missing_reason: str
) -> dict[str, object]:
    evidence = prediction.artifacts.get("browserAcceptance")
    if evidence is None:
        return {
            "status": "fail",
            "evidenceStatus": "unassessed",
            "reason": missing_reason,
        }
    return {
        "status": "fail",
        "evidenceStatus": "unverified",
        "reason": (
            "browser acceptance evidence has no verified editor-side producer; "
            "it cannot satisfy a formal PoC gate"
        ),
    }


def _record_completeness_errors(
    prediction: _VerifiedPrediction,
    *,
    correction_status: str,
    prompt_log_binding: _PromptLogBinding,
    registry_bound: bool,
    seed_policy: Mapping[str, object] | None,
) -> list[str]:
    """Return missing observability identities without blocking independent scoring.

    A sealed prediction can be authentic yet still be an incomplete acceptance
    record.  Keep that distinction visible in the final score: missing browser
    or transport evidence invalidates the trial, but does not justify hiding
    the independently measured accuracy result.
    """

    artifacts = prediction.artifacts
    runtime = artifacts.get("runtimeManifest")
    model = artifacts.get("modelManifest")
    render_policy = artifacts.get("renderPolicy")
    evidence = artifacts.get("evidenceSnapshot")
    coverage = artifacts.get("coverageReport")
    timing_and_vram = artifacts.get("timingAndVram")
    errors: list[str] = []

    if not isinstance(runtime, Mapping) or not _valid_companion_identity(
        runtime, prediction
    ):
        errors.append("Companion build and dependency-lock identity")

    if not isinstance(runtime, Mapping) or not _valid_browser_transport_profile(
        runtime.get("executionProfile")
    ):
        errors.append("reference browser/version and non-secret transport profile")

    if not isinstance(runtime, Mapping) or not _valid_runtime_seed_policy(
        runtime, prediction, seed_policy=seed_policy
    ):
        errors.append("effective runtime seed and determinism policy")

    if not isinstance(model, Mapping) or not (
        _nonempty_string(model.get("adapterId"))
        and _sha256_reference(model.get("checkpointDigest"))
        and _sha256_reference(model.get("digest"))
    ):
        errors.append("Model Manifest identity")

    if not _valid_evidence_policy_identity(render_policy, evidence):
        errors.append("Evidence Policy revision")

    if not isinstance(coverage, Mapping) or not _nonempty_string(
        coverage.get("status")
    ):
        errors.append("Coverage Report state")

    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("records"), list):
        errors.append("Evidence Snapshot uncertainty state")

    if not _valid_timing_and_vram(timing_and_vram):
        errors.append("per-stage timing and peak VRAM")

    if correction_status != "pass":
        errors.append("complete correction outcomes")
    if not _valid_prompt_log_execution_binding(prediction, prompt_log_binding):
        errors.append("frozen Prompt Log execution binding")
    if not registry_bound:
        errors.append("canonical PoC Trial registry binding")
    return errors


def _valid_companion_identity(
    runtime: Mapping[str, object], prediction: _VerifiedPrediction
) -> bool:
    bindings = prediction.manifest.get("bindings")
    artifact_records = prediction.manifest.get("artifacts")
    release = runtime.get("release")
    lock_record = (
        artifact_records.get("dependencyLock")
        if isinstance(artifact_records, Mapping)
        else None
    )
    return (
        _nonempty_string(runtime.get("companionVersion"))
        and _nonempty_string(runtime.get("serviceBuild"))
        and isinstance(bindings, Mapping)
        and runtime.get("protocolVersion") == bindings.get("protocolVersion")
        and isinstance(release, Mapping)
        and _sha256_reference(release.get("lockDigest"))
        and isinstance(lock_record, Mapping)
        and release.get("lockDigest") == lock_record.get("sha256")
    )


def _valid_runtime_seed_policy(
    runtime: Mapping[str, object],
    prediction: _VerifiedPrediction,
    *,
    seed_policy: Mapping[str, object] | None,
) -> bool:
    """Replay the registry's seed derivation before accepting runtime metadata."""

    bindings = prediction.manifest.get("bindings")
    randomness = runtime.get("randomness")
    if not (
        isinstance(bindings, Mapping)
        and isinstance(randomness, Mapping)
        and _valid_registered_seed_policy(seed_policy)
        and _nonempty_string(bindings.get("deterministicSeed"))
    ):
        return False
    declared_seed = bindings["deterministicSeed"]
    expected_effective_seed = int.from_bytes(
        hashlib.sha256(declared_seed.encode("utf-8")).digest()[:4], "big"
    )
    return (
        randomness.get("declaredSeed") == declared_seed
        and randomness.get("effectiveSeed") == expected_effective_seed
        and randomness.get("seedDerivation") == seed_policy.get("seedDerivation")
        and randomness.get("pythonRandomSeeded") is True
        and randomness.get("numpyRandomSeeded") is True
        and randomness.get("torchCpuSeeded") is True
        and randomness.get("torchCudaSeeded") is True
        and randomness.get("algorithmDeterminism")
        == seed_policy.get("algorithmDeterminism")
    )


def _valid_browser_transport_profile(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    browser = value.get("browser")
    transport = value.get("transport")
    if not (
        isinstance(browser, Mapping)
        and _nonempty_string(browser.get("family"))
        and _nonempty_string(browser.get("version"))
        and isinstance(transport, Mapping)
        and _nonempty_string(transport.get("kind"))
        and _nonempty_string(transport.get("endpointScope"))
    ):
        return False
    if not all(isinstance(key, str) for key in transport):
        return False
    return not any(
        sensitive_name in key.lower()
        for key in transport
        for sensitive_name in ("token", "secret", "password", "authorization", "cookie")
    )


def _valid_evidence_policy_identity(
    render_policy: object, evidence_snapshot: object
) -> bool:
    if not isinstance(render_policy, Mapping) or not isinstance(
        evidence_snapshot, Mapping
    ):
        return False
    render_policy_evidence = render_policy.get("evidencePolicy")
    snapshot_policy = evidence_snapshot.get("policy")
    if not isinstance(render_policy_evidence, Mapping) or not isinstance(
        snapshot_policy, Mapping
    ):
        return False
    return (
        _nonempty_string(render_policy_evidence.get("id"))
        and render_policy_evidence.get("id") == snapshot_policy.get("id")
        and render_policy_evidence.get("renderConfigVersion")
        == snapshot_policy.get("renderConfigVersion")
    )


def _valid_timing_and_vram(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    stage_seconds = value.get("stageSeconds")
    return (
        isinstance(stage_seconds, Mapping)
        and bool(stage_seconds)
        and all(
            _finite_nonnegative_number(seconds)
            for seconds in stage_seconds.values()
        )
        and _nonnegative_int(value.get("peakVramBytes"))
        and _nonempty_string(value.get("peakVramMeasurement"))
    )


def _valid_prompt_log_execution_binding(
    prediction: _VerifiedPrediction, prompt_log_binding: _PromptLogBinding
) -> bool:
    bindings = prediction.manifest.get("bindings")
    mask_set = prediction.artifacts.get("maskSet")
    return (
        prompt_log_binding.canonical_hashes_bound
        and isinstance(bindings, Mapping)
        and bindings.get("promptLogRevision") == prompt_log_binding.entry_count
        and isinstance(mask_set, Mapping)
        and mask_set.get("promptLogEntriesSha256")
        == prompt_log_binding.session_entries_sha256
    )


def _correction_round_gate(
    prediction: _VerifiedPrediction,
    *,
    prompt_log_binding: _PromptLogBinding,
) -> tuple[str, int]:
    bindings = prediction.manifest.get("bindings")
    correction_outcomes = prediction.artifacts.get("correctionOutcomes")
    if not isinstance(bindings, Mapping) or not isinstance(
        correction_outcomes, Mapping
    ):
        return "fail", 0
    final_round = bindings.get("correctionRound")
    outcomes = correction_outcomes.get("outcomes")
    if not _nonnegative_int(final_round) or not isinstance(outcomes, list):
        return "fail", 0
    successful_outcomes: list[tuple[str, int, object, int]] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            return "fail", 0
        operation = outcome.get("operation")
        correction_round = outcome.get("correctionRound")
        terminal_state = outcome.get("terminalState")
        request_id = outcome.get("requestId")
        prompt_log_revision = outcome.get("promptLogRevision")
        prompt_log_entries_sha256 = outcome.get("promptLogEntriesSha256")
        if (
            operation not in {"New", "Add", "Remove", "Refine"}
            or not _nonnegative_int(correction_round)
            or not isinstance(terminal_state, str)
            or not terminal_state
            or not _nonempty_string(request_id)
            or not _positive_int(prompt_log_revision)
            or prompt_log_revision > prompt_log_binding.entry_count
            or prompt_log_entries_sha256
            != prompt_log_binding.prefix_sha256s[prompt_log_revision - 1]
        ):
            return "fail", 0
        if terminal_state == "complete":
            successful_outcomes.append(
                (operation, correction_round, request_id, prompt_log_revision)
            )
    if not successful_outcomes:
        return "fail", 0
    new_rounds = [
        correction_round
        for operation, correction_round, _, _ in successful_outcomes
        if operation == "New"
    ]
    successful_corrections = [
        correction_round
        for operation, correction_round, _, _ in successful_outcomes
        if operation != "New"
    ]
    (
        final_operation,
        final_successful_round,
        final_request_id,
        final_prompt_log_revision,
    ) = successful_outcomes[-1]
    if (
        new_rounds != [0]
        or successful_corrections != list(range(1, final_round + 1))
        or final_successful_round != final_round
        or final_operation != bindings.get("operation")
        or final_request_id != bindings.get("requestId")
        or final_prompt_log_revision != prompt_log_binding.entry_count
        or bindings.get("promptLogRevision") != prompt_log_binding.entry_count
        or final_round > 5
    ):
        return "fail", len(successful_corrections)
    return "pass", len(successful_corrections)


def _score_controlled_overlap_prediction(
    *,
    manifest_sha256: str,
    ground_truth_sha256: str,
    ground_truth: Mapping[str, object],
    selected: set[int],
    rejected: set[int],
    uncertain: set[int],
) -> dict[str, object]:
    """Score the exact controlled front/back-overlap fixture."""

    truth_selected, truth_rejected, truth_ambiguous = _classification_sets(
        ground_truth,
        selected_key="selectedStableGaussianIds",
        rejected_key="rejectedStableGaussianIds",
        uncertain_key="ambiguousStableGaussianIds",
        label="Benchmark Ground Truth",
    )
    if (
        selected | rejected | uncertain
        != truth_selected | truth_rejected | truth_ambiguous
    ):
        raise PocRunRecordError(
            "Candidate Object Selection does not completely classify the Ground Truth universe"
        )
    rear_surface = _stable_id_set(
        ground_truth.get("rearSurfaceStableGaussianIds"),
        "Benchmark Ground Truth rearSurfaceStableGaussianIds",
    )
    distractors = _stable_id_set(
        ground_truth.get("distractorStableGaussianIds"),
        "Benchmark Ground Truth distractorStableGaussianIds",
    )
    if not rear_surface <= truth_selected:
        raise PocRunRecordError(
            "rear-surface Ground Truth must be a subset of selected truth"
        )
    if not distractors <= truth_rejected:
        raise PocRunRecordError(
            "distractor Ground Truth must be a subset of rejected truth"
        )

    scored_prediction = selected - truth_ambiguous
    intersection = len(scored_prediction & truth_selected)
    union = len(scored_prediction | truth_selected)
    metrics: dict[str, int | float] = {
        "intersectionOverUnion": _ratio(intersection, union),
        "precision": _ratio(intersection, len(scored_prediction)),
        "recall": _ratio(intersection, len(truth_selected)),
        "rearSurfaceRecall": _ratio(len(selected & rear_surface), len(rear_surface)),
        "selectedDistractorCount": len(selected & distractors),
    }
    result: dict[str, object] = {
        "schemaVersion": 1,
        "predictionManifestSha256": manifest_sha256,
        "groundTruthSha256": ground_truth_sha256,
        "metrics": metrics,
        "controlledOverlapGatePassed": (
            metrics["intersectionOverUnion"] >= 0.9
            and metrics["precision"] >= 0.9
            and metrics["recall"] >= 0.9
            and metrics["rearSurfaceRecall"] >= 0.9
            and metrics["selectedDistractorCount"] <= 81
        ),
    }
    return result


def _score_office_prediction(
    *,
    manifest_sha256: str,
    ground_truth_path: Path,
    ground_truth_sha256: str,
    ground_truth: Mapping[str, object],
    scene_snapshot: Mapping[str, object],
    office_source_ply_path: Path | None,
    output_path: Path,
    selected: set[int],
    rejected: set[int],
    uncertain: set[int],
) -> dict[str, object]:
    """Score only the frozen non-ambiguous office Ground Truth scope."""

    target_id = _office_target_id(ground_truth)
    source = _office_ground_truth_source(ground_truth)
    _validate_office_ground_truth_scene(source, scene_snapshot)
    if office_source_ply_path is not None:
        _reject_output_collision(
            output_path, office_source_ply_path, "office source PLY"
        )
    source_sha256 = _verified_office_source_ply(office_source_ply_path, source)
    labels = ground_truth.get("labels")
    if not isinstance(labels, Mapping):
        raise PocRunRecordError("office Benchmark Ground Truth labels are invalid")
    labels_bytes, labels_sha256 = _verified_office_labels_bytes(
        ground_truth_path, labels, output_path=output_path
    )
    truth_selected, truth_rejected, truth_ambiguous, scope = _office_label_sets(
        labels_bytes
    )
    if truth_selected | truth_rejected | truth_ambiguous != scope:
        raise PocRunRecordError(
            "office Benchmark Ground Truth labels must partition scope_ids"
        )
    _validate_office_label_counts(
        labels,
        selected=truth_selected,
        rejected=truth_rejected,
        ambiguous=truth_ambiguous,
        scope=scope,
    )
    if not scope <= selected | rejected | uncertain:
        raise PocRunRecordError(
            "Candidate Object Selection does not completely classify the office Ground Truth scope"
        )

    scored_scope = scope - truth_ambiguous
    scored_prediction = selected & scored_scope
    intersection = len(scored_prediction & truth_selected)
    union = len(scored_prediction | truth_selected)
    metrics: dict[str, int | float] = {
        "intersectionOverUnion": _ratio(intersection, union),
        "precision": _ratio(intersection, len(scored_prediction)),
        "recall": _ratio(intersection, len(truth_selected)),
        "truthSelectedUncertainCount": len(uncertain & truth_selected),
        "truthSelectedUncertainRate": _ratio(
            len(uncertain & truth_selected), len(truth_selected)
        ),
        "scopeUncertainCount": len(uncertain & scope),
        "scopeUncertainRate": _ratio(len(uncertain & scope), len(scope)),
    }
    return {
        "schemaVersion": 1,
        "benchmarkKind": "office",
        "targetId": target_id,
        "predictionManifestSha256": manifest_sha256,
        "groundTruthSha256": ground_truth_sha256,
        "groundTruthLabelsSha256": labels_sha256,
        "officeSourcePlySha256": source_sha256,
        "metrics": metrics,
        "officeGatePassed": metrics["intersectionOverUnion"] >= 0.8,
    }


def _office_target_id(ground_truth: Mapping[str, object]) -> str:
    target_id = ground_truth.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise PocRunRecordError("office Benchmark Ground Truth target_id is invalid")
    return target_id


@dataclass(frozen=True)
class _OfficeGroundTruthSource:
    source_path: str
    sha256: str
    gaussian_count: int


def _office_ground_truth_source(
    ground_truth: Mapping[str, object],
) -> _OfficeGroundTruthSource:
    """Map the external frozen fixture schema into Companion-side values.

    Ground Truth manifests predate the Companion protocol and deliberately use
    snake_case.  This adapter keeps that external schema at the trust boundary
    rather than introducing snake_case protocol fields.
    """

    if ground_truth.get("schema_version") != 1:
        raise PocRunRecordError("office Benchmark Ground Truth schema is unsupported")
    if ground_truth.get("status") != "frozen":
        raise PocRunRecordError("office Benchmark Ground Truth is not frozen")
    # These names are the frozen Ground Truth artifact schema, not protocol
    # fields. Keep their translation localized in this external-schema adapter.
    source_ply = ground_truth.get("source_ply")
    if not isinstance(source_ply, Mapping):
        raise PocRunRecordError("office Benchmark Ground Truth source_ply is invalid")
    source_path = source_ply.get("path")
    source_sha256 = source_ply.get("sha256")
    source_gaussian_count = source_ply.get("gaussian_count")
    if (
        not isinstance(source_path, str)
        or not source_path.strip()
        or not isinstance(source_sha256, str)
        or not _sha256_hex(source_sha256)
        or not isinstance(source_gaussian_count, int)
        or isinstance(source_gaussian_count, bool)
        or source_gaussian_count <= 0
    ):
        raise PocRunRecordError("office Benchmark Ground Truth source_ply is invalid")
    return _OfficeGroundTruthSource(
        source_path=source_path,
        sha256=source_sha256,
        gaussian_count=source_gaussian_count,
    )


def _validate_office_ground_truth_scene(
    source: _OfficeGroundTruthSource, scene_snapshot: Mapping[str, object]
) -> None:
    scene_version = scene_snapshot.get("sceneVersion")
    gaussian_count = scene_snapshot.get("gaussianCount")
    stable_id_schema = scene_snapshot.get("stableIdSchema")
    if (
        not isinstance(scene_version, str)
        or not scene_version.strip()
        or not isinstance(gaussian_count, int)
        or isinstance(gaussian_count, bool)
        or gaussian_count <= 0
        or not isinstance(stable_id_schema, str)
    ):
        raise PocRunRecordError("sealed Scene Snapshot identity is invalid")
    if (
        scene_version != f"sha256:{source.sha256}"
        or gaussian_count != source.gaussian_count
        or stable_id_schema != "uint32"
    ):
        raise PocRunRecordError(
            "office Benchmark Ground Truth does not bind the sealed Scene Snapshot"
        )


def _validate_benchmark_prompt_log(
    benchmark_prompt_log: Mapping[str, object],
    *,
    expected_target_id: str,
    frame_set: Mapping[str, object],
) -> _PromptLogBinding:
    prompt_log_target_id = benchmark_prompt_log.get("targetId")
    if (
        not isinstance(prompt_log_target_id, str)
        or not prompt_log_target_id.strip()
        or prompt_log_target_id != expected_target_id
    ):
        raise PocRunRecordError(
            "Benchmark Prompt Log does not match the sealed benchmark target"
        )
    frozen_source = benchmark_prompt_log.get("frozenSource")
    if not isinstance(frozen_source, Mapping):
        raise PocRunRecordError("Benchmark Prompt Log frozen source is invalid")
    source_file = frozen_source.get("file")
    source_sha256 = frozen_source.get("sha256")
    if (
        not isinstance(source_file, str)
        or not source_file.strip()
        or not isinstance(source_sha256, str)
        or not source_sha256.startswith("sha256:")
        or not _sha256_hex(source_sha256.removeprefix("sha256:"))
    ):
        raise PocRunRecordError("Benchmark Prompt Log frozen source is invalid")

    frozen_entries = benchmark_prompt_log.get("frozenEntries")
    session_entries = benchmark_prompt_log.get("entries")
    _validate_benchmark_prompt_entries(
        frozen_entries, "Benchmark Prompt Log frozen entries"
    )
    _validate_benchmark_prompt_entries(
        session_entries, "Benchmark Prompt Log session entries"
    )
    if not isinstance(frozen_entries, list) or not isinstance(session_entries, list):
        raise PocRunRecordError("Benchmark Prompt Log entries are invalid")
    if len(frozen_entries) != len(session_entries):
        raise PocRunRecordError(
            "Benchmark Prompt Log session entries do not match its frozen source"
        )
    for frozen_entry, session_entry in zip(frozen_entries, session_entries):
        frozen_prompt = frozen_entry["prompt"]
        session_prompt = session_entry["prompt"]
        if not isinstance(frozen_prompt, Mapping) or not isinstance(
            session_prompt, Mapping
        ):
            raise PocRunRecordError("Benchmark Prompt Log entries are invalid")
        if any(
            frozen_prompt.get(name) != session_prompt.get(name)
            for name in ("promptId", "viewId", "xPx", "yPx", "polarity")
        ):
            raise PocRunRecordError(
                "Benchmark Prompt Log session entries do not match its frozen source"
            )

    frozen_operations = [entry["operation"] for entry in frozen_entries]
    session_operations = [entry["operation"] for entry in session_entries]
    if session_operations[0] != "New" or "New" in session_operations[1:]:
        raise PocRunRecordError(
            "Benchmark Prompt Log session entries must contain one initial New"
        )
    if frozen_operations[0] != "New":
        raise PocRunRecordError(
            "Benchmark Prompt Log frozen entries must start with New"
        )
    initial_new_count = 0
    for operation in frozen_operations:
        if operation != "New":
            break
        initial_new_count += 1
    if "New" in frozen_operations[initial_new_count:]:
        raise PocRunRecordError(
            "Benchmark Prompt Log frozen entries have a non-initial New"
        )
    expected_session_operations = (
        ["New"]
        + ["Refine"] * (initial_new_count - 1)
        + frozen_operations[initial_new_count:]
    )
    if session_operations != expected_session_operations:
        raise PocRunRecordError("Benchmark Prompt Log materialization is invalid")
    if frozen_operations != session_operations:
        materialization = benchmark_prompt_log.get("sessionMaterialization")
        if (
            not isinstance(materialization, Mapping)
            or materialization.get("kind")
            != "initial-new-points-to-primary-track/v1"
        ):
            raise PocRunRecordError(
                "Benchmark Prompt Log materialization is invalid"
            )
    _validate_prompt_frame_bindings(session_entries, frame_set)
    frozen_entries_sha256 = canonical_prompt_entries_sha256(frozen_entries)
    session_entries_sha256 = canonical_prompt_entries_sha256(session_entries)
    declared_frozen_sha256 = benchmark_prompt_log.get("frozenEntriesSha256")
    declared_session_sha256 = benchmark_prompt_log.get("sessionEntriesSha256")
    canonical_hashes_bound = (
        declared_frozen_sha256 == frozen_entries_sha256
        and declared_session_sha256 == session_entries_sha256
    )
    for label, declared_sha256, expected_sha256 in (
        (
            "frozenEntriesSha256",
            declared_frozen_sha256,
            frozen_entries_sha256,
        ),
        (
            "sessionEntriesSha256",
            declared_session_sha256,
            session_entries_sha256,
        ),
    ):
        if declared_sha256 is not None and (
            not _sha256_reference(declared_sha256)
            or declared_sha256 != expected_sha256
        ):
            raise PocRunRecordError(
                f"Benchmark Prompt Log {label} does not match its entries"
            )
    return _PromptLogBinding(
        entry_count=len(session_entries),
        frozen_entries_sha256=frozen_entries_sha256,
        session_entries_sha256=session_entries_sha256,
        prefix_sha256s=tuple(
            canonical_prompt_entries_sha256(session_entries[:revision])
            for revision in range(1, len(session_entries) + 1)
        ),
        canonical_hashes_bound=canonical_hashes_bound,
    )


def _validate_prompt_frame_bindings(
    session_entries: list[object], frame_set: Mapping[str, object]
) -> None:
    ordered_views = frame_set.get("orderedViews")
    if not isinstance(ordered_views, list) or not ordered_views:
        raise PocRunRecordError("Frame Set ordered views are invalid")
    views: dict[str, tuple[str, int, int]] = {}
    for view in ordered_views:
        if not isinstance(view, Mapping):
            raise PocRunRecordError("Frame Set ordered views are invalid")
        view_id = view.get("viewId")
        frame_digest = view.get("frameDigest")
        width = view.get("width")
        height = view.get("height")
        if (
            not isinstance(view_id, str)
            or not view_id
            or view_id in views
            or not _sha256_reference(frame_digest)
            or not _positive_int(width)
            or not _positive_int(height)
        ):
            raise PocRunRecordError("Frame Set ordered views are invalid")
        views[view_id] = (frame_digest, width, height)
    for entry in session_entries:
        if not isinstance(entry, Mapping):
            raise PocRunRecordError("Benchmark Prompt Log session entries are invalid")
        prompt = entry.get("prompt")
        if not isinstance(prompt, Mapping):
            raise PocRunRecordError("Benchmark Prompt Log session entries are invalid")
        view_id = prompt.get("viewId")
        frame_digest = prompt.get("frameDigest")
        frame_width = prompt.get("frameWidth")
        frame_height = prompt.get("frameHeight")
        x_px = prompt.get("xPx")
        y_px = prompt.get("yPx")
        view = views.get(view_id) if isinstance(view_id, str) else None
        if (
            view is None
            or frame_digest != view[0]
            or frame_width != view[1]
            or frame_height != view[2]
            or not isinstance(x_px, int)
            or isinstance(x_px, bool)
            or not isinstance(y_px, int)
            or isinstance(y_px, bool)
            or x_px >= view[1]
            or y_px >= view[2]
        ):
            raise PocRunRecordError(
                "Benchmark Prompt Log session entries do not bind the Frame Set"
            )


def _validate_benchmark_prompt_entries(value: object, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise PocRunRecordError(f"{label} are invalid")
    prompt_ids: set[str] = set()
    for entry in value:
        if not isinstance(entry, Mapping):
            raise PocRunRecordError(f"{label} are invalid")
        operation = entry.get("operation")
        prompt = entry.get("prompt")
        if (
            not isinstance(operation, str)
            or operation not in {"New", "Add", "Remove", "Refine"}
            or not isinstance(prompt, Mapping)
        ):
            raise PocRunRecordError(f"{label} are invalid")
        prompt_id = prompt.get("promptId")
        view_id = prompt.get("viewId")
        x_px = prompt.get("xPx")
        y_px = prompt.get("yPx")
        polarity = prompt.get("polarity")
        if (
            not isinstance(prompt_id, str)
            or not prompt_id
            or prompt_id in prompt_ids
            or not isinstance(view_id, str)
            or not view_id
            or not isinstance(x_px, int)
            or isinstance(x_px, bool)
            or x_px < 0
            or not isinstance(y_px, int)
            or isinstance(y_px, bool)
            or y_px < 0
            or not isinstance(polarity, str)
            or polarity not in {"include", "exclude"}
        ):
            raise PocRunRecordError(f"{label} are invalid")
        prompt_ids.add(prompt_id)


def _verified_office_source_ply(
    office_source_ply_path: Path | None, source: _OfficeGroundTruthSource
) -> str:
    if office_source_ply_path is None:
        raise PocRunRecordError(
            "office source PLY path is required to independently score Ground Truth"
        )
    try:
        actual_sha256 = _sha256(office_source_ply_path)
    except OSError as error:
        raise PocRunRecordError("office source PLY is unavailable") from error
    if actual_sha256 != source.sha256:
        raise PocRunRecordError("office source PLY hash does not match Ground Truth")
    return f"sha256:{actual_sha256}"


def _verified_office_labels_bytes(
    ground_truth_path: Path,
    labels: Mapping[str, object],
    *,
    output_path: Path,
) -> tuple[bytes, str]:
    artifact = labels.get("artifact")
    expected_sha256 = labels.get("artifact_sha256")
    if not isinstance(artifact, str) or not artifact.endswith(".npz"):
        raise PocRunRecordError(
            "office Benchmark Ground Truth labels artifact must be an .npz file"
        )
    if not isinstance(expected_sha256, str):
        raise PocRunRecordError(
            "office Benchmark Ground Truth labels artifact_sha256 is invalid"
        )
    labels_root = ground_truth_path.parent.resolve()
    labels_path = (labels_root / artifact).resolve()
    if not labels_path.is_relative_to(labels_root):
        raise PocRunRecordError("office Benchmark Ground Truth labels escape its manifest")
    _reject_output_collision(
        output_path, labels_path, "office Benchmark Ground Truth labels"
    )
    labels_bytes = _read_file_bytes(
        labels_path, "office Benchmark Ground Truth labels"
    )
    actual_sha256 = _sha256_bytes(labels_bytes)
    if actual_sha256 != expected_sha256:
        raise PocRunRecordError("office Benchmark Ground Truth labels hash mismatch")
    return labels_bytes, f"sha256:{actual_sha256}"


def _office_label_sets(
    labels_bytes: bytes,
) -> tuple[set[int], set[int], set[int], set[int]]:
    expected_names = {
        "selected_ids",
        "rejected_ids",
        "ambiguous_ids",
        "scope_ids",
    }
    try:
        import numpy as np

        with np.load(io.BytesIO(labels_bytes), allow_pickle=False) as labels:
            if set(labels.files) != expected_names:
                raise PocRunRecordError(
                    "office Benchmark Ground Truth labels have an unexpected array set"
                )
            selected = _numpy_stable_id_set(
                labels["selected_ids"],
                "office Benchmark Ground Truth selected_ids",
                numpy=np,
            )
            rejected = _numpy_stable_id_set(
                labels["rejected_ids"],
                "office Benchmark Ground Truth rejected_ids",
                numpy=np,
            )
            ambiguous = _numpy_stable_id_set(
                labels["ambiguous_ids"],
                "office Benchmark Ground Truth ambiguous_ids",
                numpy=np,
            )
            scope = _numpy_stable_id_set(
                labels["scope_ids"],
                "office Benchmark Ground Truth scope_ids",
                numpy=np,
            )
    except PocRunRecordError:
        raise
    except (ImportError, OSError, ValueError) as error:
        raise PocRunRecordError(
            "office Benchmark Ground Truth labels are unavailable or invalid"
        ) from error
    if selected & rejected or selected & ambiguous or rejected & ambiguous:
        raise PocRunRecordError(
            "office Benchmark Ground Truth label classifications must be disjoint"
        )
    return selected, rejected, ambiguous, scope


def _numpy_stable_id_set(value: object, label: str, *, numpy: Any) -> set[int]:
    if (
        not isinstance(value, numpy.ndarray)
        or value.ndim != 1
        or not numpy.issubdtype(value.dtype, numpy.integer)
    ):
        raise PocRunRecordError(f"{label} must be a one-dimensional integer array")
    return _stable_id_set([int(stable_id) for stable_id in value.tolist()], label)


def _validate_office_label_counts(
    labels: Mapping[str, object],
    *,
    selected: set[int],
    rejected: set[int],
    ambiguous: set[int],
    scope: set[int],
) -> None:
    expected_counts = {
        "selected_stable_gaussians": len(selected),
        "rejected_stable_gaussians": len(rejected),
        "ambiguous_stable_gaussians": len(ambiguous),
        "scope_stable_gaussians": len(scope),
    }
    for name, expected_count in expected_counts.items():
        actual_count = labels.get(name)
        if (
            not isinstance(actual_count, int)
            or isinstance(actual_count, bool)
            or actual_count != expected_count
        ):
            raise PocRunRecordError(
                f"office Benchmark Ground Truth labels {name} does not match its artifact"
            )


def _verified_prediction(prediction_directory: Path) -> _VerifiedPrediction:
    seal_bytes = _read_file_bytes(
        prediction_directory / "prediction-seal.json", "prediction seal"
    )
    seal = _read_json_bytes(seal_bytes, "prediction seal")
    seal_sha256 = f"sha256:{_sha256_bytes(seal_bytes)}"
    if (
        seal.get("schemaVersion") != 1
        or seal.get("status") != "sealed-before-ground-truth"
    ):
        raise PocRunRecordError("prediction is not sealed before Ground Truth")
    manifest_name = seal.get("manifest")
    expected_manifest_sha256 = seal.get("manifestSha256")
    if (
        manifest_name != "prediction-manifest.json"
        or not _sha256_reference(expected_manifest_sha256)
    ):
        raise PocRunRecordError("prediction seal is malformed")
    manifest_path = prediction_directory / manifest_name
    manifest_bytes = _read_file_bytes(manifest_path, "prediction manifest")
    actual_manifest_sha256 = f"sha256:{_sha256_bytes(manifest_bytes)}"
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise PocRunRecordError("prediction manifest hash mismatch")
    manifest = _read_json_bytes(manifest_bytes, "prediction manifest")
    if (
        manifest.get("schemaVersion") != 1
        or manifest.get("status") != "prediction-complete"
    ):
        raise PocRunRecordError(
            "sealed prediction is not complete and cannot be scored"
        )
    artifact_records = manifest.get("artifacts")
    allowed_artifacts = set(REQUIRED_PREDICTION_ARTIFACTS) | set(
        OPTIONAL_PREDICTION_ARTIFACTS
    )
    if (
        not isinstance(artifact_records, dict)
        or not set(REQUIRED_PREDICTION_ARTIFACTS) <= set(artifact_records)
        or not set(artifact_records) <= allowed_artifacts
    ):
        raise PocRunRecordError("prediction manifest has an incomplete artifact set")
    artifact_values: dict[str, dict[str, object]] = {}
    for name in (*REQUIRED_PREDICTION_ARTIFACTS, *OPTIONAL_PREDICTION_ARTIFACTS):
        if name not in artifact_records:
            continue
        record = artifact_records[name]
        if not isinstance(record, dict):
            raise PocRunRecordError(f"prediction artifact record is malformed: {name}")
        relative_path = record.get("path")
        expected_sha256 = record.get("sha256")
        expected_bytes = record.get("bytes")
        if (
            not isinstance(relative_path, str)
            or not _sha256_reference(expected_sha256)
            or not _nonnegative_int(expected_bytes)
        ):
            raise PocRunRecordError(f"prediction artifact record is malformed: {name}")
        artifact_path = (prediction_directory / relative_path).resolve()
        if not artifact_path.is_relative_to(prediction_directory):
            raise PocRunRecordError(f"prediction artifact escapes its record: {name}")
        artifact_bytes = _read_file_bytes(
            artifact_path, f"{name} artifact"
        )
        if len(artifact_bytes) != expected_bytes:
            raise PocRunRecordError(f"prediction artifact byte count mismatch: {name}")
        if f"sha256:{_sha256_bytes(artifact_bytes)}" != expected_sha256:
            raise PocRunRecordError(f"prediction artifact hash mismatch: {name}")
        if name != "dependencyLock":
            artifact_values[name] = _read_json_bytes(
                artifact_bytes, f"{name} artifact"
            )
    _validate_complete_identity(manifest, artifact_values)
    return _VerifiedPrediction(
        directory=prediction_directory,
        manifest=manifest,
        manifest_sha256=actual_manifest_sha256,
        seal_sha256=seal_sha256,
        artifacts=artifact_values,
    )


def _validate_complete_identity(
    manifest: Mapping[str, object], artifacts: Mapping[str, dict[str, object]]
) -> None:
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise PocRunRecordError("prediction manifest bindings are malformed")
    missing = [
        name
        for name in COMPLETE_REQUIRED_BINDINGS
        if not _nonempty_binding(bindings.get(name))
    ]
    if missing:
        raise PocRunRecordError(
            f"prediction bindings are missing required fields: {', '.join(missing)}"
        )

    def artifact(name: str) -> dict[str, object]:
        return artifacts[name]

    scene = artifact("sceneSnapshot")
    frame_set = artifact("frameSet")
    mask_set = artifact("maskSet")
    evidence = artifact("evidenceSnapshot")
    model = artifact("modelManifest")
    runtime = artifact("runtimeManifest")
    expected = {
        "sceneId": scene.get("sceneId"),
        "sceneVersion": scene.get("sceneVersion"),
        "frameSetVersion": frame_set.get("frameSetVersion"),
        "modelManifestDigest": model.get("digest"),
    }
    for name, artifact_value in expected.items():
        if artifact_value != bindings.get(name):
            raise PocRunRecordError(
                f"prediction binding does not match its artifact: {name}"
            )
    for name in (
        "requestId",
        "sessionId",
        "promptLogRevision",
        "frameSetVersion",
        "modelManifestDigest",
    ):
        if mask_set.get(name) != bindings.get(name):
            raise PocRunRecordError(
                f"prediction binding does not match Mask Set: {name}"
            )
    for name in COMPLETE_REQUIRED_BINDINGS:
        if name in {"trialId", "terminalState"}:
            continue
        if evidence.get(name) != bindings.get(name):
            raise PocRunRecordError(
                f"prediction binding does not match Evidence Snapshot: {name}"
            )
    for name in REQUIRED_PREDICTION_ARTIFACTS:
        if name == "dependencyLock":
            continue
        value = artifact(name)
        if value.get("recordBindings") != bindings:
            raise PocRunRecordError(
                f"prediction artifact is not bound to the manifest identity: {name}"
            )
    _validate_policy_bindings(
        bindings,
        render_policy=artifact("renderPolicy"),
        evidence_snapshot=evidence,
    )
    release = runtime.get("release")
    artifact_records = manifest["artifacts"]
    lock_record = artifact_records["dependencyLock"]
    if (
        not isinstance(release, dict)
        or release.get("lockDigest") != lock_record.get("sha256")
    ):
        raise PocRunRecordError(
            "dependency lock does not match the runtime release identity"
        )


def _validate_policy_bindings(
    bindings: Mapping[str, object],
    *,
    render_policy: Mapping[str, object],
    evidence_snapshot: Mapping[str, object] | None = None,
) -> None:
    """Require policy revisions to stay bound on every terminal record."""

    expected_version = bindings.get("renderConfigVersion")
    if not isinstance(expected_version, str) or not expected_version.strip():
        raise PocRunRecordError(
            "prediction binding renderConfigVersion must be a non-empty string"
        )
    policy_records: list[tuple[str, object]] = [
        ("renderPolicy", render_policy),
        ("renderPolicy evidencePolicy", render_policy.get("evidencePolicy")),
    ]
    if evidence_snapshot is not None:
        policy_records.append(
            ("Evidence Snapshot policy", evidence_snapshot.get("policy"))
        )
    for label, container in policy_records:
        version = (
            container.get("renderConfigVersion")
            if isinstance(container, Mapping)
            else None
        )
        if version != expected_version:
            raise PocRunRecordError(
                f"prediction binding does not match {label} renderConfigVersion"
            )


def _classification_sets(
    value: Mapping[str, object],
    *,
    selected_key: str,
    rejected_key: str,
    uncertain_key: str,
    label: str,
) -> tuple[set[int], set[int], set[int]]:
    selected = _stable_id_set(value.get(selected_key), f"{label} {selected_key}")
    rejected = _stable_id_set(value.get(rejected_key), f"{label} {rejected_key}")
    uncertain = _stable_id_set(value.get(uncertain_key), f"{label} {uncertain_key}")
    if selected & rejected or selected & uncertain or rejected & uncertain:
        raise PocRunRecordError(f"{label} classifications must be disjoint")
    return selected, rejected, uncertain


def _stable_id_set(value: object, label: str) -> set[int]:
    if isinstance(value, dict) and set(value) == {"inclusiveRange"}:
        bounds = value["inclusiveRange"]
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or any(
                not isinstance(bound, int)
                or isinstance(bound, bool)
                or bound < 0
                or bound > 0xFFFFFFFF
                for bound in bounds
            )
            or bounds[0] > bounds[1]
        ):
            raise PocRunRecordError(f"{label} inclusive range is invalid")
        return set(range(bounds[0], bounds[1] + 1))
    if not isinstance(value, list):
        raise PocRunRecordError(f"{label} must be an array or inclusive range")
    if any(
        not isinstance(stable_id, int)
        or isinstance(stable_id, bool)
        or stable_id < 0
        or stable_id > 0xFFFFFFFF
        for stable_id in value
    ):
        raise PocRunRecordError(f"{label} must contain unsigned 32-bit integers")
    result = set(value)
    if len(result) != len(value):
        raise PocRunRecordError(f"{label} must not contain duplicate IDs")
    return result


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    return _read_json_bytes(_read_file_bytes(path, label), label)


def _reject_prediction_output_collisions(
    output_path: Path, prediction_directory: Path
) -> None:
    """Keep an output hard link from silently replacing a sealed input."""

    try:
        input_paths = tuple(
            path for path in prediction_directory.rglob("*") if path.is_file()
        )
    except OSError as error:
        raise PocRunRecordError("sealed prediction inputs are unavailable") from error
    for input_path in input_paths:
        _reject_output_collision(output_path, input_path, "sealed prediction input")


def _reject_output_inside_scored_record(output_path: Path) -> None:
    """Do not add diagnostics to any immutable scored Run Record."""

    for ancestor in (output_path, *output_path.parents):
        if (ancestor / "scored-run-seal.json").is_file() or (
            ancestor / "scored-run-manifest.json"
        ).is_file():
            raise PocRunRecordError(
                "score output must remain outside an existing scored Run Record"
            )


def _reject_output_collision(output_path: Path, input_path: Path, label: str) -> None:
    """Reject resolved-path and inode aliases before atomic score replacement."""

    try:
        same_path = output_path.resolve() == input_path.resolve()
        same_inode = output_path.exists() and input_path.exists() and os.path.samefile(
            output_path, input_path
        )
    except OSError as error:
        raise PocRunRecordError(f"cannot verify score output against {label}") from error
    if same_path or same_inode:
        raise PocRunRecordError(f"score output must not overwrite {label}")


def _read_file_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise PocRunRecordError(f"{label} is unavailable") from error


def _read_json_bytes(value: bytes, label: str) -> dict[str, object]:
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PocRunRecordError(f"{label} is unavailable or invalid JSON") from error
    if not isinstance(decoded, dict):
        raise PocRunRecordError(f"{label} must be a JSON object")
    return decoded


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _nonempty_binding(value: object) -> bool:
    return (
        isinstance(value, (str, int))
        and not isinstance(value, bool)
        and str(value).strip() != ""
    )


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_prompt_entries_sha256(entries: Sequence[object]) -> str:
    """Hash one exact Benchmark Prompt Log prefix independent of JSON spacing."""

    try:
        canonical = json.dumps(
            entries,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise PocRunRecordError("Benchmark Prompt Log entries are not canonicalizable") from error
    return f"sha256:{_sha256_bytes(canonical)}"


def _sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _sha256_reference(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and _sha256_hex(value.removeprefix("sha256:"))
    )


def _nonnegative_int(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _positive_int(value: object) -> bool:
    return _nonnegative_int(value) and value > 0


def _finite_probability(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def _finite_nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _write_json(path: Path, value: object) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as destination:
            destination.write(
                json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
            )
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
