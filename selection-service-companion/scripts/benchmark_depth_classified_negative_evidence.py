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

from selection_service_companion.controlled_overlap_benchmark import (
    build_controlled_overlap_snapshot,
)
from selection_service_companion.depth_classified_negative_evidence_benchmark import (
    BASELINE_METHOD_ID,
    create_baseline_run_record,
    create_experiment_input_identity,
    create_variant_run_record,
    load_depth_classified_negative_evidence_configuration,
    persist_baseline_run_record,
    persist_sidecar_failure,
    persist_variant_run_record,
    score_depth_classified_negative_evidence_prediction,
    seal_depth_classified_negative_evidence_prediction,
)
from selection_service_companion.depth_classified_negative_evidence_experiment import (
    build_depth_classified_negative_evidence_sidecar,
    replay_depth_classified_negative_evidence,
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
    EXPECTED_GSPLAT_SOURCE_COMMIT,
    current_renderer_runtime,
)


SCRIPT_ROOT = Path(__file__).resolve().parent
COMPANION_ROOT = SCRIPT_ROOT.parent
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


def _camera(
    frame: Mapping[str, object], frame_set: Mapping[str, object]
) -> dict[str, object]:
    import numpy as np

    width, height = (int(value) for value in frame_set["resolution"])
    if width <= 0 or height <= 0:
        raise ValueError("the configured Frame Set resolution is invalid")
    c2w = np.asarray(frame["camera_to_world"], dtype=np.float32)
    if c2w.shape != (4, 4) or not np.isfinite(c2w).all():
        raise ValueError("the configured CameraBinding is invalid")
    w2c = np.linalg.inv(c2w).astype(np.float32)
    focal = width / (
        2.0 * math.tan(math.radians(float(frame_set["horizontal_fov_degrees"])) / 2.0)
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


def _scene(configuration: Mapping[str, object], scene_id: str) -> dict[str, object]:
    matches = [
        scene for scene in configuration["scenes"] if scene["sceneId"] == scene_id
    ]
    if len(matches) != 1:
        raise ValueError(f"the sealed configuration has no unique scene {scene_id!r}")
    return deepcopy(matches[0])


def _accepted_frames(
    frame_set: Mapping[str, object],
    mask_set: Mapping[str, object],
    masks: object,
) -> list[tuple[dict[str, object], object]]:
    import numpy as np

    mask_tensor = np.asarray(masks, dtype=bool)
    width, height = (int(value) for value in frame_set["resolution"])
    if mask_tensor.ndim != 3 or mask_tensor.shape[1:] != (height, width):
        raise ValueError("the Stable Mask tensor does not match the Frame Set")
    frames = {int(frame["frame_index"]): frame for frame in frame_set["frames"]}
    result: list[tuple[dict[str, object], object]] = []
    for mask_frame in mask_set["frames"]:
        if mask_frame["status"] != "accepted":
            continue
        frame_index = int(mask_frame["frame_index"])
        frame = frames.get(frame_index)
        mask_index = int(mask_frame["binary_mask_index"])
        mask_area = (
            int(mask_tensor[mask_index].sum())
            if 0 <= mask_index < len(mask_tensor)
            else -1
        )
        if (
            frame is None
            or frame["candidate_id"] != mask_frame["candidate_id"]
            or not 0 <= mask_index < len(mask_tensor)
            or mask_area != int(mask_frame["mask_area_pixels"])
        ):
            raise ValueError("the Frame Set and Stable Mask Set identity disagree")
        # A zero-area observation is unobserved, not negative Evidence.
        if mask_area == 0:
            continue
        result.append((deepcopy(frame), mask_tensor[mask_index]))
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
    target_count: int,
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
    evidence_working_set = create_evidence_working_set(
        {
            "targetSplatId": "controlled-overlap",
            "coreTargetStableIds": stable_ids[:target_count],
            "contextStableGaussianIds": stable_ids[target_count:],
        }
    )
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
    target_count: int,
    camera: Mapping[str, object],
    view_id: str,
    mask_artifact: Mapping[str, object],
    depth_policy: DepthMomentValidityPolicy,
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, object]:
    """Measure and retain one unchanged production single-N result."""

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
    for run_index in range(warmup_runs + measured_runs):
        torch.cuda.synchronize()
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
            depth_moments_enabled=True,
        )
        torch.cuda.synchronize()
        if run_index >= warmup_runs:
            direct_times.append((time.perf_counter() - started) * 1000.0)
    assert direct is not None and direct.depth_moments is not None

    camera_digest = canonical_json_digest(camera)
    current_input = _current_input(
        scene_digest=str(snapshot["sceneVersion"]),
        view_id=view_id,
        camera_digest=camera_digest,
        rgb_digest=_png_digest(direct.service_rgb_bytes, width, height),
        stable_mask_digest=str(mask_artifact["digest"]),
        evidence_policy_digest=str(evidence_policy["evidencePolicyDigest"]),
        stable_ids=sorted_ids,
        target_count=target_count,
    )
    admitted = admit_gaussian_evidence(current_input)
    if admitted.get("status") != "admitted":
        raise RuntimeError(f"the production baseline identity was rejected: {admitted}")
    baseline_artifact = create_gaussian_evidence_artifact(
        admitted["admission"],
        {
            "positiveMass": direct.positive_mass.detach().cpu().tolist(),
            "negativeMass": direct.negative_mass.detach().cpu().tolist(),
            "visibleMass": direct.visible_mass.detach().cpu().tolist(),
            "boundaryMass": direct.boundary_mass.detach().cpu().tolist(),
        },
    )
    identity = create_depth_moment_readout_identity(
        admitted["admission"],
        render_stable_ids_by_projected_row=stable_ids,
        policy=depth_policy,
        width=width,
        height=height,
        direct_evidence_abi_version=DIRECT_EVIDENCE_ABI_VERSION,
        direct_evidence_source_revision=DIRECT_EVIDENCE_SOURCE_REVISION,
        direct_evidence_runtime_build_id=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
    )
    return {
        "camera": deepcopy(camera),
        "cameraDigest": camera_digest,
        "maskArtifact": deepcopy(mask_artifact),
        "pixelWeights": pixel_weights,
        "currentInput": current_input,
        "baselineArtifact": baseline_artifact,
        "baselineNegativeMass": direct.negative_mass,
        "directServiceRgbDigest": direct.service_rgb_digest,
        "depthReadout": DepthMomentReadoutRecord(
            identity=identity,
            raw_depth_moments=direct.depth_moments,
            policy=depth_policy,
            telemetry=DepthMomentTelemetry(
                depth_moment_buffer_bytes=direct.telemetry.depth_moment_buffer_bytes,
                peak_vram_bytes=direct.telemetry.peak_vram_bytes,
            ),
        ),
        "directLatencyMilliseconds": statistics.median(direct_times),
        "directPeakVramBytes": int(direct.telemetry.peak_vram_bytes),
    }


