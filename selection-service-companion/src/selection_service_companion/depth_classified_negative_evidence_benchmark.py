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
import struct
from typing import Mapping, Sequence

from .depth_classified_negative_evidence_experiment import (
    EXPERIMENTAL_SCHEMA_VERSION,
    _validated_relation_config,
    validate_depth_classified_candidate_replay,
    validate_depth_classified_negative_evidence_sidecar,
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
    "predictionInputManifestSha256",
    "predictionInputManifestDigest",
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
    "benchmarkImplementationDigest",
}
_MEASUREMENT_BOUNDARY_KEYS = {
    "policyId",
    "warmupRuns",
    "measuredRuns",
    "latencyStatistic",
    "peakVramStatistic",
    "peakResetOwner",
    "bufferWriteMetric",
    "totalComposition",
}
_COST_MEASUREMENT_KEYS = {"measurementBoundary", "stages"}
_COST_STAGE_KEYS = {
    "stageId",
    "costKind",
    "measurementComposition",
    "latencyMilliseconds",
    "startVramBytes",
    "peakVramBytes",
    "endVramBytes",
    "retainedInputs",
    "retainedOutputsThroughReturn",
    "bufferWrites",
}
_BASELINE_COST_STAGES = (
    "productionBaseline",
    "baselineCandidateReplay",
)
_VARIANT_COST_STAGES = (
    "productionBaseline",
    "baselineCandidateReplay",
    "sharedCwedReadoutAcquisition",
    "referenceContributorAndClassificationSidecar",
    "variantCandidateReplay",
)
_BASELINE_TOTAL_COST_STAGE = "productionBaselineTotal"
_VARIANT_TOTAL_COST_STAGE = "shadowExperimentTotal"
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
    "predictionInputManifest",
    "predictionInputManifestSha256",
    "groundTruthAccess",
    "thinOrEdgeGroundTruth",
}
_PREDICTION_INPUT_MANIFEST_KEYS = {
    "schemaVersion",
    "manifestKind",
    "sceneId",
    "sceneSnapshot",
    "frameSet",
    "stableMasks",
    "evidenceWorkingSet",
    "manifestDigest",
}
_PREDICTION_SCENE_REFERENCE_KEYS = {"path", "sha256", "format", "gaussianCount"}
_PREDICTION_FRAME_SET_KEYS = {
    "resolution",
    "horizontalFovDegrees",
    "views",
}
_PREDICTION_VIEW_KEYS = {
    "viewId",
    "cameraToWorld",
    "stableMaskIndex",
    "stableMaskAreaPixels",
    "status",
}
_PREDICTION_MASK_REFERENCE_KEYS = {
    "path",
    "sha256",
    "archiveKeys",
    "tensorKey",
    "shape",
    "dtype",
}
_PREDICTION_WORKING_SET_KEYS = {
    "policyId",
    "policyDigest",
    "coreStableGaussianIdsSource",
    "contextStableGaussianIds",
}
_FORBIDDEN_PREDICTION_MANIFEST_KEYS = {
    "targetcount",
    "distractorcount",
    "groundtruth",
    "selectedcount",
    "rejected",
    "ambiguouscount",
    "rearsurfacecount",
    "targetstableidrange",
}
_FORBIDDEN_PREDICTION_MANIFEST_VALUES = (
    "ground_truth",
    "ground-truth",
    "groundtruth",
)
_PREDICTION_SCENE_SHA256 = (
    "sha256:0f31c4f659bf02f5927f132b38703005f1ffd82a019ee58cff277696b18e51bf"
)
_PREDICTION_SCENE_PROPERTIES = (
    "property float x",
    "property float y",
    "property float z",
    "property float f_dc_0",
    "property float f_dc_1",
    "property float f_dc_2",
    "property float opacity",
    "property float scale_0",
    "property float scale_1",
    "property float scale_2",
    "property float rot_0",
    "property float rot_1",
    "property float rot_2",
    "property float rot_3",
    "property uint stable_id",
)
_PREDICTION_SCENE_VERTEX = struct.Struct("<14fI")


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
    prediction_input_manifest_sha256: str,
    prediction_input_manifest_digest: str,
    deterministic_seed: str,
) -> dict[str, object]:
    """Bind the exact byte/runtime input shared by baseline and variants."""

    payload: dict[str, object] = {
        "sceneSnapshotDigest": scene_snapshot_digest,
        "cameraBindingsDigest": camera_bindings_digest,
        "stableMasksDigest": stable_masks_digest,
        "workingSetsDigest": working_sets_digest,
        "rendererRuntimeDigest": renderer_runtime_digest,
        "predictionInputManifestSha256": prediction_input_manifest_sha256,
        "predictionInputManifestDigest": prediction_input_manifest_digest,
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
        "predictionInputManifestSha256",
        "predictionInputManifestDigest",
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
                "benchmarkImplementationDigest",
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


def _validated_buffer_writes(value: object, label: str) -> dict[str, int]:
    if (
        not isinstance(value, Mapping)
        or "total" not in value
        or any(not isinstance(name, str) or not name for name in value)
        or any(
            not isinstance(count, int) or isinstance(count, bool) or count < 0
            for count in value.values()
        )
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"the {label} buffer-write record is invalid."
        )
    result = dict(value)
    if result["total"] != sum(
        count for name, count in result.items() if name != "total"
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"the {label} buffer-write total is inconsistent."
        )
    return result


def _validated_cost_stage(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _COST_STAGE_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "an experiment cost stage is incomplete."
        )
    stage_id = value["stageId"]
    cost_kind = value["costKind"]
    composition = value["measurementComposition"]
    latency = value["latencyMilliseconds"]
    memory_values = (
        value["startVramBytes"],
        value["peakVramBytes"],
        value["endVramBytes"],
    )
    retained_inputs = value["retainedInputs"]
    retained_outputs = value["retainedOutputsThroughReturn"]
    if (
        not isinstance(stage_id, str)
        or not stage_id
        or cost_kind not in {"measured-stage", "derived-total"}
        or not isinstance(composition, str)
        or (
            cost_kind == "measured-stage"
            and composition
            not in {
                "median-of-whole-stage-runs",
                "sum-of-per-view-medians/max-of-per-view-allocations",
            }
        )
        or (
            cost_kind == "derived-total"
            and composition != "sum-of-components/max-of-components"
        )
        or isinstance(latency, bool)
        or not isinstance(latency, (int, float))
        or not math.isfinite(float(latency))
        or float(latency) < 0.0
        or any(
            memory is not None
            and (
                isinstance(memory, bool)
                or not isinstance(memory, int)
                or memory < 0
            )
            for memory in memory_values
        )
        or not isinstance(retained_inputs, list)
        or not isinstance(retained_outputs, list)
        or any(
            not isinstance(name, str) or not name
            for name in [*retained_inputs, *retained_outputs]
        )
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "an experiment cost stage contains invalid timing, memory, or retention metadata."
        )
    if cost_kind == "measured-stage":
        if value["peakVramBytes"] is not None and (
            value["startVramBytes"] is None
            or value["endVramBytes"] is None
            or value["peakVramBytes"]
            < max(value["startVramBytes"], value["endVramBytes"])
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a measured GPU stage has inconsistent start/peak/end allocation."
            )
    elif value["startVramBytes"] is not None or value["endVramBytes"] is not None:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "a derived total must not claim measured start/end allocation."
        )
    return {
        "stageId": stage_id,
        "costKind": cost_kind,
        "measurementComposition": composition,
        "latencyMilliseconds": float(latency),
        "startVramBytes": value["startVramBytes"],
        "peakVramBytes": value["peakVramBytes"],
        "endVramBytes": value["endVramBytes"],
        "retainedInputs": list(retained_inputs),
        "retainedOutputsThroughReturn": list(retained_outputs),
        "bufferWrites": _validated_buffer_writes(
            value["bufferWrites"], f"{stage_id} stage"
        ),
    }


