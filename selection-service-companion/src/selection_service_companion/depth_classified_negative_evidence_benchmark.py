"""Immutable prediction and scoring records for the V2AX benchmark.

Prediction persistence accepts no Ground Truth input.  The unchanged
single-``negativeMass`` baseline is sealed before any experimental/reference
variant.  The independent scorer verifies every prediction hash before it
opens Ground Truth, and a variant result never changes the baseline gate.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Mapping, Sequence

from .depth_classified_negative_evidence_experiment import (
    EXPERIMENTAL_SCHEMA_VERSION,
    _validated_relation_config,
    validate_depth_classified_replay_config,
)
from .digests import canonical_json_digest


BASELINE_METHOD_ID = "production-single-negative-mass/baseline-v1"
BASELINE_RECORD_KIND = (
    "depth-classified-negative-evidence-baseline/experimental-reference"
)
VARIANT_RECORD_KIND = (
    "depth-classified-negative-evidence-variant/experimental-reference"
)
PREDICTION_MANIFEST_KIND = (
    "depth-classified-negative-evidence-prediction/experimental-reference"
)
SCORE_RECORD_KIND = "depth-classified-negative-evidence-score/experimental-reference"
_SCORE_POLICY = {
    "policyId": "depth-classified-negative-evidence-score/experimental-reference-v1",
    "minimumTargetPrecision": 0.9,
    "minimumTargetRecall": 0.9,
    "maximumDistractorLeakageCount": 81,
}
_INPUT_IDENTITY_KEYS = {
    "sceneSnapshotDigest",
    "cameraBindingsDigest",
    "stableMasksDigest",
    "workingSetsDigest",
    "rendererRuntimeDigest",
    "deterministicSeed",
}
_RUNTIME_SOURCE_KEYS = {
    "directEvidenceAbiVersion",
    "directEvidenceSourceRevision",
    "directEvidenceRuntimeBuildId",
    "rendererRuntimeDigest",
    "gpuName",
    "computeCapability",
    "torchVersion",
    "cudaVersion",
    "gsplatSourceCommit",
}
_TIMING_AND_VRAM_KEYS = {"latencyMilliseconds", "peakVramBytes"}
_BASELINE_BUFFER_WRITE_KEYS = {
    "productionNegativeMass",
    "classifiedSidecar",
    "total",
}
_VARIANT_BUFFER_WRITE_KEYS = {
    "productionNegativeMass",
    "front",
    "near",
    "behind",
    "invalidDepth",
    "classifiedSidecar",
    "total",
}
_MAX_STABLE_GAUSSIAN_ID = (1 << 32) - 1
_CONFIGURATION_KEYS = {
    "schemaVersion",
    "experimentId",
    "status",
    "predictionProtocol",
    "depthMomentValidityPolicy",
    "relationConfigs",
    "variantMethods",
    "measurementPolicy",
    "scenes",
    "recommendationChoices",
    "configurationDigest",
}
_SCENE_CONFIGURATION_KEYS = {
    "sceneId",
    "seeds",
    "fixtureManifest",
    "fixtureManifestSha256",
    "sceneSnapshot",
    "sceneSnapshotSha256",
    "frameSetManifest",
    "frameSetManifestSha256",
    "stableMaskManifest",
    "stableMaskManifestSha256",
    "stableMasks",
    "stableMasksSha256",
    "groundTruthAccess",
    "thinOrEdgeGroundTruth",
}


class DepthClassifiedNegativeEvidenceBenchmarkError(ValueError):
    """A V2AX prediction or independent score record failed closed."""


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _validated_digest_list(value: object, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not _is_digest(item) for item in value)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"{label} must contain one or more SHA-256 identities."
        )
    return list(value)


def create_experiment_input_identity(
    *,
    scene_snapshot_digest: str,
    camera_bindings_digest: str,
    stable_masks_digest: str,
    working_sets_digest: str,
    renderer_runtime_digest: str,
    deterministic_seed: str,
) -> dict[str, object]:
    """Bind the exact byte/runtime input shared by baseline and variants."""

    payload: dict[str, object] = {
        "sceneSnapshotDigest": scene_snapshot_digest,
        "cameraBindingsDigest": camera_bindings_digest,
        "stableMasksDigest": stable_masks_digest,
        "workingSetsDigest": working_sets_digest,
        "rendererRuntimeDigest": renderer_runtime_digest,
        "deterministicSeed": deterministic_seed,
    }
    validated = _validated_input_identity(payload)
    return {
        **validated,
        "inputIdentityDigest": canonical_json_digest(validated),
    }


def _validated_input_identity(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment input identity is invalid."
        )
    payload = dict(value)
    declared_digest = payload.pop("inputIdentityDigest", None)
    if set(payload) != _INPUT_IDENTITY_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment input identity is incomplete or has unknown fields."
        )
    for name in (
        "sceneSnapshotDigest",
        "cameraBindingsDigest",
        "stableMasksDigest",
        "workingSetsDigest",
        "rendererRuntimeDigest",
    ):
        if not _is_digest(payload[name]):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                f"the experiment input {name} is not a SHA-256 identity."
            )
    seed = payload["deterministicSeed"]
    if not isinstance(seed, str) or not seed.strip():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment deterministic seed is invalid."
        )
    expected_digest = canonical_json_digest(payload)
    if declared_digest is not None and declared_digest != expected_digest:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment input identity digest does not match its payload."
        )
    return deepcopy(payload)


def _validated_runtime_source(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _RUNTIME_SOURCE_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment runtime/source identity is incomplete."
        )
    result = deepcopy(dict(value))
    if (
        not isinstance(result["directEvidenceAbiVersion"], str)
        or not result["directEvidenceAbiVersion"].strip()
        or any(
            not _is_digest(result[name])
            for name in (
                "directEvidenceSourceRevision",
                "directEvidenceRuntimeBuildId",
                "rendererRuntimeDigest",
            )
        )
        or any(
            not isinstance(result[name], str) or not result[name].strip()
            for name in (
                "gpuName",
                "computeCapability",
                "torchVersion",
                "cudaVersion",
                "gsplatSourceCommit",
            )
        )
        or len(result["gsplatSourceCommit"]) != 40
        or any(
            character not in "0123456789abcdef"
            for character in result["gsplatSourceCommit"]
        )
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment runtime/source identity is invalid."
        )
    return result


def _validated_timing_and_vram(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _TIMING_AND_VRAM_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment timing/VRAM record is incomplete."
        )
    latency = value["latencyMilliseconds"]
    peak_vram = value["peakVramBytes"]
    if (
        isinstance(latency, bool)
        or not isinstance(latency, (int, float))
        or not math.isfinite(float(latency))
        or float(latency) < 0.0
        or isinstance(peak_vram, bool)
        or not isinstance(peak_vram, int)
        or peak_vram < 0
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment timing/VRAM values are invalid."
        )
    return {
        "latencyMilliseconds": float(latency),
        "peakVramBytes": peak_vram,
    }


def _stable_id_list(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or any(
            not isinstance(stable_id, int)
            or isinstance(stable_id, bool)
            or stable_id < 0
            or stable_id > _MAX_STABLE_GAUSSIAN_ID
            for stable_id in value
        )
        or len(set(value)) != len(value)
        or value != sorted(value)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"{label} must be sorted unique unsigned 32-bit Stable Gaussian IDs."
        )
    return list(value)


def _validated_candidate_replay(value: object) -> dict[str, object]:
    required = {
        "selectedStableGaussianIds",
        "rejectedStableGaussianIds",
        "uncertainStableGaussianIds",
        "candidateInputStableGaussianIds",
        "replayDigest",
    }
    if not isinstance(value, Mapping) or not required <= set(value):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment Candidate replay is incomplete."
        )
    selected = _stable_id_list(
        value["selectedStableGaussianIds"], "selected Candidate IDs"
    )
    rejected = _stable_id_list(
        value["rejectedStableGaussianIds"], "rejected Candidate IDs"
    )
    uncertain = _stable_id_list(
        value["uncertainStableGaussianIds"], "uncertain Candidate IDs"
    )
    candidate_input = _stable_id_list(
        value["candidateInputStableGaussianIds"], "Candidate input IDs"
    )
    if (
        set(selected) & set(rejected)
        or set(selected) & set(uncertain)
        or set(rejected) & set(uncertain)
        or candidate_input != selected
        or not _is_digest(value["replayDigest"])
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment Candidate replay classifications are inconsistent."
        )
    return {
        "selectedStableGaussianIds": selected,
        "rejectedStableGaussianIds": rejected,
        "uncertainStableGaussianIds": uncertain,
        "candidateInputStableGaussianIds": candidate_input,
        "replayDigest": value["replayDigest"],
    }


def _record_input(value: object) -> tuple[dict[str, object], str]:
    if not isinstance(value, Mapping) or not _is_digest(
        value.get("inputIdentityDigest")
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the run record requires one exact experiment input identity."
        )
    payload = _validated_input_identity(value)
    digest = canonical_json_digest(payload)
    if digest != value["inputIdentityDigest"]:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the run record input identity digest is invalid."
        )
    return payload, digest


def create_baseline_run_record(
    *,
    input_identity: object,
    baseline_artifact_digests: Sequence[str],
    candidate_replay: object,
    runtime_source: object,
    timing_and_vram: object,
    buffer_writes: object,
) -> dict[str, object]:
    """Create the unchanged production single-N prediction record."""

    identity, identity_digest = _record_input(input_identity)
    artifacts = _validated_digest_list(
        list(baseline_artifact_digests), "baseline artifact identities"
    )
    candidate = _validated_candidate_replay(candidate_replay)
    payload: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "recordKind": BASELINE_RECORD_KIND,
        "method": {"methodId": BASELINE_METHOD_ID, "coefficients": None},
        "inputIdentity": identity,
        "inputIdentityDigest": identity_digest,
        "groundTruthAccess": "closed-during-prediction",
        "runtimeSource": _validated_runtime_source(runtime_source),
        "timingAndVram": _validated_timing_and_vram(timing_and_vram),
        "bufferWrites": _validated_baseline_buffer_writes(buffer_writes),
        "outputDigests": {
            "baselineArtifacts": artifacts,
            "candidateReplay": candidate["replayDigest"],
        },
        "candidate": candidate,
    }
    return {**payload, "recordDigest": canonical_json_digest(payload)}


def _validated_baseline_buffer_writes(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != _BASELINE_BUFFER_WRITE_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the baseline buffer-write record is incomplete."
        )
    result = dict(value)
    if (
        any(
            not isinstance(result[name], int)
            or isinstance(result[name], bool)
            or result[name] < 0
            for name in _BASELINE_BUFFER_WRITE_KEYS
        )
        or result["classifiedSidecar"] != 0
        or result["total"] != result["productionNegativeMass"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the baseline buffer-write counts are invalid."
        )
    return result


def _validated_variant_buffer_writes(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != _VARIANT_BUFFER_WRITE_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the variant buffer-write record is incomplete."
        )
    result = dict(value)
    if any(
        not isinstance(result[name], int)
        or isinstance(result[name], bool)
        or result[name] < 0
        for name in _VARIANT_BUFFER_WRITE_KEYS
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the variant buffer-write counts are invalid."
        )
    classified = sum(
        result[name] for name in ("front", "near", "behind", "invalidDepth")
    )
    if (
        result["classifiedSidecar"] != classified
        or result["total"] != result["productionNegativeMass"] + classified
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the variant buffer-write totals are inconsistent."
        )
    return result


def create_variant_run_record(
    *,
    input_identity: object,
    replay_config: object,
    sidecar_digests: Sequence[str],
    candidate_replay: object,
    runtime_source: object,
    timing_and_vram: object,
    buffer_writes: object,
) -> dict[str, object]:
    """Create one separate experimental/reference variant prediction record."""

    identity, identity_digest = _record_input(input_identity)
    method = validate_depth_classified_replay_config(replay_config)
    sidecars = _validated_digest_list(
        list(sidecar_digests), "classified diagnostic sidecar identities"
    )
    candidate = _validated_candidate_replay(candidate_replay)
    payload: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "recordKind": VARIANT_RECORD_KIND,
        "method": method,
        "inputIdentity": identity,
        "inputIdentityDigest": identity_digest,
        "groundTruthAccess": "closed-during-prediction",
        "runtimeSource": _validated_runtime_source(runtime_source),
        "timingAndVram": _validated_timing_and_vram(timing_and_vram),
        "bufferWrites": _validated_variant_buffer_writes(buffer_writes),
        "outputDigests": {
            "classifiedDiagnosticSidecars": sidecars,
            "candidateReplay": candidate["replayDigest"],
        },
        "candidate": candidate,
    }
    return {**payload, "recordDigest": canonical_json_digest(payload)}


def _validated_run_record(value: object, expected_kind: str) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or value.get("recordKind") != expected_kind
        or not _is_digest(value.get("recordDigest"))
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment run record is incomplete or has the wrong kind."
        )
    payload = {
        key: deepcopy(item) for key, item in value.items() if key != "recordDigest"
    }
    if canonical_json_digest(payload) != value["recordDigest"]:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment run record digest does not match its payload."
        )
    _record_input(
        {
            **payload["inputIdentity"],
            "inputIdentityDigest": payload["inputIdentityDigest"],
        }
    )
    _validated_candidate_replay(payload["candidate"])
    _validated_runtime_source(payload["runtimeSource"])
    _validated_timing_and_vram(payload["timingAndVram"])
    if payload.get("groundTruthAccess") != "closed-during-prediction":
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "Ground Truth was not closed during prediction."
        )
    if expected_kind == VARIANT_RECORD_KIND:
        validate_depth_classified_replay_config(payload["method"])
        _validated_variant_buffer_writes(payload["bufferWrites"])
    else:
        _validated_baseline_buffer_writes(payload["bufferWrites"])
        if payload.get("method") != {
            "methodId": BASELINE_METHOD_ID,
            "coefficients": None,
        }:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "the baseline method is not the unchanged production single-N identity."
            )
    return deepcopy(dict(value))


def load_depth_classified_negative_evidence_configuration(
    path: Path,
) -> dict[str, object]:
    """Load and verify the finite V2AX configuration without opening Ground Truth."""

    value = _read_json(path, "depth-classified experiment configuration")
    if set(value) != _CONFIGURATION_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the depth-classified experiment configuration is incomplete."
        )
    payload = {
        key: deepcopy(item)
        for key, item in value.items()
        if key != "configurationDigest"
    }
    if (
        value.get("schemaVersion") != EXPERIMENTAL_SCHEMA_VERSION
        or value.get("experimentId")
        != "v2ax-depth-classified-negative-evidence/experimental-reference-v1"
        or value.get("status") != "sealed-configuration"
        or value.get("configurationDigest") != canonical_json_digest(payload)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the depth-classified experiment configuration identity is invalid."
        )
    if value.get("predictionProtocol") != {
        "baselineMethodId": BASELINE_METHOD_ID,
        "baselineMustBePersistedFirst": True,
        "groundTruthAccess": "independent-scorer-only",
    }:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment prediction isolation protocol is invalid."
        )
    depth_policy = value.get("depthMomentValidityPolicy")
    if (
        not isinstance(depth_policy, Mapping)
        or set(depth_policy) != {"policyId", "minimumM0"}
        or depth_policy.get("policyId")
        != "depth-moment-minimum-m0/experimental-reference-v1"
        or isinstance(depth_policy.get("minimumM0"), bool)
        or not isinstance(depth_policy.get("minimumM0"), (int, float))
        or not math.isfinite(float(depth_policy["minimumM0"]))
        or float(depth_policy["minimumM0"]) <= 0.0
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment Depth Moment validity policy is invalid."
        )
    relations = value.get("relationConfigs")
    variants = value.get("variantMethods")
    if (
        not isinstance(relations, list)
        or len(relations) != 1
        or not isinstance(variants, list)
        or not variants
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment requires one relation function and a finite variant set."
        )
    _validated_relation_config(relations[0])
    validated_variants = [
        validate_depth_classified_replay_config(variant) for variant in variants
    ]
    method_ids = [str(variant["methodId"]) for variant in validated_variants]
    if len(set(method_ids)) != len(method_ids):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment variant method identities must be unique."
        )
    measurement = value.get("measurementPolicy")
    if (
        not isinstance(measurement, Mapping)
        or set(measurement)
        != {
            "warmupRuns",
            "measuredRuns",
            "latencyStatistic",
            "peakVramMeasurement",
            "bufferWriteMeasurement",
        }
        or measurement.get("warmupRuns") != 1
        or measurement.get("measuredRuns") != 3
        or measurement.get("latencyStatistic") != "median"
        or measurement.get("peakVramMeasurement") != "torch.cuda.max_memory_allocated"
        or measurement.get("bufferWriteMeasurement")
        != "logical-output-channel-elements"
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment measurement policy is invalid."
        )
    scenes = value.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment requires at least one immutable scene manifest."
        )
    configuration_root = path.resolve().parent
    path_and_digest_fields = (
        ("fixtureManifest", "fixtureManifestSha256"),
        ("sceneSnapshot", "sceneSnapshotSha256"),
        ("frameSetManifest", "frameSetManifestSha256"),
        ("stableMaskManifest", "stableMaskManifestSha256"),
        ("stableMasks", "stableMasksSha256"),
    )
    seen_scenes: set[str] = set()
    for scene in scenes:
        if (
            not isinstance(scene, Mapping)
            or set(scene) != _SCENE_CONFIGURATION_KEYS
            or not isinstance(scene.get("sceneId"), str)
            or not scene["sceneId"]
            or scene["sceneId"] in seen_scenes
            or not isinstance(scene.get("seeds"), list)
            or not scene["seeds"]
            or len(set(scene["seeds"])) != len(scene["seeds"])
            or any(not isinstance(seed, str) or not seed for seed in scene["seeds"])
            or scene.get("groundTruthAccess") != "independent-scorer-only"
            or scene.get("thinOrEdgeGroundTruth")
            not in {"available-in-fixture", "unavailable-in-fixture"}
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "an experiment scene configuration is invalid."
            )
        seen_scenes.add(str(scene["sceneId"]))
        for path_field, digest_field in path_and_digest_fields:
            relative = scene[path_field]
            expected_digest = scene[digest_field]
            if (
                not isinstance(relative, str)
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
                or not _is_digest(expected_digest)
            ):
                raise DepthClassifiedNegativeEvidenceBenchmarkError(
                    "an experiment fixture path or digest is invalid."
                )
            fixture = (configuration_root / relative).resolve()
            if (
                not fixture.is_relative_to(configuration_root)
                or not fixture.is_file()
                or _sha256(fixture) != expected_digest
            ):
                raise DepthClassifiedNegativeEvidenceBenchmarkError(
                    f"the immutable experiment fixture does not match: {relative}."
                )
    if value.get("recommendationChoices") != [
        "retain-experimental",
        "propose-promotion-issue",
        "delete",
    ]:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment recommendation choices are invalid."
        )
    return deepcopy(value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def persist_baseline_run_record(prediction_directory: Path, record: object) -> Path:
    """Persist and seal the baseline before a variant may be written."""

    baseline = _validated_run_record(record, BASELINE_RECORD_KIND)
    prediction_directory.mkdir(parents=True, exist_ok=True)
    path = prediction_directory / "baseline-run-record.json"
    seal_path = prediction_directory / "baseline-seal.json"
    if path.exists() or seal_path.exists():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "refusing to overwrite the immutable baseline run record."
        )
    _write_json(path, baseline)
    _write_json(
        seal_path,
        {
            "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
            "status": "baseline-sealed-before-variants-and-ground-truth",
            "record": path.name,
            "recordSha256": _sha256(path),
            "recordDigest": baseline["recordDigest"],
        },
    )
    return path


def persist_sidecar_failure(
    prediction_directory: Path,
    *,
    error: Exception,
    baseline_record_digest: str,
) -> Path:
    """Persist diagnostic sidecar failure after leaving the baseline sealed."""

    if (
        not (prediction_directory / "baseline-seal.json").is_file()
        or not _is_digest(baseline_record_digest)
        or (prediction_directory / "prediction-seal.json").exists()
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "a sidecar failure requires an unmodified sealed baseline."
        )
    path = prediction_directory / "sidecar-failure.json"
    if path.exists():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "refusing to overwrite an immutable sidecar failure record."
        )
    _write_json(
        path,
        {
            "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
            "status": "baseline-sealed-sidecar-failed",
            "errorType": type(error).__name__,
            "message": str(error),
            "baselineRecordDigest": baseline_record_digest,
            "groundTruthAccess": "closed-during-prediction",
        },
    )
    return path


def persist_variant_run_record(
    prediction_directory: Path,
    record: object,
    *,
    ordinal: int,
) -> Path:
    """Persist one diagnostic variant without modifying the sealed baseline."""

    if (
        isinstance(ordinal, bool)
        or not isinstance(ordinal, int)
        or ordinal < 0
        or not (prediction_directory / "baseline-seal.json").is_file()
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "a variant requires a non-negative ordinal and a sealed baseline."
        )
    variant = _validated_run_record(record, VARIANT_RECORD_KIND)
    stem = f"variant-{ordinal:03d}"
    path = prediction_directory / f"{stem}-run-record.json"
    seal_path = prediction_directory / f"{stem}-seal.json"
    if path.exists() or seal_path.exists():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "refusing to overwrite an immutable variant run record."
        )
    _write_json(path, variant)
    _write_json(
        seal_path,
        {
            "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
            "status": "variant-sealed-before-ground-truth",
            "record": path.name,
            "recordSha256": _sha256(path),
            "recordDigest": variant["recordDigest"],
        },
    )
    return path


def seal_depth_classified_negative_evidence_prediction(
    prediction_directory: Path,
    *,
    expected_variant_method_ids: Sequence[str],
) -> dict[str, object]:
    """Seal the ordered baseline-plus-finite-variant prediction index."""

    manifest_path = prediction_directory / "prediction-manifest.json"
    seal_path = prediction_directory / "prediction-seal.json"
    if manifest_path.exists() or seal_path.exists():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "refusing to overwrite a sealed depth-classified prediction."
        )
    baseline_path = prediction_directory / "baseline-run-record.json"
    baseline_seal = _read_json(
        prediction_directory / "baseline-seal.json", "baseline seal"
    )
    baseline = _verified_record_file(baseline_path, baseline_seal, BASELINE_RECORD_KIND)
    records: list[dict[str, object]] = [
        {
            "kind": "baseline",
            "methodId": BASELINE_METHOD_ID,
            "path": baseline_path.name,
            "sha256": _sha256(baseline_path),
            "recordDigest": baseline["recordDigest"],
        }
    ]
    methods = list(expected_variant_method_ids)
    if not methods or len(set(methods)) != len(methods):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed experiment requires a finite unique variant method set."
        )
    for ordinal, expected_method in enumerate(methods):
        stem = f"variant-{ordinal:03d}"
        path = prediction_directory / f"{stem}-run-record.json"
        seal = _read_json(
            prediction_directory / f"{stem}-seal.json", f"variant {ordinal} seal"
        )
        variant = _verified_record_file(path, seal, VARIANT_RECORD_KIND)
        if variant["method"]["methodId"] != expected_method:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "the persisted variant method order does not match the sealed configuration."
            )
        if variant["inputIdentityDigest"] != baseline["inputIdentityDigest"]:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "baseline and variants did not consume identity-equivalent inputs."
            )
        records.append(
            {
                "kind": "variant",
                "methodId": expected_method,
                "path": path.name,
                "sha256": _sha256(path),
                "recordDigest": variant["recordDigest"],
            }
        )
    extra_variants = sorted(
        path for path in prediction_directory.glob("variant-*-run-record.json")
    )
    if len(extra_variants) != len(methods):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the persisted variant set is incomplete or contains undeclared methods."
        )
    manifest: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "artifactKind": PREDICTION_MANIFEST_KIND,
        "status": "prediction-complete",
        "inputIdentityDigest": baseline["inputIdentityDigest"],
        "groundTruthAccess": "closed-during-prediction",
        "records": records,
    }
    _write_json(manifest_path, manifest)
    seal = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "status": "sealed-before-ground-truth",
        "manifest": manifest_path.name,
        "manifestSha256": _sha256(manifest_path),
    }
    _write_json(seal_path, seal)
    return seal


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"{label} is unavailable or invalid JSON."
        ) from error
    if not isinstance(value, dict):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"{label} must be a JSON object."
        )
    return value


def _verified_record_file(
    path: Path,
    seal: Mapping[str, object],
    expected_kind: str,
) -> dict[str, object]:
    if seal.get("record") != path.name or seal.get("recordSha256") != _sha256(path):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "an experiment run-record seal does not match its file."
        )
    record = _validated_run_record(_read_json(path, "run record"), expected_kind)
    if seal.get("recordDigest") != record["recordDigest"]:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "an experiment run-record seal does not match its canonical digest."
        )
    return record


def _verified_prediction(
    prediction_directory: Path,
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    seal = _read_json(prediction_directory / "prediction-seal.json", "prediction seal")
    manifest_path = prediction_directory / "prediction-manifest.json"
    if (
        seal.get("status") != "sealed-before-ground-truth"
        or seal.get("manifest") != manifest_path.name
        or seal.get("manifestSha256") != _sha256(manifest_path)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment prediction seal is invalid."
        )
    manifest = _read_json(manifest_path, "prediction manifest")
    records = manifest.get("records")
    if (
        manifest.get("status") != "prediction-complete"
        or manifest.get("artifactKind") != PREDICTION_MANIFEST_KIND
        or manifest.get("groundTruthAccess") != "closed-during-prediction"
        or not isinstance(records, list)
        or len(records) < 2
        or records[0].get("kind") != "baseline"
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment prediction manifest is incomplete."
        )
    verified: list[dict[str, object]] = []
    for index, entry in enumerate(records):
        if not isinstance(entry, Mapping) or not isinstance(entry.get("path"), str):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "the experiment prediction record index is malformed."
            )
        path = (prediction_directory / entry["path"]).resolve()
        if not path.is_relative_to(prediction_directory.resolve()):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "an experiment run record escapes its prediction directory."
            )
        expected_kind = BASELINE_RECORD_KIND if index == 0 else VARIANT_RECORD_KIND
        if entry.get("sha256") != _sha256(path):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "an indexed experiment run record hash does not match."
            )
        record = _validated_run_record(_read_json(path, "run record"), expected_kind)
        if (
            entry.get("recordDigest") != record["recordDigest"]
            or entry.get("methodId") != record["method"]["methodId"]
            or record["inputIdentityDigest"] != manifest.get("inputIdentityDigest")
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "an indexed experiment run record identity does not match."
            )
        verified.append(record)
    return manifest, verified, str(seal["manifestSha256"])


def _stable_id_set(value: object, label: str) -> set[int]:
    if isinstance(value, Mapping) and set(value) == {"inclusiveRange"}:
        bounds = value["inclusiveRange"]
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or any(
                not isinstance(bound, int)
                or isinstance(bound, bool)
                or bound < 0
                or bound > _MAX_STABLE_GAUSSIAN_ID
                for bound in bounds
            )
            or bounds[0] > bounds[1]
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                f"{label} inclusive range is invalid."
            )
        return set(range(bounds[0], bounds[1] + 1))
    return set(_stable_id_list(value, label))


def _score_candidate(
    candidate: Mapping[str, object], ground_truth: Mapping[str, object]
) -> tuple[dict[str, object], bool]:
    selected = _stable_id_set(
        candidate.get("selectedStableGaussianIds"), "Candidate selected IDs"
    )
    rejected = _stable_id_set(
        candidate.get("rejectedStableGaussianIds"), "Candidate rejected IDs"
    )
    uncertain = _stable_id_set(
        candidate.get("uncertainStableGaussianIds"), "Candidate uncertain IDs"
    )
    truth_selected = _stable_id_set(
        ground_truth.get("selectedStableGaussianIds"), "Ground Truth selected IDs"
    )
    truth_rejected = _stable_id_set(
        ground_truth.get("rejectedStableGaussianIds"), "Ground Truth rejected IDs"
    )
    truth_ambiguous = _stable_id_set(
        ground_truth.get("ambiguousStableGaussianIds"), "Ground Truth ambiguous IDs"
    )
    if (
        selected & rejected
        or selected & uncertain
        or rejected & uncertain
        or selected | rejected | uncertain
        != truth_selected | truth_rejected | truth_ambiguous
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the Candidate does not completely and disjointly classify Ground Truth."
        )
    distractors = _stable_id_set(
        ground_truth.get("distractorStableGaussianIds"), "Ground Truth distractor IDs"
    )
    if not distractors <= truth_rejected:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "Ground Truth distractors must be rejected truth."
        )
    scored_selected = selected - truth_ambiguous
    true_positive = len(scored_selected & truth_selected)
    precision = true_positive / len(scored_selected) if scored_selected else 0.0
    recall = true_positive / len(truth_selected) if truth_selected else 1.0
    leakage_count = len(selected & distractors)
    thin_or_edge_raw = ground_truth.get("thinOrEdgeStableGaussianIds")
    if thin_or_edge_raw is None:
        thin_or_edge_retention: float | None = None
        thin_or_edge_available = False
    else:
        thin_or_edge = _stable_id_set(thin_or_edge_raw, "Ground Truth thin/edge IDs")
        if not thin_or_edge <= truth_selected:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "Ground Truth thin/edge IDs must be selected truth."
            )
        thin_or_edge_retention = (
            len(selected & thin_or_edge) / len(thin_or_edge) if thin_or_edge else 1.0
        )
        thin_or_edge_available = True
    universe_size = len(truth_selected | truth_rejected | truth_ambiguous)
    metrics: dict[str, object] = {
        "targetPrecision": precision,
        "targetRecall": recall,
        "distractorLeakageCount": leakage_count,
        "distractorLeakageRate": (
            leakage_count / len(distractors) if distractors else 0.0
        ),
        "thinOrEdgeRetention": thin_or_edge_retention,
        "thinOrEdgeRetentionAvailable": thin_or_edge_available,
        "finalCandidateQuality": {
            "selectedCount": len(selected),
            "rejectedCount": len(rejected),
            "uncertainCount": len(uncertain),
            "uncertainRate": len(uncertain) / universe_size if universe_size else 0.0,
        },
    }
    gate_passed = (
        precision >= float(_SCORE_POLICY["minimumTargetPrecision"])
        and recall >= float(_SCORE_POLICY["minimumTargetRecall"])
        and leakage_count <= int(_SCORE_POLICY["maximumDistractorLeakageCount"])
    )
    return metrics, gate_passed


def score_depth_classified_negative_evidence_prediction(
    prediction_directory: Path,
    *,
    ground_truth_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Verify all prediction hashes, then open Ground Truth and score every method."""

    prediction_directory = prediction_directory.resolve()
    if ground_truth_path.resolve().is_relative_to(prediction_directory):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "Ground Truth must remain outside the sealed prediction."
        )
    if output_path.resolve().is_relative_to(prediction_directory):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "scores must not modify the sealed prediction."
        )
    _, records, manifest_sha256 = _verified_prediction(prediction_directory)

    # This is intentionally the first Ground Truth read.
    ground_truth = _read_json(ground_truth_path, "Benchmark Ground Truth")
    methods: list[dict[str, object]] = []
    for record in records:
        metrics, gate_passed = _score_candidate(record["candidate"], ground_truth)
        methods.append(
            {
                "recordKind": record["recordKind"],
                "recordDigest": record["recordDigest"],
                "method": deepcopy(record["method"]),
                "metrics": metrics,
                "qualityGatePassed": gate_passed,
                "runtimeSource": deepcopy(record["runtimeSource"]),
                "timingAndVram": deepcopy(record["timingAndVram"]),
                "bufferWrites": deepcopy(record["bufferWrites"]),
            }
        )
    baseline_passed = bool(methods[0]["qualityGatePassed"])
    result: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "artifactKind": SCORE_RECORD_KIND,
        "predictionManifestSha256": manifest_sha256,
        "groundTruthSha256": _sha256(ground_truth_path),
        "groundTruthClosedDuringPrediction": True,
        "inputIdentity": deepcopy(records[0]["inputIdentity"]),
        "inputIdentityDigest": records[0]["inputIdentityDigest"],
        "scorePolicy": deepcopy(_SCORE_POLICY),
        "baselineGatePassed": baseline_passed,
        "baselineResult": "passed" if baseline_passed else "failed",
        "variantCannotAlterBaselineResult": True,
        "methods": methods,
    }
    _write_json(output_path, result)
    return result


__all__ = [
    "BASELINE_METHOD_ID",
    "DepthClassifiedNegativeEvidenceBenchmarkError",
    "create_baseline_run_record",
    "create_experiment_input_identity",
    "create_variant_run_record",
    "load_depth_classified_negative_evidence_configuration",
    "persist_baseline_run_record",
    "persist_sidecar_failure",
    "persist_variant_run_record",
    "score_depth_classified_negative_evidence_prediction",
    "seal_depth_classified_negative_evidence_prediction",
]