def _projected_depth_rows(
    snapshot: Mapping[str, object], camera: Mapping[str, object]
) -> object:
    """Project Gaussian centers by row; this is not a pixel depth raster."""

    import torch

    gaussians = snapshot.get("gaussians")
    if not isinstance(gaussians, list) or not gaussians:
        raise ValueError("the Scene Snapshot has no projected-row geometry")
    positions = torch.tensor(
        [gaussian["mean"] for gaussian in gaussians],
        dtype=torch.float32,
        device="cuda",
    )
    world_to_camera = torch.tensor(
        camera["worldToCamera"], dtype=torch.float32, device="cuda"
    ).reshape(4, 4)
    depths = (positions @ world_to_camera[2, :3] + world_to_camera[2, 3]).contiguous()
    if not bool(torch.isfinite(depths).all().item()):
        raise ValueError("the projected Gaussian center depth is non-finite")
    return depths


def _build_sidecar_for_view(
    *,
    backend: LockedGsplatBackend,
    snapshot: Mapping[str, object],
    stable_ids: list[int],
    baseline: Mapping[str, object],
    relation_config: Mapping[str, object],
    warmup_runs: int,
    measured_runs: int,
) -> dict[str, object]:
    """Measure a reconciled complete-Contributor experimental sidecar."""

    import torch

    mask_artifact = baseline["maskArtifact"]
    width = int(mask_artifact["width"])
    height = int(mask_artifact["height"])
    projected_depths = _projected_depth_rows(snapshot, baseline["camera"])
    sorted_ids = sorted(stable_ids)
    sidecar = None
    times: list[float] = []
    torch.cuda.reset_peak_memory_stats()
    for run_index in range(warmup_runs + measured_runs):
        torch.cuda.synchronize()
        started = time.perf_counter()
        reference = backend.rasterize_reference_evidence_typed(
            snapshot=snapshot,
            camera=baseline["camera"],
            width=width,
            height=height,
            stable_ids=stable_ids,
        )
        if reference.service_rgb_digest != baseline["directServiceRgbDigest"]:
            raise ValueError(
                "the reference Contributor stream does not match baseline RGB"
            )
        accepted_sequence_digest = _tensor_digest(
            "accepted-contribution-sequence/v1",
            reference.stable_ids,
            reference.contributor_ids,
            reference.contributor_weights,
            projected_depths,
        )
        sidecar = build_depth_classified_negative_evidence_sidecar(
            relation_config=relation_config,
            depth_readout=baseline["depthReadout"],
            stable_ids_by_projected_row=stable_ids,
            evidence_stable_ids=sorted_ids,
            contributor_row_ids=reference.contributor_ids.contiguous(),
            contributor_weights=reference.contributor_weights.contiguous(),
            projected_depth_by_row=projected_depths,
            negative_pixel_weights=baseline["pixelWeights"][2][1],
            baseline_negative_mass=baseline["baselineNegativeMass"],
            baseline_artifact_digest=str(
                baseline["baselineArtifact"]["artifactDigest"]
            ),
            accepted_contribution_sequence_digest=accepted_sequence_digest,
        )
        torch.cuda.synchronize()
        if run_index >= warmup_runs:
            times.append((time.perf_counter() - started) * 1000.0)
    assert sidecar is not None
    return {
        "sidecar": sidecar,
        "latencyMilliseconds": statistics.median(times),
        "peakVramBytes": int(torch.cuda.max_memory_allocated()),
    }


