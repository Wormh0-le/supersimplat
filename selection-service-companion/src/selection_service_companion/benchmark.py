"""Blind PoC Trial records and independent scoring.

Prediction sealing deliberately has no Ground Truth parameter.  The scorer is
the first boundary that accepts Ground Truth, and it verifies the immutable
prediction seal before opening it.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Mapping
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
REQUIRED_BINDINGS = (
    "trialId",
    "protocolVersion",
    "deterministicSeed",
    "terminalState",
)


class PocRunRecordError(ValueError):
    """A PoC Trial cannot be sealed or independently scored."""


@dataclass(frozen=True)
class SealedPrediction:
    directory: Path
    manifest_path: Path
    seal_path: Path
    manifest_sha256: str


def seal_prediction(
    output_directory: Path,
    *,
    artifacts: Mapping[str, Path],
    bindings: Mapping[str, object],
) -> SealedPrediction:
    """Atomically persist and seal all blind prediction artifacts."""

    missing_artifacts = sorted(set(REQUIRED_PREDICTION_ARTIFACTS) - set(artifacts))
    unexpected_artifacts = sorted(set(artifacts) - set(REQUIRED_PREDICTION_ARTIFACTS))
    if missing_artifacts or unexpected_artifacts:
        raise PocRunRecordError(
            "prediction artifacts must match the required set; "
            f"missing={missing_artifacts}, unexpected={unexpected_artifacts}"
        )
    missing_bindings = [
        name for name in REQUIRED_BINDINGS if not _nonempty_binding(bindings.get(name))
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
        for name in REQUIRED_PREDICTION_ARTIFACTS:
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
) -> dict[str, object]:
    """Verify a sealed blind prediction, then independently open and score truth."""

    prediction_directory = prediction_directory.resolve()
    if ground_truth_path.resolve().is_relative_to(prediction_directory):
        raise PocRunRecordError(
            "Ground Truth must remain outside the sealed prediction"
        )
    if output_path.resolve().is_relative_to(prediction_directory):
        raise PocRunRecordError(
            "independent scores must not modify the sealed prediction"
        )

    manifest, manifest_sha256 = _verified_manifest(prediction_directory)
    candidate_record = manifest["artifacts"]["candidateObjectSelection"]
    candidate_path = prediction_directory / candidate_record["path"]
    candidate = _read_json_object(candidate_path, "Candidate Object Selection")

    # This read intentionally occurs only after every prediction hash passed.
    ground_truth = _read_json_object(ground_truth_path, "Benchmark Ground Truth")
    selected, rejected, uncertain = _classification_sets(
        candidate,
        selected_key="selectedStableGaussianIds",
        rejected_key="rejectedStableGaussianIds",
        uncertain_key="uncertainStableGaussianIds",
        label="Candidate Object Selection",
    )
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
        "groundTruthSha256": f"sha256:{_sha256(ground_truth_path)}",
        "metrics": metrics,
        "controlledOverlapGatePassed": (
            metrics["intersectionOverUnion"] >= 0.9
            and metrics["precision"] >= 0.9
            and metrics["recall"] >= 0.9
            and metrics["rearSurfaceRecall"] >= 0.9
            and metrics["selectedDistractorCount"] <= 81
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, result)
    return result


def _verified_manifest(prediction_directory: Path) -> tuple[dict[str, object], str]:
    seal = _read_json_object(
        prediction_directory / "prediction-seal.json", "prediction seal"
    )
    if seal.get("status") != "sealed-before-ground-truth":
        raise PocRunRecordError("prediction is not sealed before Ground Truth")
    manifest_name = seal.get("manifest")
    expected_manifest_sha256 = seal.get("manifestSha256")
    if manifest_name != "prediction-manifest.json" or not isinstance(
        expected_manifest_sha256, str
    ):
        raise PocRunRecordError("prediction seal is malformed")
    manifest_path = prediction_directory / manifest_name
    actual_manifest_sha256 = f"sha256:{_sha256(manifest_path)}"
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise PocRunRecordError("prediction manifest hash mismatch")
    manifest = _read_json_object(manifest_path, "prediction manifest")
    if manifest.get("status") != "prediction-complete":
        raise PocRunRecordError(
            "sealed prediction is not complete and cannot be scored"
        )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(
        REQUIRED_PREDICTION_ARTIFACTS
    ):
        raise PocRunRecordError("prediction manifest has an incomplete artifact set")
    for name in REQUIRED_PREDICTION_ARTIFACTS:
        record = artifacts[name]
        if not isinstance(record, dict):
            raise PocRunRecordError(f"prediction artifact record is malformed: {name}")
        relative_path = record.get("path")
        expected_sha256 = record.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise PocRunRecordError(f"prediction artifact record is malformed: {name}")
        artifact_path = (prediction_directory / relative_path).resolve()
        if not artifact_path.is_relative_to(prediction_directory):
            raise PocRunRecordError(f"prediction artifact escapes its record: {name}")
        if f"sha256:{_sha256(artifact_path)}" != expected_sha256:
            raise PocRunRecordError(f"prediction artifact hash mismatch: {name}")
    return manifest, actual_manifest_sha256


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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PocRunRecordError(f"{label} is unavailable or invalid JSON") from error
    if not isinstance(value, dict):
        raise PocRunRecordError(f"{label} must be a JSON object")
    return value


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _nonempty_binding(value: object) -> bool:
    return (
        isinstance(value, (str, int))
        and not isinstance(value, bool)
        and str(value).strip() != ""
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