def _validated_cost_measurement(
    value: object,
    *,
    expected_component_stages: Sequence[str],
    expected_total_stage: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _COST_MEASUREMENT_KEYS:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment cost measurement is incomplete."
        )
    boundary = value["measurementBoundary"]
    if (
        not isinstance(boundary, Mapping)
        or set(boundary) != _MEASUREMENT_BOUNDARY_KEYS
        or boundary.get("policyId")
        != "audited-component-cost/experimental-reference-v1"
        or boundary.get("warmupRuns") != 1
        or boundary.get("measuredRuns") != 3
        or boundary.get("latencyStatistic") != "median"
        or boundary.get("peakVramStatistic") != "maximum"
        or boundary.get("peakResetOwner") != "locked-renderer-call"
        or boundary.get("bufferWriteMetric")
        != "logical-output-channel-elements"
        or boundary.get("totalComposition")
        != "derived-sum-of-component-medians/max-of-component-peaks"
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment cost measurement boundary is invalid."
        )
    raw_stages = value["stages"]
    if not isinstance(raw_stages, list):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment cost stages must be ordered."
        )
    stages = [_validated_cost_stage(stage) for stage in raw_stages]
    expected_ids = [*expected_component_stages, expected_total_stage]
    if [stage["stageId"] for stage in stages] != expected_ids:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the experiment cost stages do not match the method boundary."
        )
    components = stages[:-1]
    total = stages[-1]
    component_latency = sum(
        float(stage["latencyMilliseconds"]) for stage in components
    )
    component_peaks = [
        int(stage["peakVramBytes"])
        for stage in components
        if stage["peakVramBytes"] is not None
    ]
    component_writes = sum(
        int(stage["bufferWrites"]["total"]) for stage in components
    )
    if (
        any(stage["costKind"] != "measured-stage" for stage in components)
        or total["costKind"] != "derived-total"
        or not math.isclose(
            float(total["latencyMilliseconds"]),
            component_latency,
            rel_tol=1e-12,
            abs_tol=1e-9,
        )
        or total["peakVramBytes"] != (max(component_peaks) if component_peaks else 0)
        or total["startVramBytes"] is not None
        or total["endVramBytes"] is not None
        or total["retainedInputs"] != []
        or total["retainedOutputsThroughReturn"] != []
        or total["bufferWrites"]
        != {"componentStageWrites": component_writes, "total": component_writes}
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the end-to-end method cost does not compose from its audited stages."
        )
    return {
        "measurementBoundary": deepcopy(dict(boundary)),
        "stages": stages,
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
    cost_measurement: object,
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
        "costMeasurement": _validated_cost_measurement(
            cost_measurement,
            expected_component_stages=_BASELINE_COST_STAGES,
            expected_total_stage=_BASELINE_TOTAL_COST_STAGE,
        ),
        "outputDigests": {
            "baselineArtifacts": artifacts,
            "candidateReplay": candidate["replayDigest"],
        },
        "candidate": candidate,
    }
    return {**payload, "recordDigest": canonical_json_digest(payload)}