def predict(arguments: argparse.Namespace) -> dict[str, object]:
    import numpy as np
    import torch

    configuration = load_depth_classified_negative_evidence_configuration(
        arguments.configuration
    )
    scene = _scene(configuration, arguments.scene_id)
    if arguments.seed not in scene["seeds"]:
        raise ValueError("the requested seed is not in the sealed scene configuration")
    if arguments.output.exists():
        raise ValueError(f"refusing to overwrite prediction output: {arguments.output}")
    runtime_status = current_renderer_runtime().status()
    if runtime_status.status != "ready":
        raise RuntimeError(
            f"the locked renderer runtime is unavailable: {runtime_status.message}"
        )

    configuration_root = arguments.configuration.resolve().parent
    snapshot_path = configuration_root / scene["sceneSnapshot"]
    frame_set_path = configuration_root / scene["frameSetManifest"]
    mask_set_path = configuration_root / scene["stableMaskManifest"]
    masks_path = configuration_root / scene["stableMasks"]
    snapshot = build_controlled_overlap_snapshot(snapshot_path)
    stable_ids = [int(value) for value in validate_supported_snapshot(snapshot)]
    fixture_manifest = json.loads(
        (configuration_root / scene["fixtureManifest"]).read_text(encoding="utf-8")
    )
    target_count = int(fixture_manifest["targetCount"])
    frame_set = json.loads(frame_set_path.read_text(encoding="utf-8"))
    mask_set = json.loads(mask_set_path.read_text(encoding="utf-8"))
    with np.load(masks_path, allow_pickle=False) as archive:
        frames = _accepted_frames(frame_set, mask_set, archive["masks"])

    relation_config = configuration["relationConfigs"][0]
    depth_policy_config = configuration["depthMomentValidityPolicy"]
    depth_policy = DepthMomentValidityPolicy(
        policy_id=str(depth_policy_config["policyId"]),
        minimum_m0=float(depth_policy_config["minimumM0"]),
    )
    measurement = configuration["measurementPolicy"]
    backend = LockedGsplatBackend()
    torch.cuda.reset_peak_memory_stats()
    per_view: dict[str, dict[str, object]] = {}
    for frame, mask in frames:
        view_id = str(frame["candidate_id"])
        mask_input = _mask_artifact(mask)
        per_view[view_id] = _render_baseline_view(
            backend=backend,
            snapshot=snapshot,
            stable_ids=stable_ids,
            target_count=target_count,
            camera=_camera(frame, frame_set),
            view_id=view_id,
            mask_artifact=mask_input,
            depth_policy=depth_policy,
            warmup_runs=int(measurement["warmupRuns"]),
            measured_runs=int(measurement["measuredRuns"]),
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
    baseline_aggregation = aggregate_reference_gaussian_evidence(
        aggregation_input, aggregation_policy
    )
    baseline_candidate = _candidate_replay(baseline_aggregation)
    input_identity = create_experiment_input_identity(
        scene_snapshot_digest=_sha256(snapshot_path),
        camera_bindings_digest=canonical_json_digest(
            {view_id: per_view[view_id]["cameraDigest"] for view_id in view_ids}
        ),
        stable_masks_digest=_sha256(masks_path),
        working_sets_digest=canonical_json_digest(
            {
                "evidenceWorkingSet": first_input["evidenceWorkingSet"],
                "renderWorkingSets": [
                    per_view[view_id]["currentInput"]["renderWorkingSet"]
                    for view_id in view_ids
                ],
            }
        ),
        renderer_runtime_digest=DIRECT_EVIDENCE_RUNTIME_BUILD_ID,
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
        "torchVersion": torch.__version__,
        "cudaVersion": str(torch.version.cuda),
        "gsplatSourceCommit": EXPECTED_GSPLAT_SOURCE_COMMIT,
    }
    baseline_latency_ms = sum(
        float(per_view[view_id]["directLatencyMilliseconds"]) for view_id in view_ids
    )
    production_negative_writes = len(view_ids) * len(stable_ids)
    baseline_record = create_baseline_run_record(
        input_identity=input_identity,
        baseline_artifact_digests=[
            str(per_view[view_id]["baselineArtifact"]["artifactDigest"])
            for view_id in view_ids
        ],
        candidate_replay=baseline_candidate,
        runtime_source=runtime_source,
        timing_and_vram={
            "latencyMilliseconds": baseline_latency_ms,
            "peakVramBytes": max(
                int(per_view[view_id]["directPeakVramBytes"]) for view_id in view_ids
            ),
        },
        buffer_writes={
            "productionNegativeMass": production_negative_writes,
            "classifiedSidecar": 0,
            "total": production_negative_writes,
        },
    )

    arguments.output.mkdir(parents=True)
    _write_json(arguments.output / "configuration.json", configuration)
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

    sidecar_results: dict[str, dict[str, object]] = {}
    try:
        for view_id in view_ids:
            sidecar_results[view_id] = _build_sidecar_for_view(
                backend=backend,
                snapshot=snapshot,
                stable_ids=stable_ids,
                baseline=per_view[view_id],
                relation_config=relation_config,
                warmup_runs=int(measurement["warmupRuns"]),
                measured_runs=int(measurement["measuredRuns"]),
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
    for ordinal, method in enumerate(configuration["variantMethods"]):
        replay = None
        replay_times: list[float] = []
        for run_index in range(
            int(measurement["warmupRuns"]) + int(measurement["measuredRuns"])
        ):
            replay_started = time.perf_counter()
            replay = replay_depth_classified_negative_evidence(
                aggregation_input=aggregation_input,
                sidecars_by_view_id=sidecars_by_view_id,
                replay_config=method,
                aggregation_policy=aggregation_policy,
            )
            if run_index >= int(measurement["warmupRuns"]):
                replay_times.append((time.perf_counter() - replay_started) * 1000.0)
        assert replay is not None
        replay_ms = statistics.median(replay_times)
        _write_json(
            arguments.output / "candidate-replays" / f"variant-{ordinal:03d}.json",
            replay,
        )
        channel_elements = len(view_ids) * len(stable_ids)
        writes = {
            "front": channel_elements,
            "near": channel_elements,
            "behind": channel_elements,
            "invalidDepth": channel_elements,
        }
        classified_writes = sum(writes.values())
        writes["productionNegativeMass"] = production_negative_writes
        writes["classifiedSidecar"] = classified_writes
        writes["total"] = production_negative_writes + classified_writes
        record = create_variant_run_record(
            input_identity=input_identity,
            replay_config=method,
            sidecar_digests=[
                str(sidecars_by_view_id[view_id]["artifactDigest"])
                for view_id in view_ids
            ],
            candidate_replay=replay,
            runtime_source=runtime_source,
            timing_and_vram={
                "latencyMilliseconds": baseline_latency_ms
                + sum(
                    float(sidecar_results[view_id]["latencyMilliseconds"])
                    for view_id in view_ids
                )
                + replay_ms,
                "peakVramBytes": max(
                    int(sidecar_results[view_id]["peakVramBytes"])
                    for view_id in view_ids
                ),
            },
            buffer_writes=writes,
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
        (scene["sceneSnapshotSha256"], seed)
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
        f"- Runtime: torch `{scores[0]['methods'][0]['runtimeSource']['torchVersion']}`, CUDA `{scores[0]['methods'][0]['runtimeSource']['cudaVersion']}`, gsplat source `{scores[0]['methods'][0]['runtimeSource']['gsplatSourceCommit']}`.",
        "",
        "## Trial results",
        "",
        "| Scene digest | Seed | Method | Precision | Recall | Distractor leaks | Thin/edge retention | Latency ms | Peak VRAM bytes | Buffer writes | Gate |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for score in scores:
        identity = score["inputIdentity"]
        for method in score["methods"]:
            metrics = method["metrics"]
            thin = metrics["thinOrEdgeRetention"]
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
                        f"{float(method['timingAndVram']['latencyMilliseconds']):.3f}",
                        str(method["timingAndVram"]["peakVramBytes"]),
                        str(method["bufferWrites"]["total"]),
                        "pass" if method["qualityGatePassed"] else "fail",
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
            "- Every classified sidecar and Candidate replay used the same input identity digest as the baseline.",
            "- Ground Truth was opened only by the independent scorer after prediction hash verification.",
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
