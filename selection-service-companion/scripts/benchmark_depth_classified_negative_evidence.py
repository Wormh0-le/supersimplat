#!/usr/bin/env python3
"""Run, independently score, and report the sealed V2AX experiment."""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Mapping

from selection_service_companion.depth_classified_negative_evidence_benchmark import (
    BASELINE_METHOD_ID,
    build_depth_classified_negative_evidence_prediction_snapshot,
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
from selection_service_companion.depth_classified_negative_evidence_experiment import (
    ProjectedDepthRowsRecord,
    build_depth_classified_negative_evidence_sidecar,
    exact_projected_depth_rows_equal,
    replay_depth_classified_negative_evidence,
)
from selection_service_companion.depth_moment_qualification import (
    DepthMomentInternalCapability,
    load_internal_depth_moment_capability,
)
from selection_service_companion.depth_moment_readout import (
    DepthMomentReadoutRecord,
    DepthMomentTelemetry,
    create_depth_moment_readout_identity,
)
from selection_service_companion.depth_moments import DepthMomentValidityPolicy
from selection_service_companion.digests import canonical_json_digest
from selection_service_companion.direct_gaussian_evidence import (
    DIRECT_EVIDENCE_ABI_VERSION,
    DIRECT_EVIDENCE_BACKEND_ID,
    DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    DIRECT_EVIDENCE_SOURCE_REVISION,
)
from selection_service_companion.gaussian_evidence_contract import (
    admit_gaussian_evidence,
    create_evidence_working_set,
    create_gaussian_evidence_artifact,
)
from selection_service_companion.gsplat_renderer import (
    LockedGsplatBackend,
    validate_supported_snapshot,
)
from selection_service_companion.reference_gaussian_evidence import (
    default_reference_evidence_policy,
    typed_pixel_evidence_weights,
)
from selection_service_companion.reference_gaussian_evidence_aggregation import (
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
)
from selection_service_companion.renderer_runtime import (
    current_renderer_runtime,
)


SCRIPT_ROOT = Path(__file__).resolve().parent
COMPANION_ROOT = SCRIPT_ROOT.parent
_PRODUCTION_MASS_ATOL = 2e-6
_PRODUCTION_MASS_RTOL = 1e-5

DEFAULT_CONFIGURATION = (
    COMPANION_ROOT
    / "tests/fixtures/ai-select-v1/depth-classified-negative-evidence-v1.json"
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)

    predict = commands.add_parser("predict")
    predict.add_argument("--configuration", type=Path, default=DEFAULT_CONFIGURATION)
    predict.add_argument("--scene-id", required=True)
    predict.add_argument("--seed", required=True)
    predict.add_argument("--output", type=Path, required=True)

    score = commands.add_parser("score")
    score.add_argument("--prediction", type=Path, required=True)
    score.add_argument("--ground-truth", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)

    report = commands.add_parser("report")
    report.add_argument("--configuration", type=Path, default=DEFAULT_CONFIGURATION)
    report.add_argument("--scores", type=Path, nargs="+", required=True)
    report.add_argument("--output", type=Path, required=True)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _write_json(path: Path, value: object) -> None:
    _write_text(
        path,
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )


def _tensor_digest(label: str, *tensors: object) -> str:
    import torch

    digest = hashlib.sha256(label.encode("utf-8"))
    for tensor in tensors:
        if not isinstance(tensor, torch.Tensor):
            raise TypeError("accepted contribution identity requires torch tensors")
        owned = tensor.detach().contiguous().cpu()
        digest.update(str(owned.dtype).encode("ascii"))
        digest.update(json.dumps(list(owned.shape)).encode("ascii"))
        digest.update(owned.numpy().tobytes(order="C"))
    return f"sha256:{digest.hexdigest()}"


def _benchmark_implementation_digest() -> str:
    files = (
        Path(__file__).resolve(),
        COMPANION_ROOT
        / "src/selection_service_companion/depth_classified_negative_evidence_benchmark.py",
        COMPANION_ROOT
        / "src/selection_service_companion/depth_classified_negative_evidence_experiment.py",
        COMPANION_ROOT / "src/selection_service_companion/gsplat_renderer.py",
        COMPANION_ROOT
        / "src/selection_service_companion/direct_gaussian_evidence.py",
    )
    return canonical_json_digest(
        {path.relative_to(COMPANION_ROOT).as_posix(): _sha256(path) for path in files}
    )


def _buffer_writes(**channels: int) -> dict[str, int]:
    return {**channels, "total": sum(channels.values())}


def _cost_stage(
    *,
    stage_id: str,
    latency_ms: float,
    start_vram_bytes: int | None,
    peak_vram_bytes: int | None,
    end_vram_bytes: int | None,
    retained_inputs: list[str],
    retained_outputs: list[str],
    buffer_writes: dict[str, int],
    measurement_composition: str = "median-of-whole-stage-runs",
) -> dict[str, object]:
    return {
        "stageId": stage_id,
        "costKind": "measured-stage",
        "measurementComposition": measurement_composition,
        "latencyMilliseconds": latency_ms,
        "startVramBytes": start_vram_bytes,
        "peakVramBytes": peak_vram_bytes,
        "endVramBytes": end_vram_bytes,
        "retainedInputs": retained_inputs,
        "retainedOutputsThroughReturn": retained_outputs,
        "bufferWrites": buffer_writes,
    }


def _cost_measurement(
    measurement: Mapping[str, object],
    *,
    components: list[dict[str, object]],
    total_stage_id: str,
) -> dict[str, object]:
    latency = sum(float(stage["latencyMilliseconds"]) for stage in components)
    peaks = [
        int(stage["peakVramBytes"])
        for stage in components
        if stage["peakVramBytes"] is not None
    ]
    writes = sum(int(stage["bufferWrites"]["total"]) for stage in components)
    total = {
        "stageId": total_stage_id,
        "costKind": "derived-total",
        "measurementComposition": "sum-of-components/max-of-components",
        "latencyMilliseconds": latency,
        "startVramBytes": None,
        "peakVramBytes": max(peaks) if peaks else 0,
        "endVramBytes": None,
        "retainedInputs": [],
        "retainedOutputsThroughReturn": [],
        "bufferWrites": _buffer_writes(componentStageWrites=writes),
    }
    return {
        "measurementBoundary": {
            "policyId": "audited-component-cost/experimental-reference-v1",
            "warmupRuns": measurement["warmupRuns"],
            "measuredRuns": measurement["measuredRuns"],
            "latencyStatistic": measurement["latencyStatistic"],
            "peakVramStatistic": measurement["peakVramStatistic"],
            "peakResetOwner": measurement["peakResetOwner"],
            "bufferWriteMetric": measurement["bufferWriteMeasurement"],
            "totalComposition": measurement["totalComposition"],
        },
        "stages": [*components, total],
    }


def _camera(
    frame: Mapping[str, object], frame_set: Mapping[str, object]
) -> dict[str, object]:
    import numpy as np

    width, height = (int(value) for value in frame_set["resolution"])
    if width <= 0 or height <= 0:
        raise ValueError("the configured Frame Set resolution is invalid")
    c2w = np.asarray(frame["cameraToWorld"], dtype=np.float32)
    if c2w.shape != (4, 4) or not np.isfinite(c2w).all():
        raise ValueError("the configured CameraBinding is invalid")
    w2c = np.linalg.inv(c2w).astype(np.float32)
    focal = width / (
        2.0 * math.tan(math.radians(float(frame_set["horizontalFovDegrees"])) / 2.0)
    )
    return {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": w2c.reshape(-1).tolist(),
        "intrinsics": [
            focal,
            0.0,
            width / 2.0,
            0.0,
            focal,
            height / 2.0,
            0.0,
            0.0,
            1.0,
        ],
        "nearPlane": 0.01,
        "farPlane": 20.0,
    }


def _mask_artifact(mask: object) -> dict[str, object]:
    import numpy as np

    binary = np.asarray(mask, dtype=bool)
    if binary.ndim != 2:
        raise ValueError("the configured Stable Mask must be two-dimensional")
    height, width = binary.shape
    packed = np.packbits(binary.reshape(-1), bitorder="little").tobytes()
    return {
        "encoding": "bitset-lsb-v1",
        "width": width,
        "height": height,
        "data": base64.b64encode(packed).decode("ascii"),
        "digest": f"sha256:{hashlib.sha256(packed).hexdigest()}",
    }


def _png_digest(rgb_bytes: bytes, width: int, height: int) -> str:
    from PIL import Image

    output = BytesIO()
    Image.frombytes("RGB", (width, height), rgb_bytes).save(output, format="PNG")
    return f"sha256:{hashlib.sha256(output.getvalue()).hexdigest()}"


def _accepted_frames(
    frame_set: Mapping[str, object],
    masks: object,
) -> list[tuple[dict[str, object], object]]:
    import numpy as np

    mask_tensor = np.asarray(masks, dtype=bool)
    width, height = (int(value) for value in frame_set["resolution"])
    if mask_tensor.ndim != 3 or mask_tensor.shape[1:] != (height, width):
        raise ValueError("the Stable Mask tensor does not match the Frame Set")
    result: list[tuple[dict[str, object], object]] = []
    for frame in frame_set["views"]:
        if frame["status"] != "accepted":
            continue
        mask_index = int(frame["stableMaskIndex"])
        mask_area = (
            int(mask_tensor[mask_index].sum())
            if 0 <= mask_index < len(mask_tensor)
            else -1
        )
        if (
            not 0 <= mask_index < len(mask_tensor)
            or mask_area != int(frame["stableMaskAreaPixels"])
        ):
            raise ValueError("the sealed View and Stable Mask identity disagree")
        # A zero-area observation is unobserved, not negative Evidence.
        if mask_area == 0:
            continue
        result.append((deepcopy(dict(frame)), mask_tensor[mask_index]))
    if not result:
        raise ValueError("the sealed scene has no accepted Stable Masks")
    return result


def _current_input(
    *,
    scene_digest: str,
    view_id: str,
    camera_digest: str,
    rgb_digest: str,
    stable_mask_digest: str,
    evidence_policy_digest: str,
    stable_ids: list[int],
    evidence_working_set: Mapping[str, object],
) -> dict[str, object]:
    dependency = {
        "splatId": "controlled-overlap",
        "renderStateToken": scene_digest,
        "geometryToken": scene_digest,
        "gaussianIdentityToken": scene_digest,
        "worldTransformToken": "identity-transform/v1",
    }
    request_binding = {
        "targetContextId": "v2ax-controlled-overlap",
        "contextRevision": 1,
        "dependencyToken": dependency,
    }
    render_working_set_payload = {
        "targetSplatId": "controlled-overlap",
        "dependencyToken": dependency,
        "cameraBindingDigest": camera_digest,
        "stableGaussianIds": stable_ids,
        "completeness": "complete",
    }
    render_working_set = {
        **render_working_set_payload,
        "renderWorkingSetToken": canonical_json_digest(render_working_set_payload),
    }
    return {
        "requestBinding": request_binding,
        "targetSplatId": "controlled-overlap",
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": "included",
            "cameraBindingDigest": camera_digest,
            "rgbDigest": rgb_digest,
            "stableMaskDigest": stable_mask_digest,
        },
        "evidencePolicyDigest": evidence_policy_digest,
        "renderWorkingSet": render_working_set,
        "evidenceWorkingSet": evidence_working_set,
        "rasterImplementationId": DIRECT_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "production-direct",
        "evidenceBackendId": DIRECT_EVIDENCE_BACKEND_ID,
        "runtimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    }


def _candidate_replay(aggregation: Mapping[str, object]) -> dict[str, object]:
    return {
        "selectedStableGaussianIds": list(aggregation["selectedStableGaussianIds"]),
        "rejectedStableGaussianIds": list(aggregation["rejectedStableGaussianIds"]),
        "uncertainStableGaussianIds": list(aggregation["uncertainStableGaussianIds"]),
        "candidateInputStableGaussianIds": list(
            aggregation["candidateInputStableGaussianIds"]
        ),
        "replayDigest": aggregation["resultDigest"],
    }


def _render_baseline_view(
    *,
    backend: LockedGsplatBackend,
    snapshot: Mapping[str, object],
    stable_ids: list[int],
    evidence_working_set: Mapping[str, object],
    camera: Mapping[str, object],
    view_id: str,
    mask_artifact: Mapping[str, object],
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, object]:
    """Measure one production single-N View with depth moments disabled."""

    import torch

    width = int(mask_artifact["width"])
    height = int(mask_artifact["height"])
    evidence_policy = default_reference_evidence_policy()
    pixel_weights = typed_pixel_evidence_weights(
        dict(mask_artifact), evidence_policy, torch
    )
    sorted_ids = sorted(stable_ids)
    direct = None
    direct_times: list[float] = []
    starts: list[int] = []
    peaks: list[int] = []
    ends: list[int] = []
    for run_index in range(warmup_runs + measured_runs):
        # Each repetition starts from the declared retained inputs, not the
        # previous repetition's output tensors.
        direct = None
        torch.cuda.synchronize()
        start_allocated = int(torch.cuda.memory_allocated())
        started = time.perf_counter()
        direct = backend.rasterize_direct_evidence_typed(
            snapshot=snapshot,
            camera=camera,
            width=width,
            height=height,
            render_stable_ids=stable_ids,
            evidence_stable_ids=sorted_ids,
            target_stable_ids=sorted_ids,
            pixel_weights=pixel_weights,
            depth_moments_enabled=False,
        )
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000.0
        if direct.depth_moments is not None:
            raise ValueError("the production baseline unexpectedly wrote depth moments")
        if run_index >= warmup_runs:
            direct_times.append(elapsed)
            starts.append(start_allocated)
            peaks.append(int(direct.telemetry.peak_vram_bytes))
            ends.append(int(torch.cuda.memory_allocated()))
    assert direct is not None

    camera_digest = canonical_json_digest(camera)
    current_input = _current_input(
        scene_digest=str(snapshot["sceneVersion"]),
        view_id=view_id,
        camera_digest=camera_digest,
        rgb_digest=_png_digest(direct.service_rgb_bytes, width, height),
        stable_mask_digest=str(mask_artifact["digest"]),
        evidence_policy_digest=str(evidence_policy["evidencePolicyDigest"]),
        stable_ids=sorted_ids,
        evidence_working_set=evidence_working_set,
    )
    admitted = admit_gaussian_evidence(current_input)
    if admitted.get("status") != "admitted":
        raise RuntimeError(f"the production baseline identity was rejected: {admitted}")
    masses = {
        "positiveMass": direct.positive_mass.detach().cpu().tolist(),
        "negativeMass": direct.negative_mass.detach().cpu().tolist(),
        "visibleMass": direct.visible_mass.detach().cpu().tolist(),
        "boundaryMass": direct.boundary_mass.detach().cpu().tolist(),
    }
    baseline_artifact = create_gaussian_evidence_artifact(
        admitted["admission"], masses
    )
    projected_depth_rows = ProjectedDepthRowsRecord(
        rows=direct.projected_depth_rows,
        stable_ids_by_projected_row=stable_ids,
    )
    return {
        "camera": deepcopy(camera),
        "cameraDigest": camera_digest,
        "maskArtifact": deepcopy(mask_artifact),
        "pixelWeights": pixel_weights,
        "currentInput": current_input,
        "admission": admitted["admission"],
        "baselineArtifact": baseline_artifact,
        "baselineMassTensors": {
            "positiveMass": direct.positive_mass.detach().cpu().clone(),
            "negativeMass": direct.negative_mass.detach().cpu().clone(),
            "visibleMass": direct.visible_mass.detach().cpu().clone(),
            "boundaryMass": direct.boundary_mass.detach().cpu().clone(),
        },
        "baselineStableGaussianIds": direct.stable_gaussian_ids,
        "baselineBoundaryContactStableGaussianIds": (
            direct.boundary_contact_stable_gaussian_ids
        ),
        "directServiceRgbDigest": direct.service_rgb_digest,
        "directServiceRgbBytes": direct.service_rgb_bytes,
        "projectedDepthRows": projected_depth_rows,
        "latencyMilliseconds": statistics.median(direct_times),
        "startVramBytes": max(starts),
        "peakVramBytes": max(peaks),
        "endVramBytes": max(ends),
    }


def _acquire_cwed_for_view(
    *,
    backend: LockedGsplatBackend,
    snapshot: Mapping[str, object],
    stable_ids: list[int],
    baseline: Mapping[str, object],
    depth_capability: DepthMomentInternalCapability,
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, object]:
    """Acquire CWED from a second exact Direct call and prove baseline parity."""

    import torch

    mask_artifact = baseline["maskArtifact"]
    width = int(mask_artifact["width"])
    height = int(mask_artifact["height"])
    sorted_ids = sorted(stable_ids)
    direct = None
    readout = None
    projected_depth_rows = None
    times: list[float] = []
    starts: list[int] = []
    peaks: list[int] = []
    ends: list[int] = []
    for run_index in range(warmup_runs + measured_runs):
        direct = None
        readout = None
        projected_depth_rows = None
        direct_channels = None
        torch.cuda.synchronize()
        start_allocated = int(torch.cuda.memory_allocated())
        started = time.perf_counter()
        direct = backend.rasterize_direct_evidence_typed(
            snapshot=snapshot,
            camera=baseline["camera"],
            width=width,
            height=height,
            render_stable_ids=stable_ids,
            evidence_stable_ids=sorted_ids,
            target_stable_ids=sorted_ids,
            pixel_weights=baseline["pixelWeights"],
            depth_moments_enabled=True,
        )
        if direct.depth_moments is None:
            raise ValueError("the shared CWED stage did not return depth moments")
        projected_depth_rows = ProjectedDepthRowsRecord(
            rows=direct.projected_depth_rows,
            stable_ids_by_projected_row=stable_ids,
        )
        if not depth_capability.supports_execution(
            width=width,
            height=height,
            render_gaussian_count=direct.telemetry.projected_gaussian_count,
            evidence_gaussian_count=len(sorted_ids),
            intersection_count=direct.telemetry.intersection_count,
        ):
            raise ValueError("the CWED operation exceeds its qualified envelope")
        identity = create_depth_moment_readout_identity(
            baseline["admission"],
            render_stable_ids_by_projected_row=stable_ids,
            capability=depth_capability,
            width=width,
            height=height,
        )
        readout = DepthMomentReadoutRecord(
            identity=identity,
            raw_depth_moments=direct.depth_moments,
            policy=depth_capability.policy,
            telemetry=DepthMomentTelemetry(
                depth_moment_buffer_bytes=direct.telemetry.depth_moment_buffer_bytes,
                peak_vram_bytes=direct.telemetry.peak_vram_bytes,
                projected_gaussian_count=direct.telemetry.projected_gaussian_count,
                evidence_gaussian_count=len(sorted_ids),
                intersection_count=direct.telemetry.intersection_count,
            ),
        )
        direct_channels = {
            "positiveMass": direct.positive_mass,
            "negativeMass": direct.negative_mass,
            "visibleMass": direct.visible_mass,
            "boundaryMass": direct.boundary_mass,
        }
        mismatches: list[str] = []
        if direct.service_rgb_digest != baseline["directServiceRgbDigest"]:
            mismatches.append("serviceRgbDigest")
        if direct.service_rgb_bytes != baseline["directServiceRgbBytes"]:
            mismatches.append("serviceRgbBytes")
        if direct.stable_gaussian_ids != baseline["baselineStableGaussianIds"]:
            mismatches.append("stableGaussianIds")
        if (
            direct.boundary_contact_stable_gaussian_ids
            != baseline["baselineBoundaryContactStableGaussianIds"]
        ):
            mismatches.append("boundaryContactStableGaussianIds")
        mismatches.extend(
            name
            for name, tensor in direct_channels.items()
            if not torch.allclose(
                tensor.detach().cpu(),
                baseline["baselineMassTensors"][name],
                rtol=_PRODUCTION_MASS_RTOL,
                atol=_PRODUCTION_MASS_ATOL,
            )
        )
        if not exact_projected_depth_rows_equal(
            projected_depth_rows, baseline["projectedDepthRows"]
        ):
            mismatches.append("exactProjectedDepthRowsOrRowMapping")
        if mismatches:
            raise ValueError(
                "the CWED acquisition does not share the sealed production input, "
                "exact projected depths, or mass-equivalent output: "
                f"{', '.join(mismatches)}"
            )
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000.0
        if run_index >= warmup_runs:
            times.append(elapsed)
            starts.append(start_allocated)
            peaks.append(int(torch.cuda.max_memory_allocated()))
            ends.append(int(torch.cuda.memory_allocated()))
    assert direct is not None and readout is not None and projected_depth_rows is not None
    return {
        "direct": direct,
        "depthReadout": readout,
        "projectedDepthRows": projected_depth_rows,
        "baselineArtifactDigest": baseline["baselineArtifact"]["artifactDigest"],
        "latencyMilliseconds": statistics.median(times),
        "startVramBytes": max(starts),
        "peakVramBytes": max(peaks),
        "endVramBytes": max(ends),
    }


def _build_sidecar_for_view(
    *,
    backend: LockedGsplatBackend,
    snapshot: Mapping[str, object],
    stable_ids: list[int],
    baseline: Mapping[str, object],
    cwed: Mapping[str, object],
    relation_config: Mapping[str, object],
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, object]:
    """Measure the reference Contributor/classification stage against exact depths."""

    import torch

    mask_artifact = baseline["maskArtifact"]
    width = int(mask_artifact["width"])
    height = int(mask_artifact["height"])
    sorted_ids = sorted(stable_ids)
    sidecar = None
    times: list[float] = []
    starts: list[int] = []
    peaks: list[int] = []
    ends: list[int] = []
    contributor_ids_elements = 0
    contributor_weights_elements = 0
    baseline_negative_mass = baseline["baselineMassTensors"]["negativeMass"].to(
        cwed["direct"].negative_mass.device
    )
    for run_index in range(warmup_runs + measured_runs):
        reference = None
        reference_depth_rows = None
        sidecar = None
        torch.cuda.synchronize()
        start_allocated = int(torch.cuda.memory_allocated())
        started = time.perf_counter()
        reference = backend.rasterize_reference_evidence_typed(
            snapshot=snapshot,
            camera=baseline["camera"],
            width=width,
            height=height,
            stable_ids=stable_ids,
        )
        reference_depth_rows = ProjectedDepthRowsRecord(
            rows=reference.projected_depth_rows,
            stable_ids_by_projected_row=stable_ids,
        )
        if (
            reference.service_rgb_digest != baseline["directServiceRgbDigest"]
            or tuple(reference.stable_ids.detach().cpu().tolist()) != tuple(stable_ids)
            or not exact_projected_depth_rows_equal(
                reference_depth_rows, cwed["projectedDepthRows"]
            )
        ):
            raise ValueError(
                "the reference Contributor stage does not share the baseline/CWED projected rows"
            )
        accepted_sequence_digest = _tensor_digest(
            "accepted-contribution-sequence/v1",
            reference.stable_ids,
            reference.contributor_ids,
            reference.contributor_weights,
            reference_depth_rows.rows,
        )
        sidecar = build_depth_classified_negative_evidence_sidecar(
            relation_config=relation_config,
            depth_readout=cwed["depthReadout"],
            projected_depth_rows=reference_depth_rows,
            evidence_stable_ids=sorted_ids,
            contributor_row_ids=reference.contributor_ids.contiguous(),
            contributor_weights=reference.contributor_weights.contiguous(),
            negative_pixel_weights=baseline["pixelWeights"][2][1],
            baseline_negative_mass=baseline_negative_mass,
            baseline_artifact_digest=str(cwed["baselineArtifactDigest"]),
            accepted_contribution_sequence_digest=accepted_sequence_digest,
        )
        torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000.0
        if run_index >= warmup_runs:
            times.append(elapsed)
            starts.append(start_allocated)
            peaks.append(int(torch.cuda.max_memory_allocated()))
            ends.append(int(torch.cuda.memory_allocated()))
        contributor_ids_elements = int(reference.contributor_ids.numel())
        contributor_weights_elements = int(reference.contributor_weights.numel())
    assert sidecar is not None
    return {
        "sidecar": sidecar,
        "latencyMilliseconds": statistics.median(times),
        "startVramBytes": max(starts),
        "peakVramBytes": max(peaks),
        "endVramBytes": max(ends),
        "referenceContributorIdElements": contributor_ids_elements,
        "referenceContributorWeightElements": contributor_weights_elements,
    }


def predict(arguments: argparse.Namespace) -> dict[str, object]:
    import torch

    prediction_input = load_depth_classified_negative_evidence_prediction_input(
        arguments.configuration,
        scene_id=arguments.scene_id,
    )
    configuration = prediction_input["configuration"]
    scene = prediction_input["scene"]
    if arguments.seed not in scene["seeds"]:
        raise ValueError("the requested seed is not in the sealed scene configuration")
    if arguments.output.exists():
        raise ValueError(f"refusing to overwrite prediction output: {arguments.output}")
    runtime_status = current_renderer_runtime().status()
    if runtime_status.status != "ready":
        raise RuntimeError(
            f"the locked renderer runtime is unavailable: {runtime_status.message}"
        )

    snapshot_path = prediction_input["sceneSnapshotPath"]
    masks_path = prediction_input["stableMasksPath"]
    input_manifest = prediction_input["manifest"]
    snapshot = build_depth_classified_negative_evidence_prediction_snapshot(
        snapshot_path
    )
    stable_ids = [int(value) for value in validate_supported_snapshot(snapshot)]
    working_set_policy = prediction_input["evidenceWorkingSet"]
    if working_set_policy["coreStableGaussianIdsSource"] != (
        "validated-scene-snapshot-order"
    ):
        raise ValueError("the prediction Working Set source is unsupported")
    evidence_working_set = create_evidence_working_set(
        {
            "targetSplatId": str(snapshot["sceneId"]),
            "coreTargetStableIds": stable_ids,
            "contextStableGaussianIds": list(
                working_set_policy["contextStableGaussianIds"]
            ),
        }
    )
    frame_set = prediction_input["frameSet"]
    frames = _accepted_frames(frame_set, prediction_input["stableMasks"])

    relation_config = configuration["relationConfigs"][0]
    depth_policy_config = configuration["depthMomentValidityPolicy"]
    depth_policy = DepthMomentValidityPolicy(
        policy_id=str(depth_policy_config["policyId"]),
        minimum_m0=float(depth_policy_config["minimumM0"]),
    )
    depth_capability = load_internal_depth_moment_capability()
    if depth_capability.status != "ready" or depth_capability.policy != depth_policy:
        raise RuntimeError(
            "the benchmark requires the exact checked CWED qualification capability"
        )
    measurement = configuration["measurementPolicy"]
    warmup_runs = int(measurement["warmupRuns"])
    measured_runs = int(measurement["measuredRuns"])
    backend = LockedGsplatBackend()
    per_view: dict[str, dict[str, object]] = {}
    for frame, mask in frames:
        view_id = str(frame["viewId"])
        per_view[view_id] = _render_baseline_view(
            backend=backend,
            snapshot=snapshot,
            stable_ids=stable_ids,
            evidence_working_set=evidence_working_set,
            camera=_camera(frame, frame_set),
            view_id=view_id,
            mask_artifact=_mask_artifact(mask),
            warmup_runs=warmup_runs,
            measured_runs=measured_runs,
        )

    view_ids = sorted(per_view)
    baseline_views = [
        {
            "currentInput": per_view[view_id]["currentInput"],
            "artifact": per_view[view_id]["baselineArtifact"],
        }
        for view_id in view_ids
    ]
    first_input = baseline_views[0]["currentInput"]
    aggregation_input = {
        "requestBinding": first_input["requestBinding"],
        "targetSplatId": first_input["targetSplatId"],
        "classificationUniverseStableGaussianIds": sorted(stable_ids),
        "classificationScopeStableGaussianIds": sorted(stable_ids),
        "evidenceWorkingSet": first_input["evidenceWorkingSet"],
        "views": baseline_views,
    }
    aggregation_policy = default_reference_aggregation_policy()
    baseline_aggregation = None
    baseline_replay_times: list[float] = []
    for run_index in range(warmup_runs + measured_runs):
        started = time.perf_counter()
        baseline_aggregation = aggregate_reference_gaussian_evidence(
            aggregation_input, aggregation_policy
        )
        if run_index >= warmup_runs:
            baseline_replay_times.append((time.perf_counter() - started) * 1000.0)
    assert baseline_aggregation is not None
    baseline_candidate = _candidate_replay(baseline_aggregation)

    camera_digests = {
        view_id: per_view[view_id]["cameraDigest"] for view_id in view_ids
    }
    input_identity = create_experiment_input_identity(
        scene_snapshot_digest=_sha256(snapshot_path),
        camera_bindings_digest=canonical_json_digest(camera_digests),
        stable_masks_digest=_sha256(masks_path),
        working_sets_digest=canonical_json_digest(
            {
                "policyId": working_set_policy["policyId"],
                "policyDigest": working_set_policy["policyDigest"],
                "evidenceWorkingSet": first_input["evidenceWorkingSet"],
                "renderWorkingSets": [
                    per_view[view_id]["currentInput"]["renderWorkingSet"]
                    for view_id in view_ids
                ],
            }
        ),
        renderer_runtime_digest=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        prediction_input_manifest_sha256=_sha256(
            prediction_input["manifestPath"]
        ),
        prediction_input_manifest_digest=str(input_manifest["manifestDigest"]),
        deterministic_seed=arguments.seed,
    )
    runtime_source = {
        "directEvidenceAbiVersion": DIRECT_EVIDENCE_ABI_VERSION,
        "directEvidenceSourceRevision": DIRECT_EVIDENCE_SOURCE_REVISION,
        "directEvidenceRuntimeBuildId": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        "rendererRuntimeDigest": DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
        "gpuName": torch.cuda.get_device_name(),
        "computeCapability": ".".join(
            str(value) for value in torch.cuda.get_device_capability()
        ),
        "benchmarkImplementationDigest": _benchmark_implementation_digest(),
    }
    width, height = (int(value) for value in frame_set["resolution"])
    pixel_count = len(view_ids) * width * height
    gaussian_count = len(view_ids) * len(stable_ids)
    production_stage = _cost_stage(
        stage_id="productionBaseline",
        latency_ms=sum(
            float(per_view[view_id]["latencyMilliseconds"]) for view_id in view_ids
        ),
        start_vram_bytes=max(
            int(per_view[view_id]["startVramBytes"]) for view_id in view_ids
        ),
        peak_vram_bytes=max(
            int(per_view[view_id]["peakVramBytes"]) for view_id in view_ids
        ),
        end_vram_bytes=max(
            int(per_view[view_id]["endVramBytes"]) for view_id in view_ids
        ),
        retained_inputs=[
            "labelFreeSceneSnapshot",
            "cameraBindings",
            "stableMasks",
            "wholeTargetSplatEvidenceWorkingSet",
        ],
        retained_outputs=[
            "productionGaussianEvidenceArtifacts",
            "exactProjectedDepthRowsRecords",
        ],
        measurement_composition="sum-of-per-view-medians/max-of-per-view-allocations",
        buffer_writes=_buffer_writes(
            authoritativeRgb=pixel_count * 3,
            rasterAlpha=pixel_count,
            positiveMass=gaussian_count,
            negativeMass=gaussian_count,
            visibleMass=gaussian_count,
            boundaryMass=gaussian_count,
            exactProjectedDepthRows=gaussian_count,
        ),
    )
    baseline_replay_stage = _cost_stage(
        stage_id="baselineCandidateReplay",
        latency_ms=statistics.median(baseline_replay_times),
        start_vram_bytes=None,
        peak_vram_bytes=None,
        end_vram_bytes=None,
        retained_inputs=["productionGaussianEvidenceArtifacts"],
        retained_outputs=["baselineCandidateReplay"],
        buffer_writes=_buffer_writes(candidateClassifications=len(stable_ids)),
    )
    baseline_cost = _cost_measurement(
        measurement,
        components=[production_stage, baseline_replay_stage],
        total_stage_id="productionBaselineTotal",
    )
    baseline_record = create_baseline_run_record(
        input_identity=input_identity,
        baseline_artifact_digests=[
            str(per_view[view_id]["baselineArtifact"]["artifactDigest"])
            for view_id in view_ids
        ],
        candidate_replay=baseline_candidate,
        runtime_source=runtime_source,
        cost_measurement=baseline_cost,
    )

    arguments.output.mkdir(parents=True)
    _write_json(arguments.output / "configuration.json", configuration)
    _write_text(
        arguments.output / "prediction-input-manifest.json",
        prediction_input["manifestPath"].read_text(encoding="utf-8"),
    )
    _write_json(
        arguments.output / "baseline-artifacts.json",
        {
            "schemaVersion": 1,
            "methodId": BASELINE_METHOD_ID,
            "views": baseline_views,
            "candidateReplay": baseline_candidate,
        },
    )
    persist_baseline_run_record(arguments.output, baseline_record)

    cwed_results: dict[str, dict[str, object]] = {}
    sidecar_results: dict[str, dict[str, object]] = {}
    try:
        for view_id in view_ids:
            cwed_results[view_id] = _acquire_cwed_for_view(
                backend=backend,
                snapshot=snapshot,
                stable_ids=stable_ids,
                baseline=per_view[view_id],
                depth_capability=depth_capability,
                warmup_runs=warmup_runs,
                measured_runs=measured_runs,
            )
        for view_id in view_ids:
            sidecar_results[view_id] = _build_sidecar_for_view(
                backend=backend,
                snapshot=snapshot,
                stable_ids=stable_ids,
                baseline=per_view[view_id],
                cwed=cwed_results[view_id],
                relation_config=relation_config,
                warmup_runs=warmup_runs,
                measured_runs=measured_runs,
            )
    except Exception as error:
        failure_path = persist_sidecar_failure(
            arguments.output,
            error=error,
            baseline_record_digest=str(baseline_record["recordDigest"]),
        )
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        return {
            "status": failure["status"],
            "prediction": str(arguments.output),
            "sceneId": arguments.scene_id,
            "seed": arguments.seed,
            "baselineMethodId": BASELINE_METHOD_ID,
            "errorType": failure["errorType"],
        }

    sidecars_by_view_id = {
        view_id: sidecar_results[view_id]["sidecar"] for view_id in view_ids
    }
    for view_id, sidecar in sidecars_by_view_id.items():
        _write_json(arguments.output / "sidecars" / f"{view_id}.json", sidecar)
    cwed_stage = _cost_stage(
        stage_id="sharedCwedReadoutAcquisition",
        latency_ms=sum(
            float(cwed_results[view_id]["latencyMilliseconds"])
            for view_id in view_ids
        ),
        start_vram_bytes=max(
            int(cwed_results[view_id]["startVramBytes"]) for view_id in view_ids
        ),
        peak_vram_bytes=max(
            int(cwed_results[view_id]["peakVramBytes"]) for view_id in view_ids
        ),
        end_vram_bytes=max(
            int(cwed_results[view_id]["endVramBytes"]) for view_id in view_ids
        ),
        retained_inputs=[
            "sealedProductionBaselineIdentity",
            "exactProjectedDepthRowsRecords",
        ],
        retained_outputs=["depthMomentReadouts", "cwedMassEquivalentDirectResults"],
        measurement_composition="sum-of-per-view-medians/max-of-per-view-allocations",
        buffer_writes=_buffer_writes(
            authoritativeRgb=pixel_count * 3,
            rasterAlpha=pixel_count,
            positiveMass=gaussian_count,
            negativeMass=gaussian_count,
            visibleMass=gaussian_count,
            boundaryMass=gaussian_count,
            exactProjectedDepthRows=gaussian_count,
            depthMomentM0=pixel_count,
            depthMomentM1=pixel_count,
            depthMomentM2=pixel_count,
            ownedRawDepthMoments=pixel_count * 3,
            readoutValid=pixel_count,
            readoutCwed=pixel_count,
            readoutVariance=pixel_count,
        ),
    )
    reference_stage = _cost_stage(
        stage_id="referenceContributorAndClassificationSidecar",
        latency_ms=sum(
            float(sidecar_results[view_id]["latencyMilliseconds"])
            for view_id in view_ids
        ),
        start_vram_bytes=max(
            int(sidecar_results[view_id]["startVramBytes"])
            for view_id in view_ids
        ),
        peak_vram_bytes=max(
            int(sidecar_results[view_id]["peakVramBytes"])
            for view_id in view_ids
        ),
        end_vram_bytes=max(
            int(sidecar_results[view_id]["endVramBytes"]) for view_id in view_ids
        ),
        retained_inputs=[
            "sealedProductionBaselineIdentity",
            "depthMomentReadouts",
            "exactProjectedDepthRowsRecords",
        ],
        retained_outputs=["classifiedDiagnosticSidecars"],
        measurement_composition="sum-of-per-view-medians/max-of-per-view-allocations",
        buffer_writes=_buffer_writes(
            authoritativeRgb=pixel_count * 3,
            rasterAlpha=pixel_count,
            referenceContributorIds=sum(
                int(sidecar_results[view_id]["referenceContributorIdElements"])
                for view_id in view_ids
            ),
            referenceContributorWeights=sum(
                int(sidecar_results[view_id]["referenceContributorWeightElements"])
                for view_id in view_ids
            ),
            exactProjectedDepthRows=gaussian_count,
            frontNegativeMass=gaussian_count,
            nearNegativeMass=gaussian_count,
            behindNegativeMass=gaussian_count,
            invalidDepthNegativeMass=gaussian_count,
        ),
    )
    for ordinal, method in enumerate(configuration["variantMethods"]):
        replay = None
        replay_times: list[float] = []
        for run_index in range(warmup_runs + measured_runs):
            replay_started = time.perf_counter()
            replay = replay_depth_classified_negative_evidence(
                aggregation_input=aggregation_input,
                sidecars_by_view_id=sidecars_by_view_id,
                replay_config=method,
                aggregation_policy=aggregation_policy,
            )
            if run_index >= warmup_runs:
                replay_times.append((time.perf_counter() - replay_started) * 1000.0)
        assert replay is not None
        _write_json(
            arguments.output / "candidate-replays" / f"variant-{ordinal:03d}.json",
            replay,
        )
        variant_replay_stage = _cost_stage(
            stage_id="variantCandidateReplay",
            latency_ms=statistics.median(replay_times),
            start_vram_bytes=None,
            peak_vram_bytes=None,
            end_vram_bytes=None,
            retained_inputs=[
                "productionGaussianEvidenceArtifacts",
                "classifiedDiagnosticSidecars",
            ],
            retained_outputs=["variantCandidateReplay"],
            buffer_writes=_buffer_writes(
                reweightedNegativeMass=gaussian_count,
                candidateClassifications=len(stable_ids),
            ),
        )
        variant_cost = _cost_measurement(
            measurement,
            components=[
                production_stage,
                baseline_replay_stage,
                cwed_stage,
                reference_stage,
                variant_replay_stage,
            ],
            total_stage_id="shadowExperimentTotal",
        )
        record = create_variant_run_record(
            input_identity=input_identity,
            replay_config=method,
            sidecar_digests=[
                str(sidecars_by_view_id[view_id]["artifactDigest"])
                for view_id in view_ids
            ],
            candidate_replay=replay,
            runtime_source=runtime_source,
            cost_measurement=variant_cost,
        )
        persist_variant_run_record(arguments.output, record, ordinal=ordinal)
    seal = seal_depth_classified_negative_evidence_prediction(
        arguments.output,
        expected_variant_method_ids=[
            str(method["methodId"]) for method in configuration["variantMethods"]
        ],
    )
    return {
        "status": "prediction-complete",
        "prediction": str(arguments.output),
        "sceneId": arguments.scene_id,
        "seed": arguments.seed,
        "manifestSha256": seal["manifestSha256"],
        "baselineMethodId": BASELINE_METHOD_ID,
        "variantMethodIds": [
            method["methodId"] for method in configuration["variantMethods"]
        ],
    }


def report(arguments: argparse.Namespace) -> str:
    configuration = load_depth_classified_negative_evidence_configuration(
        arguments.configuration
    )
    scores = [json.loads(path.read_text(encoding="utf-8")) for path in arguments.scores]
    expected_trials = {
        (
            load_depth_classified_negative_evidence_prediction_input(
                arguments.configuration,
                scene_id=str(scene["sceneId"]),
            )["manifest"]["sceneSnapshot"]["sha256"],
            seed,
        )
        for scene in configuration["scenes"]
        for seed in scene["seeds"]
    }
    actual_trials = {
        (
            score["inputIdentity"]["sceneSnapshotDigest"],
            score["inputIdentity"]["deterministicSeed"],
        )
        for score in scores
    }
    thin_edge_complete = all(
        all(
            method["metrics"]["thinOrEdgeRetentionAvailable"]
            for method in score["methods"]
        )
        for score in scores
    )
    recommendation = "retain-experimental"
    reasons = []
    if actual_trials != expected_trials:
        reasons.append("the sealed scene/seed matrix is incomplete")
    if not thin_edge_complete:
        reasons.append(
            "the available immutable fixture has no thin/edge Ground Truth class"
        )
    if len(configuration["scenes"]) < 2:
        reasons.append("no immutable real-scene trial is present in this repository")
    trial_validity = (
        "invalid-incomplete-for-promotion"
        if reasons
        else "complete-experimental-record"
    )
    if not reasons:
        reasons.append(
            "promotion still requires a separately reviewed schema and identity migration Issue"
        )

    lines = [
        "# V2AX depth-classified Negative Evidence report",
        "",
        f"**Recommendation: `{recommendation}`.**",
        f"**Trial validity: `{trial_validity}`.**",
        "",
        "This report does not promote a classified channel. The production baseline result remains independent of every variant.",
        "",
        "## Trial seals and runtime",
        "",
        *[
            f"- `{score['inputIdentity']['deterministicSeed']}`: prediction manifest `{score['predictionManifestSha256']}`, Ground Truth `{score['groundTruthSha256']}`, input identity `{score['inputIdentityDigest']}`."
            for score in scores
        ],
        f"- GPU: `{scores[0]['methods'][0]['runtimeSource']['gpuName']}` (compute capability `{scores[0]['methods'][0]['runtimeSource']['computeCapability']}`).",
        "",
        "## Trial results",
        "",
        "| Scene digest | Seed | Method | Precision | Recall | Distractor leaks | Thin/edge retention | Derived total latency ms | Max component peak VRAM bytes | Logical output elements | Gate |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for score in scores:
        identity = score["inputIdentity"]
        for method in score["methods"]:
            metrics = method["metrics"]
            thin = metrics["thinOrEdgeRetention"]
            total_cost = method["costMeasurement"]["stages"][-1]
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(identity["sceneSnapshotDigest"]),
                        str(identity["deterministicSeed"]),
                        str(method["method"]["methodId"]),
                        f"{float(metrics['targetPrecision']):.6f}",
                        f"{float(metrics['targetRecall']):.6f}",
                        str(metrics["distractorLeakageCount"]),
                        "unavailable" if thin is None else f"{float(thin):.6f}",
                        f"{float(total_cost['latencyMilliseconds']):.3f}",
                        str(total_cost["peakVramBytes"]),
                        str(total_cost["bufferWrites"]["total"]),
                        "pass" if method["qualityGatePassed"] else "fail",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Audited cost components",
            "",
            "GPU-stage latencies are sums of per-View medians and GPU allocations are maxima across the identically reset per-View calls; Candidate replay latencies are whole-stage medians. Method totals are derived sums of component values and maximum component peaks, not paired end-to-end samples. The production total is moments-off Direct Evidence plus baseline Candidate aggregation; each shadow total adds CWED/readout acquisition, reference Contributor/classification, and its own replay.",
            "",
            "| Seed | Method | Stage | Kind | Composition | Latency ms | Start / peak / end VRAM bytes | Logical output elements | Retained outputs |",
            "|---|---|---|---|---|---:|---|---:|---|",
        ]
    )
    for score in scores:
        seed = score["inputIdentity"]["deterministicSeed"]
        for method in score["methods"]:
            method_id = method["method"]["methodId"]
            for stage in method["costMeasurement"]["stages"]:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(seed),
                            str(method_id),
                            str(stage["stageId"]),
                            str(stage["costKind"]),
                            str(stage["measurementComposition"]),
                            f"{float(stage['latencyMilliseconds']):.3f}",
                            f"{stage['startVramBytes']} / {stage['peakVramBytes']} / {stage['endVramBytes']}",
                            str(stage["bufferWrites"]["total"]),
                            ", ".join(stage["retainedOutputsThroughReturn"]) or "none",
                        ]
                    )
                    + " |"
                )
    lines.extend(
        [
            "",
            "## Isolation verdict",
            "",
            "- The unchanged single-`negativeMass` baseline was persisted and sealed first.",
            "- Prediction opened one allowlisted input manifest, a label-free Scene Snapshot, and a masks-only NPZ; no Ground Truth-bearing fixture manifest was reachable.",
            "- Every classified sidecar and Candidate replay used the same input identity digest as the baseline.",
            "- Baseline Direct Evidence ran with moments off; the CWED call proved exact RGB, Stable-ID row, and projected-depth parity plus production-tolerance P/N/V/boundary parity before sidecar use.",
            "- Ground Truth was opened only by the independent scorer after prediction input/output graph hash and canonical-digest verification.",
            "- Variant quality cannot rescue or alter baseline pass/fail.",
            "- Production Evidence, readiness, Runtime Profile, Candidate binding, and orchestration remain unchanged.",
            "",
            "## Recommendation rationale",
            "",
            *[f"- {reason}." for reason in reasons],
            "",
            "A later promotion requires a new reviewed Issue. Until then, keep this experiment sealed and nonblocking.",
            "",
        ]
    )
    _write_text(arguments.output, "\n".join(lines))
    return recommendation


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "predict":
        summary = predict(arguments)
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["status"] == "prediction-complete" else 2
    if arguments.command == "score":
        result = score_depth_classified_negative_evidence_prediction(
            arguments.prediction,
            ground_truth_path=arguments.ground_truth,
            output_path=arguments.output,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    recommendation = report(arguments)
    print(
        json.dumps({"report": str(arguments.output), "recommendation": recommendation})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