def create_variant_run_record(
    *,
    input_identity: object,
    replay_config: object,
    sidecar_digests: Sequence[str],
    candidate_replay: object,
    runtime_source: object,
    cost_measurement: object,
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
        "costMeasurement": _validated_cost_measurement(
            cost_measurement,
            expected_component_stages=_VARIANT_COST_STAGES,
            expected_total_stage=_VARIANT_TOTAL_COST_STAGE,
        ),
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
    if payload.get("groundTruthAccess") != "closed-during-prediction":
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "Ground Truth was not closed during prediction."
        )
    if expected_kind == VARIANT_RECORD_KIND:
        validate_depth_classified_replay_config(payload["method"])
        _validated_cost_measurement(
            payload["costMeasurement"],
            expected_component_stages=_VARIANT_COST_STAGES,
            expected_total_stage=_VARIANT_TOTAL_COST_STAGE,
        )
    else:
        _validated_cost_measurement(
            payload["costMeasurement"],
            expected_component_stages=_BASELINE_COST_STAGES,
            expected_total_stage=_BASELINE_TOTAL_COST_STAGE,
        )
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
        != "depth-moment-minimum-m0/qualified-v1"
        or isinstance(depth_policy.get("minimumM0"), bool)
        or not isinstance(depth_policy.get("minimumM0"), (int, float))
        or not math.isfinite(float(depth_policy["minimumM0"]))
        or float(depth_policy["minimumM0"]) != (1.0 / 255.0)
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
            "peakVramStatistic",
            "peakResetOwner",
            "bufferWriteMeasurement",
            "totalComposition",
        }
        or measurement.get("warmupRuns") != 1
        or measurement.get("measuredRuns") != 3
        or measurement.get("latencyStatistic") != "median"
        or measurement.get("peakVramMeasurement") != "torch.cuda.max_memory_allocated"
        or measurement.get("peakVramStatistic") != "maximum"
        or measurement.get("peakResetOwner") != "locked-renderer-call"
        or measurement.get("bufferWriteMeasurement")
        != "logical-output-channel-elements"
        or measurement.get("totalComposition")
        != "derived-sum-of-component-medians/max-of-component-peaks"
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
        relative = scene["predictionInputManifest"]
        expected_digest = scene["predictionInputManifestSha256"]
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not _is_digest(expected_digest)
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "an experiment prediction-input manifest path or digest is invalid."
            )
        manifest_path = (configuration_root / relative).resolve()
        if (
            not manifest_path.is_relative_to(configuration_root)
            or not manifest_path.is_file()
            or _sha256(manifest_path) != expected_digest
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                f"the immutable prediction-input manifest does not match: {relative}."
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


def _normalized_manifest_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _assert_prediction_safe_manifest(value: object, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if (
                not isinstance(key, str)
                or _normalized_manifest_key(key)
                in _FORBIDDEN_PREDICTION_MANIFEST_KEYS
            ):
                raise DepthClassifiedNegativeEvidenceBenchmarkError(
                    f"{label} contains a Ground Truth-bearing field."
                )
            _assert_prediction_safe_manifest(item, label)
        return
    if isinstance(value, list):
        for item in value:
            _assert_prediction_safe_manifest(item, label)
        return
    if (
        isinstance(value, str)
        and value != "whole-target-splat/pre-ground-truth-v1"
        and any(
            forbidden in value.lower()
            for forbidden in _FORBIDDEN_PREDICTION_MANIFEST_VALUES
        )
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"{label} names a Ground Truth-bearing fixture."
        )


def _verified_prediction_input_file(
    *,
    configuration_root: Path,
    reference: object,
    label: str,
) -> Path:
    if (
        not isinstance(reference, Mapping)
        or set(reference) != {"path", "sha256"}
        or not isinstance(reference.get("path"), str)
        or Path(str(reference["path"])).is_absolute()
        or ".." in Path(str(reference["path"])).parts
        or not _is_digest(reference.get("sha256"))
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"the {label} prediction input reference is invalid."
        )
    path = (configuration_root / str(reference["path"])).resolve()
    if (
        not path.is_relative_to(configuration_root)
        or not path.is_file()
        or _sha256(path) != reference["sha256"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"the immutable {label} prediction input does not match."
        )
    return path


def load_depth_classified_negative_evidence_prediction_input(
    configuration_path: Path,
    *,
    scene_id: str,
) -> dict[str, object]:
    """Open only the sealed pre-Ground-Truth prediction input boundary."""

    configuration = load_depth_classified_negative_evidence_configuration(
        configuration_path
    )
    matches = [
        scene for scene in configuration["scenes"] if scene["sceneId"] == scene_id
    ]
    if len(matches) != 1:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed experiment has no unique prediction scene."
        )
    scene = deepcopy(matches[0])
    configuration_root = configuration_path.resolve().parent
    manifest_path = _verified_prediction_input_file(
        configuration_root=configuration_root,
        reference={
            "path": scene["predictionInputManifest"],
            "sha256": scene["predictionInputManifestSha256"],
        },
        label="prediction-input manifest",
    )
    manifest = _read_json(manifest_path, "prediction-input manifest")
    _assert_prediction_safe_manifest(manifest, "prediction-input manifest")
    manifest_payload = {
        key: deepcopy(item)
        for key, item in manifest.items()
        if key != "manifestDigest"
    }
    scene_reference = manifest.get("sceneSnapshot")
    frame_set = manifest.get("frameSet")
    mask_reference = manifest.get("stableMasks")
    working_set = manifest.get("evidenceWorkingSet")
    if (
        set(manifest) != _PREDICTION_INPUT_MANIFEST_KEYS
        or manifest.get("schemaVersion") != EXPERIMENTAL_SCHEMA_VERSION
        or manifest.get("manifestKind")
        != "depth-classified-negative-evidence-input/experimental-reference-v1"
        or manifest.get("sceneId") != scene_id
        or manifest.get("manifestDigest") != canonical_json_digest(manifest_payload)
        or not isinstance(scene_reference, Mapping)
        or set(scene_reference) != _PREDICTION_SCENE_REFERENCE_KEYS
        or scene_reference.get("sha256") != _PREDICTION_SCENE_SHA256
        or scene_reference.get("format") != "controlled-overlap-ply/no-class-label-v1"
        or scene_reference.get("gaussianCount") != 16384
        or not isinstance(frame_set, Mapping)
        or set(frame_set) != _PREDICTION_FRAME_SET_KEYS
        or not isinstance(mask_reference, Mapping)
        or set(mask_reference) != _PREDICTION_MASK_REFERENCE_KEYS
        or not isinstance(working_set, Mapping)
        or set(working_set) != _PREDICTION_WORKING_SET_KEYS
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the prediction-input manifest contract is invalid."
        )
    scene_path = _verified_prediction_input_file(
        configuration_root=configuration_root,
        reference={"path": scene_reference["path"], "sha256": scene_reference["sha256"]},
        label="label-free Scene Snapshot",
    )
    masks_path = _verified_prediction_input_file(
        configuration_root=configuration_root,
        reference={"path": mask_reference["path"], "sha256": mask_reference["sha256"]},
        label="masks-only archive",
    )
    resolution = frame_set.get("resolution")
    horizontal_fov = frame_set.get("horizontalFovDegrees")
    views = frame_set.get("views")
    if (
        not isinstance(resolution, list)
        or len(resolution) != 2
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in resolution
        )
        or isinstance(horizontal_fov, bool)
        or not isinstance(horizontal_fov, (int, float))
        or not math.isfinite(float(horizontal_fov))
        or not 0.0 < float(horizontal_fov) < 180.0
        or not isinstance(views, list)
        or not views
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the prediction Frame Set is invalid."
        )
    known_view_ids: set[str] = set()
    known_mask_indices: set[int] = set()
    for view in views:
        if not isinstance(view, Mapping) or set(view) != _PREDICTION_VIEW_KEYS:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a prediction View is incomplete."
            )
        view_id = view.get("viewId")
        camera = view.get("cameraToWorld")
        mask_index = view.get("stableMaskIndex")
        mask_area = view.get("stableMaskAreaPixels")
        if (
            not isinstance(view_id, str)
            or not view_id
            or view_id in known_view_ids
            or view.get("status") != "accepted"
            or not isinstance(camera, list)
            or len(camera) != 4
            or any(not isinstance(row, list) or len(row) != 4 for row in camera)
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for row in camera
                for value in row
            )
            or not isinstance(mask_index, int)
            or isinstance(mask_index, bool)
            or mask_index < 0
            or mask_index in known_mask_indices
            or not isinstance(mask_area, int)
            or isinstance(mask_area, bool)
            or mask_area < 0
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a prediction View identity, camera, or Stable Mask binding is invalid."
            )
        known_view_ids.add(view_id)
        known_mask_indices.add(mask_index)
    working_set_payload = {
        "policyId": working_set.get("policyId"),
        "coreStableGaussianIdsSource": working_set.get(
            "coreStableGaussianIdsSource"
        ),
        "contextStableGaussianIds": working_set.get("contextStableGaussianIds"),
    }
    if (
        working_set.get("policyId")
        != "whole-target-splat/pre-ground-truth-v1"
        or working_set.get("policyDigest")
        != canonical_json_digest(working_set_payload)
        or working_set.get("coreStableGaussianIdsSource")
        != "validated-scene-snapshot-order"
        or working_set.get("contextStableGaussianIds") != []
        or mask_reference.get("archiveKeys") != ["masks"]
        or mask_reference.get("tensorKey") != "masks"
        or mask_reference.get("shape") != [len(views), resolution[1], resolution[0]]
        or mask_reference.get("dtype") != "bool"
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the masks-only archive or pre-Ground-Truth Working Set policy is invalid."
        )
    try:
        import numpy as np

        with np.load(masks_path, allow_pickle=False) as archive:
            if archive.files != ["masks"]:
                raise DepthClassifiedNegativeEvidenceBenchmarkError(
                    "the prediction archive contains fields other than Stable Masks."
                )
            masks = archive["masks"]
            if list(masks.shape) != mask_reference["shape"] or str(masks.dtype) != "bool":
                raise DepthClassifiedNegativeEvidenceBenchmarkError(
                    "the prediction Stable Mask tensor does not match its manifest."
                )
            stable_masks = masks.copy()
    except DepthClassifiedNegativeEvidenceBenchmarkError:
        raise
    except Exception as error:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the masks-only prediction archive is unavailable or invalid."
        ) from error
    for view in views:
        if int(stable_masks[int(view["stableMaskIndex"])].sum()) != int(
            view["stableMaskAreaPixels"]
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a prediction Stable Mask area does not match its sealed View."
            )
    return {
        "configuration": configuration,
        "scene": scene,
        "manifest": deepcopy(manifest),
        "manifestPath": manifest_path,
        "sceneSnapshotPath": scene_path,
        "stableMasksPath": masks_path,
        "stableMasks": stable_masks,
        "frameSet": deepcopy(dict(frame_set)),
        "evidenceWorkingSet": deepcopy(dict(working_set)),
    }


def build_depth_classified_negative_evidence_prediction_snapshot(
    path: Path,
) -> dict[str, object]:
    """Read the label-free controlled-overlap Scene Snapshot used by prediction."""

    source = path.read_bytes()
    if f"sha256:{hashlib.sha256(source).hexdigest()}" != _PREDICTION_SCENE_SHA256:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the label-free prediction Scene Snapshot digest is invalid."
        )
    marker = b"end_header\n"
    header_end = source.find(marker)
    if header_end < 0:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the label-free prediction Scene Snapshot has no complete header."
        )
    header = source[: header_end + len(marker)].decode("ascii").splitlines()
    if header[:2] != ["ply", "format binary_little_endian 1.0"]:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the label-free prediction Scene Snapshot encoding is unsupported."
        )
    try:
        element = next(line for line in header if line.startswith("element vertex "))
        gaussian_count = int(element.removeprefix("element vertex "))
    except (StopIteration, ValueError) as error:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the label-free prediction Scene Snapshot count is invalid."
        ) from error
    properties = tuple(line for line in header if line.startswith("property "))
    if properties != _PREDICTION_SCENE_PROPERTIES:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the prediction Scene Snapshot must not contain benchmark class labels."
        )
    payload = source[header_end + len(marker) :]
    if len(payload) != gaussian_count * _PREDICTION_SCENE_VERTEX.size:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the label-free prediction Scene Snapshot payload is incomplete."
        )
    gaussians: list[dict[str, object]] = []
    known_ids: set[int] = set()
    for values in _PREDICTION_SCENE_VERTEX.iter_unpack(payload):
        stable_id = values[14]
        if stable_id in known_ids or stable_id > _MAX_STABLE_GAUSSIAN_ID:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "the label-free prediction Stable Gaussian IDs are invalid."
            )
        known_ids.add(stable_id)
        gaussians.append(
            {
                "stableId": stable_id,
                "mean": list(values[0:3]),
                "rotation": [values[11], values[12], values[13], values[10]],
                "logScale": list(values[7:10]),
                "logitOpacity": values[6],
                "dc": list(values[3:6]),
                "sh": [],
            }
        )
    return {
        "protocolVersion": "1",
        "sceneId": "controlled-overlap",
        "sceneVersion": _PREDICTION_SCENE_SHA256,
        "gaussianCount": gaussian_count,
        "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
        "attributeSchema": (
            "mean:f32x3;rotation:f32x4;logScale:f32x3;"
            "logitOpacity:f32;dc:f32x3;sh:f32x0"
        ),
        "stableIdSchema": "uint32",
        "appearancePolicy": "effective-editor-dc-sh-bands-0",
        "renderConfiguration": {
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.04, 0.04, 0.04, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        "gaussians": gaussians,
    }


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


def _canonical_artifact(path: Path, *, digest_field: str, label: str) -> dict[str, object]:
    artifact = _read_json(path, label)
    digest = artifact.get(digest_field)
    payload = {
        key: deepcopy(item)
        for key, item in artifact.items()
        if key != digest_field
    }
    if not _is_digest(digest) or canonical_json_digest(payload) != digest:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            f"the persisted {label} canonical digest is invalid."
        )
    return artifact


def _artifact_index_entry(
    prediction_directory: Path,
    path: Path,
    *,
    kind: str,
    digest: str | None = None,
    method_id: str | None = None,
    view_id: str | None = None,
) -> dict[str, object]:
    resolved = path.resolve()
    if not resolved.is_relative_to(prediction_directory.resolve()) or not path.is_file():
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "a persisted prediction artifact is unavailable or escapes its directory."
        )
    result: dict[str, object] = {
        "kind": kind,
        "path": path.relative_to(prediction_directory).as_posix(),
        "sha256": _sha256(path),
    }
    if digest is not None:
        result["artifactDigest"] = digest
    if method_id is not None:
        result["methodId"] = method_id
    if view_id is not None:
        result["viewId"] = view_id
    return result


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
    variant_records: list[dict[str, object]] = []
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
        variant_records.append(variant)
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

    input_manifest_path = prediction_directory / "prediction-input-manifest.json"
    input_manifest = _canonical_artifact(
        input_manifest_path,
        digest_field="manifestDigest",
        label="prediction-input manifest",
    )
    if (
        _sha256(input_manifest_path)
        != baseline["inputIdentity"]["predictionInputManifestSha256"]
        or input_manifest["manifestDigest"]
        != baseline["inputIdentity"]["predictionInputManifestDigest"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the persisted prediction-input manifest does not match the run identity."
        )
    baseline_bundle_path = prediction_directory / "baseline-artifacts.json"
    baseline_bundle = _read_json(baseline_bundle_path, "baseline artifact bundle")
    baseline_views = baseline_bundle.get("views")
    baseline_candidate = baseline_bundle.get("candidateReplay")
    if (
        baseline_bundle.get("methodId") != BASELINE_METHOD_ID
        or not isinstance(baseline_views, list)
        or [
            view.get("artifact", {}).get("artifactDigest")
            for view in baseline_views
            if isinstance(view, Mapping)
        ]
        != baseline["outputDigests"]["baselineArtifacts"]
        or _validated_candidate_replay(baseline_candidate) != baseline["candidate"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the persisted baseline artifact bundle does not match its run record."
        )
    artifacts: list[dict[str, object]] = [
        _artifact_index_entry(
            prediction_directory,
            input_manifest_path,
            kind="prediction-input-manifest",
            digest=str(input_manifest["manifestDigest"]),
        ),
        _artifact_index_entry(
            prediction_directory,
            baseline_bundle_path,
            kind="baseline-artifact-bundle",
        ),
    ]
    sidecar_paths = sorted((prediction_directory / "sidecars").glob("*.json"))
    sidecars = [
        validate_depth_classified_negative_evidence_sidecar(
            _canonical_artifact(
                sidecar_path,
                digest_field="artifactDigest",
                label="classified sidecar",
            )
        )
        for sidecar_path in sidecar_paths
    ]
    if any(
        sidecar.get("depthMomentIdentity", {}).get("viewId") != path.stem
        for path, sidecar in zip(sidecar_paths, sidecars, strict=True)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "a persisted sidecar was swapped across View identities."
        )
    sidecar_digests = [str(sidecar["artifactDigest"]) for sidecar in sidecars]
    if not sidecars or any(
        record["outputDigests"]["classifiedDiagnosticSidecars"] != sidecar_digests
        for record in variant_records
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the persisted sidecar set does not match every variant run record."
        )
    artifacts.extend(
        _artifact_index_entry(
            prediction_directory,
            path,
            kind="classified-sidecar",
            digest=str(sidecar["artifactDigest"]),
            view_id=path.stem,
        )
        for path, sidecar in zip(sidecar_paths, sidecars, strict=True)
    )
    expected_replay_paths = [
        prediction_directory / "candidate-replays" / f"variant-{ordinal:03d}.json"
        for ordinal in range(len(methods))
    ]
    if sorted((prediction_directory / "candidate-replays").glob("*.json")) != sorted(
        expected_replay_paths
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the persisted Candidate replay directory contains unindexed files."
        )
    for ordinal, method_id in enumerate(methods):
        replay_path = (
            prediction_directory
            / "candidate-replays"
            / f"variant-{ordinal:03d}.json"
        )
        replay = validate_depth_classified_candidate_replay(
            _canonical_artifact(
                replay_path,
                digest_field="replayDigest",
                label="Candidate replay",
            )
        )
        variant = variant_records[ordinal]
        replay_candidate = _validated_candidate_replay(replay)
        if (
            replay.get("method", {}).get("methodId") != method_id
            or replay_candidate != variant["candidate"]
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a persisted Candidate replay does not match its variant run record."
            )
        artifacts.append(
            _artifact_index_entry(
                prediction_directory,
                replay_path,
                kind="candidate-replay",
                digest=str(replay["replayDigest"]),
                method_id=method_id,
            )
        )
    artifact_paths = [str(artifact["path"]) for artifact in artifacts]
    if len(set(artifact_paths)) != len(artifact_paths):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the prediction artifact index contains duplicate paths."
        )
    manifest: dict[str, object] = {
        "schemaVersion": EXPERIMENTAL_SCHEMA_VERSION,
        "artifactKind": PREDICTION_MANIFEST_KIND,
        "status": "prediction-complete",
        "inputIdentityDigest": baseline["inputIdentityDigest"],
        "groundTruthAccess": "closed-during-prediction",
        "records": records,
        "artifacts": artifacts,
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

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed prediction does not index its persisted artifacts."
        )
    artifact_paths = [
        entry.get("path") for entry in artifacts if isinstance(entry, Mapping)
    ]
    if (
        len(artifact_paths) != len(artifacts)
        or any(not isinstance(path, str) for path in artifact_paths)
        or len(set(artifact_paths)) != len(artifact_paths)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed prediction artifact index has malformed or duplicate paths."
        )
    indexed_generated_paths = {
        str(path)
        for path in artifact_paths
        if str(path).startswith("sidecars/")
        or str(path).startswith("candidate-replays/")
    }
    actual_generated_paths = {
        path.relative_to(prediction_directory).as_posix()
        for directory in ("sidecars", "candidate-replays")
        for path in (prediction_directory / directory).glob("*.json")
    }
    if indexed_generated_paths != actual_generated_paths:
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed prediction contains unindexed sidecar or replay files."
        )
    input_entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping)
        and entry.get("kind") == "prediction-input-manifest"
    ]
    baseline_entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping)
        and entry.get("kind") == "baseline-artifact-bundle"
    ]
    sidecar_entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping) and entry.get("kind") == "classified-sidecar"
    ]
    replay_entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping) and entry.get("kind") == "candidate-replay"
    ]
    if (
        len(input_entries) != 1
        or len(baseline_entries) != 1
        or not sidecar_entries
        or len(replay_entries) != len(verified) - 1
        or len(artifacts)
        != len(input_entries)
        + len(baseline_entries)
        + len(sidecar_entries)
        + len(replay_entries)
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed prediction artifact index is incomplete or has unknown kinds."
        )

    def indexed_path(entry: Mapping[str, object]) -> Path:
        relative = entry.get("path")
        if not isinstance(relative, str):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed prediction artifact path is malformed."
            )
        path = (prediction_directory / relative).resolve()
        if (
            not path.is_relative_to(prediction_directory.resolve())
            or not path.is_file()
            or entry.get("sha256") != _sha256(path)
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed prediction artifact hash does not match."
            )
        return path

    input_manifest = _canonical_artifact(
        indexed_path(input_entries[0]),
        digest_field="manifestDigest",
        label="sealed prediction-input manifest",
    )
    if (
        input_entries[0].get("artifactDigest") != input_manifest["manifestDigest"]
        or input_entries[0].get("sha256")
        != verified[0]["inputIdentity"]["predictionInputManifestSha256"]
        or input_manifest["manifestDigest"]
        != verified[0]["inputIdentity"]["predictionInputManifestDigest"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed prediction-input manifest no longer matches the run identity."
        )
    baseline_bundle = _read_json(
        indexed_path(baseline_entries[0]), "sealed baseline artifact bundle"
    )
    baseline_views = baseline_bundle.get("views")
    if (
        baseline_bundle.get("methodId") != BASELINE_METHOD_ID
        or not isinstance(baseline_views, list)
        or [
            view.get("artifact", {}).get("artifactDigest")
            for view in baseline_views
            if isinstance(view, Mapping)
        ]
        != verified[0]["outputDigests"]["baselineArtifacts"]
        or _validated_candidate_replay(baseline_bundle.get("candidateReplay"))
        != verified[0]["candidate"]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed baseline artifact bundle no longer matches its run record."
        )
    verified_sidecar_digests: list[str] = []
    known_sidecar_views: set[str] = set()
    baseline_view_ids = {
        str(view["currentInput"]["view"]["viewId"])
        for view in baseline_views
    }
    for entry in sidecar_entries:
        sidecar_path = indexed_path(entry)
        view_id = entry.get("viewId")
        sidecar = validate_depth_classified_negative_evidence_sidecar(
            _canonical_artifact(
                sidecar_path,
                digest_field="artifactDigest",
                label="sealed classified sidecar",
            )
        )
        if (
            not isinstance(view_id, str)
            or view_id in known_sidecar_views
            or sidecar_path.stem != view_id
            or sidecar.get("depthMomentIdentity", {}).get("viewId") != view_id
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed sidecar View identity is missing, duplicated, or swapped."
            )
        known_sidecar_views.add(view_id)
        if entry.get("artifactDigest") != sidecar["artifactDigest"]:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed sidecar canonical digest does not match its index."
            )
        verified_sidecar_digests.append(str(sidecar["artifactDigest"]))
    if known_sidecar_views != baseline_view_ids or any(
        record["outputDigests"]["classifiedDiagnosticSidecars"]
        != verified_sidecar_digests
        for record in verified[1:]
    ):
        raise DepthClassifiedNegativeEvidenceBenchmarkError(
            "the sealed sidecar set no longer matches the variant run records."
        )
    replays_by_method: dict[str, dict[str, object]] = {}
    for entry in replay_entries:
        method_id = entry.get("methodId")
        replay = validate_depth_classified_candidate_replay(
            _canonical_artifact(
                indexed_path(entry),
                digest_field="replayDigest",
                label="sealed Candidate replay",
            )
        )
        if (
            not isinstance(method_id, str)
            or method_id in replays_by_method
            or entry.get("artifactDigest") != replay["replayDigest"]
            or replay.get("method", {}).get("methodId") != method_id
            or replay.get("sourceBaselineArtifactDigests")
            != verified[0]["outputDigests"]["baselineArtifacts"]
            or replay.get("sourceSidecarDigests") != verified_sidecar_digests
        ):
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed Candidate replay identity does not match its index."
            )
        replays_by_method[method_id] = replay
    for record in verified[1:]:
        method_id = str(record["method"]["methodId"])
        replay = replays_by_method.get(method_id)
        if replay is None or _validated_candidate_replay(replay) != record["candidate"]:
            raise DepthClassifiedNegativeEvidenceBenchmarkError(
                "a sealed Candidate replay no longer matches its run record."
            )
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
                "costMeasurement": deepcopy(record["costMeasurement"]),
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
    "build_depth_classified_negative_evidence_prediction_snapshot",
    "create_baseline_run_record",
    "create_experiment_input_identity",
    "create_variant_run_record",
    "load_depth_classified_negative_evidence_configuration",
    "load_depth_classified_negative_evidence_prediction_input",
    "persist_baseline_run_record",
    "persist_sidecar_failure",
    "persist_variant_run_record",
    "score_depth_classified_negative_evidence_prediction",
    "seal_depth_classified_negative_evidence_prediction",
]
