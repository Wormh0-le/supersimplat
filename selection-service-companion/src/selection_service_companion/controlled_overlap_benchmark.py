"""Production benchmark path for the frozen controlled-overlap fixture."""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import platform
import struct
import tempfile
import time
from typing import Any, Mapping, Sequence

from .benchmark import PocRunRecordError, SealedPrediction, seal_prediction


_EXPECTED_PROPERTIES = (
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
    "property uchar benchmark_class",
)
_VERTEX = struct.Struct("<14fIB")


def build_controlled_overlap_snapshot(ply_path: Path) -> dict[str, object]:
    """Read the exact frozen PLY into supported SuperSplat-v1 semantics."""

    source = ply_path.read_bytes()
    marker = b"end_header\n"
    header_end = source.find(marker)
    if header_end < 0:
        raise PocRunRecordError("controlled-overlap PLY has no complete header")
    header = source[: header_end + len(marker)].decode("ascii").splitlines()
    if header[:2] != ["ply", "format binary_little_endian 1.0"]:
        raise PocRunRecordError("controlled-overlap PLY encoding is unsupported")
    try:
        element = next(line for line in header if line.startswith("element vertex "))
        gaussian_count = int(element.removeprefix("element vertex "))
    except (StopIteration, ValueError) as error:
        raise PocRunRecordError(
            "controlled-overlap PLY vertex count is invalid"
        ) from error
    properties = tuple(line for line in header if line.startswith("property "))
    if properties != _EXPECTED_PROPERTIES:
        raise PocRunRecordError("controlled-overlap PLY property schema is unsupported")
    payload = source[header_end + len(marker) :]
    if len(payload) != gaussian_count * _VERTEX.size:
        raise PocRunRecordError("controlled-overlap PLY payload length is invalid")

    gaussians: list[dict[str, object]] = []
    known_ids: set[int] = set()
    for values in _VERTEX.iter_unpack(payload):
        stable_id = values[14]
        if stable_id in known_ids or stable_id > 0xFFFFFFFF:
            raise PocRunRecordError(
                "controlled-overlap Stable Gaussian IDs are invalid"
            )
        known_ids.add(stable_id)
        gaussians.append(
            {
                "stableId": stable_id,
                "mean": list(values[0:3]),
                # PLY stores the conventional wxyz tuple; the protocol is xyzw.
                "rotation": [values[11], values[12], values[13], values[10]],
                "logScale": list(values[7:10]),
                "logitOpacity": values[6],
                "dc": list(values[3:6]),
                "sh": [],
            }
        )
    digest = hashlib.sha256(source).hexdigest()
    return {
        "protocolVersion": "1",
        "sceneId": "controlled-overlap",
        "sceneVersion": f"sha256:{digest}",
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


def seal_preview_prediction(
    output_directory: Path,
    *,
    publication: Any,
    scene_snapshot: Mapping[str, object],
    prompt_log: Sequence[Mapping[str, object]],
    model_manifest: Mapping[str, object],
    runtime_manifest: Mapping[str, object],
    dependency_lock: Path,
    render_policy: Mapping[str, object],
    correction_outcomes: Sequence[Mapping[str, object]],
    timing_and_vram: Mapping[str, object],
    internal_diagnostics: Mapping[str, object],
    bindings: Mapping[str, object],
) -> SealedPrediction:
    """Materialize one complete Companion publication as a blind run record."""

    records = publication.evidence_snapshot.get("records")
    if not isinstance(records, list):
        raise PocRunRecordError("Evidence Snapshot records are unavailable")
    classifications: dict[str, list[int]] = {
        "selected": [],
        "rejected": [],
        "uncertain": [],
    }
    for record in records:
        if not isinstance(record, dict):
            raise PocRunRecordError("Evidence Snapshot record is malformed")
        stable_id = record.get("stableId")
        classification = record.get("classification")
        if (
            not isinstance(stable_id, int)
            or isinstance(stable_id, bool)
            or stable_id < 0
            or stable_id > 0xFFFFFFFF
            or classification not in classifications
        ):
            raise PocRunRecordError("Evidence Snapshot classification is malformed")
        classifications[classification].append(stable_id)
    candidate = {
        "selectedStableGaussianIds": sorted(classifications["selected"]),
        "rejectedStableGaussianIds": sorted(classifications["rejected"]),
        "uncertainStableGaussianIds": sorted(classifications["uncertain"]),
    }

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="poc-prediction-artifacts-", dir=output_directory.parent
    ) as temporary:
        artifact_root = Path(temporary)
        values: dict[str, object] = {
            "sceneSnapshot": scene_snapshot,
            "benchmarkPromptLog": list(prompt_log),
            "frameSet": publication.frame_set,
            "maskSet": publication.mask_set,
            "candidateObjectSelection": candidate,
            "evidenceSnapshot": publication.evidence_snapshot,
            "coverageReport": publication.coverage_report,
            "modelManifest": model_manifest,
            "runtimeManifest": runtime_manifest,
            "renderPolicy": render_policy,
            "correctionOutcomes": list(correction_outcomes),
            "timingAndVram": timing_and_vram,
            "internalDiagnostics": internal_diagnostics,
        }
        artifacts: dict[str, Path] = {}
        for name, value in values.items():
            path = artifact_root / f"{name}.json"
            path.write_text(
                json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            artifacts[name] = path
        artifacts["dependencyLock"] = dependency_lock
        return seal_prediction(
            output_directory,
            artifacts=artifacts,
            bindings=bindings,
        )


def run_controlled_overlap_prediction(
    output_directory: Path,
    *,
    fixture_ply: Path,
    dependency_lock: Path,
    state_directory: Path,
    model_manifest_digest: str | None = None,
    image_size: int = 1008,
    deterministic_seed: str = "controlled-overlap-seed-1",
) -> SealedPrediction:
    """Execute the production path and seal either completion or failure."""

    if output_directory.exists():
        raise PocRunRecordError(
            f"refusing to overwrite an existing PoC Run Record: {output_directory}"
        )
    started = time.perf_counter()
    try:
        return _run_controlled_overlap_prediction(
            output_directory,
            fixture_ply=fixture_ply,
            dependency_lock=dependency_lock,
            state_directory=state_directory,
            model_manifest_digest=model_manifest_digest,
            image_size=image_size,
            deterministic_seed=deterministic_seed,
        )
    except Exception as error:
        return _seal_failed_controlled_overlap_prediction(
            output_directory,
            fixture_ply=fixture_ply,
            dependency_lock=dependency_lock,
            state_directory=state_directory,
            deterministic_seed=deterministic_seed,
            elapsed_seconds=time.perf_counter() - started,
            error=error,
        )


def _run_controlled_overlap_prediction(
    output_directory: Path,
    *,
    fixture_ply: Path,
    dependency_lock: Path,
    state_directory: Path,
    model_manifest_digest: str | None,
    image_size: int,
    deterministic_seed: str,
) -> SealedPrediction:
    """Execute and seal the real gsplat/CUDA and SAM3 Generated View path."""

    if image_size != 1008:
        raise PocRunRecordError(
            "the controlled-overlap production Anchor must use the 1008-pixel policy baseline"
        )
    from PIL import Image
    import torch

    from . import PACKAGE_VERSION, PROTOCOL_VERSION
    from .evidence import evidence_policy
    from .generated_views import (
        NEIGHBOR_ANOMALY_POLICY_ID,
        NEIGHBOR_ANOMALY_THRESHOLDS,
        PREFLIGHT_POLICY_ID,
    )
    from .state import CompanionState

    state = CompanionState(state_directory)
    release = state.require_release()
    available_models = [
        model
        for model in state.available_models()
        if model.get("adapterId") == "sam3.1"
        and (
            model_manifest_digest is None
            or model.get("digest") == model_manifest_digest
        )
    ]
    if len(available_models) != 1:
        raise PocRunRecordError(
            "the production trial requires exactly one matching installed SAM3.1 Model Manifest"
        )
    model = available_models[0]
    renderer = state.contributor_renderer
    if renderer is None or not getattr(renderer, "requires_locked_runtime", False):
        raise PocRunRecordError(
            "the locked production gsplat/CUDA renderer is unavailable"
        )

    snapshot = build_controlled_overlap_snapshot(fixture_ply)
    camera = _anchor_camera(image_size)
    anchor_started = time.perf_counter()
    rasterized = renderer.backend.rasterize(
        snapshot=snapshot,
        camera=camera,
        width=image_size,
        height=image_size,
    )
    anchor_seconds = time.perf_counter() - anchor_started
    anchor_png_buffer = BytesIO()
    Image.frombytes("RGB", (image_size, image_size), rasterized.service_rgb_bytes).save(
        anchor_png_buffer, format="PNG"
    )
    anchor_png = anchor_png_buffer.getvalue()
    anchor_digest = f"sha256:{hashlib.sha256(anchor_png).hexdigest()}"
    frame_set_version = f"controlled-anchor:{anchor_digest}"
    frame_set = {
        "frameSetId": "controlled-overlap-anchor",
        "frameSetVersion": frame_set_version,
        "orderedViews": [
            {
                "viewId": "anchor-view",
                "frameDigest": anchor_digest,
                "width": image_size,
                "height": image_size,
                "imagePngBase64": base64.b64encode(anchor_png).decode("ascii"),
                "source": "anchor",
                "camera": camera,
            }
        ],
    }
    state.register_scene_snapshot(snapshot)
    state.register_frame_set(frame_set)
    session_id = state.open_object_selection_session(
        frame_set_version=frame_set_version,
        model_manifest_digest=str(model["digest"]),
        open_request_id=f"controlled-overlap:{deterministic_seed}",
    )
    if session_id is None:
        raise PocRunRecordError(
            "the Companion is busy with another Object Selection Session"
        )
    bindings = {
        "requestId": f"controlled-overlap-preview:{deterministic_seed}",
        "sessionId": session_id,
        "targetSplatId": "controlled-overlap",
        "sceneId": snapshot["sceneId"],
        "sceneVersion": snapshot["sceneVersion"],
        "operation": "New",
        "correctionRound": 0,
        "deterministicSeed": deterministic_seed,
        "promptLogRevision": 1,
        "frameSetVersion": frame_set_version,
        "renderConfigVersion": "supersplat-effective-rgb-v1",
        "modelManifestDigest": model["digest"],
    }
    prompt_log = [
        {
            "operation": "New",
            "prompt": {
                "promptId": "controlled-overlap-center",
                "viewId": "anchor-view",
                "frameDigest": anchor_digest,
                "frameWidth": image_size,
                "frameHeight": image_size,
                "xPx": image_size // 2,
                "yPx": image_size // 2,
                "polarity": "include",
            },
        }
    ]
    preview_started = time.perf_counter()
    try:
        publication = state.update_preview_publication(
            bindings=bindings,
            prompt_log=prompt_log,
        )
    finally:
        state.close_object_selection_session(session_id)
    preview_seconds = time.perf_counter() - preview_started

    capabilities = state.capabilities()
    runtime_manifest = {
        "companionVersion": PACKAGE_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "release": release,
        "renderer": capabilities.get("renderer"),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cudaRuntime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
    }
    public_model_manifest = {
        key: value
        for key, value in model.items()
        if key not in {"weightsPath", "installedAt"}
    }
    quality_diagnostics = publication.coverage_report.get("qualityDiagnostics", {})
    internal_diagnostics = {
        "attemptedViewIds": publication.coverage_report.get("attemptedViewIds", []),
        "rejectedViews": publication.coverage_report.get("rejectedViews", []),
        "qualityDiagnostics": quality_diagnostics,
        "renderResolution": publication.bindings.get("renderConfigVersion"),
    }
    peak_vram_bytes = max(
        int(rasterized.peak_vram_bytes or 0),
        int(getattr(renderer, "last_peak_vram_bytes", 0) or 0),
    )
    return seal_preview_prediction(
        output_directory,
        publication=publication,
        scene_snapshot=snapshot,
        prompt_log=prompt_log,
        model_manifest=public_model_manifest,
        runtime_manifest=runtime_manifest,
        dependency_lock=dependency_lock,
        render_policy={
            "renderConfigVersion": publication.bindings.get("renderConfigVersion"),
            "cameraPreflightPolicy": PREFLIGHT_POLICY_ID,
            "neighborAnomalyPolicy": NEIGHBOR_ANOMALY_POLICY_ID,
            "neighborAnomalyThresholds": NEIGHBOR_ANOMALY_THRESHOLDS,
            "evidencePolicy": evidence_policy(),
        },
        correction_outcomes=[
            {
                "operation": "New",
                "correctionRound": 0,
                "requestId": publication.bindings.get("requestId"),
                "terminalState": "complete",
            }
        ],
        timing_and_vram={
            "anchorRenderSeconds": anchor_seconds,
            "previewSeconds": preview_seconds,
            "peakVramBytes": peak_vram_bytes,
        },
        internal_diagnostics=internal_diagnostics,
        bindings={
            "trialId": f"controlled-overlap:{deterministic_seed}",
            "protocolVersion": PROTOCOL_VERSION,
            "deterministicSeed": deterministic_seed,
            "terminalState": "complete",
            **publication.bindings,
        },
    )


def _seal_failed_controlled_overlap_prediction(
    output_directory: Path,
    *,
    fixture_ply: Path,
    dependency_lock: Path,
    state_directory: Path,
    deterministic_seed: str,
    elapsed_seconds: float,
    error: Exception,
) -> SealedPrediction:
    from . import PACKAGE_VERSION, PROTOCOL_VERSION
    from .masking import MaskSessionError
    from .state import CompanionState

    error_code = (
        error.code if isinstance(error, MaskSessionError) else type(error).__name__
    )
    try:
        snapshot: object = build_controlled_overlap_snapshot(fixture_ply)
    except Exception as snapshot_error:
        snapshot = {
            "status": "unavailable",
            "reason": type(snapshot_error).__name__,
            "message": str(snapshot_error),
        }
    state = CompanionState(state_directory)
    models = state.models()
    model_manifest: object = (
        {
            key: value
            for key, value in models[0].items()
            if key not in {"weightsPath", "installedAt"}
        }
        if len(models) == 1
        else {"status": "unavailable", "modelCount": len(models)}
    )
    try:
        release: object = state.require_release()
    except ValueError as release_error:
        release = {"status": "unavailable", "message": str(release_error)}
    unavailable = {
        "status": "unavailable",
        "terminalState": error_code,
        "reason": str(error),
    }
    values: dict[str, object] = {
        "sceneSnapshot": snapshot,
        "benchmarkPromptLog": {
            "status": "not-published",
            "intendedOperation": "New",
            "anchorPoint": [504, 504],
        },
        "frameSet": unavailable,
        "maskSet": unavailable,
        "candidateObjectSelection": unavailable,
        "evidenceSnapshot": unavailable,
        "coverageReport": unavailable,
        "modelManifest": model_manifest,
        "runtimeManifest": {
            "companionVersion": PACKAGE_VERSION,
            "protocolVersion": PROTOCOL_VERSION,
            "release": release,
            "python": platform.python_version(),
        },
        "renderPolicy": {
            "renderConfigVersion": "supersplat-effective-rgb-v1",
            "generatedViewResolutionBaseline": 1008,
        },
        "correctionOutcomes": [
            {"operation": "New", "correctionRound": 0, "terminalState": error_code}
        ],
        "timingAndVram": {
            "elapsedSeconds": elapsed_seconds,
            "peakVramBytes": None,
        },
        "internalDiagnostics": {
            "errorCode": error_code,
            "errorType": type(error).__name__,
            "message": str(error),
        },
    }
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="poc-failed-prediction-", dir=output_directory.parent
    ) as temporary:
        root = Path(temporary)
        artifacts: dict[str, Path] = {}
        for name, value in values.items():
            path = root / f"{name}.json"
            path.write_text(
                json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            artifacts[name] = path
        artifacts["dependencyLock"] = dependency_lock
        return seal_prediction(
            output_directory,
            artifacts=artifacts,
            bindings={
                "trialId": f"controlled-overlap:{deterministic_seed}",
                "protocolVersion": PROTOCOL_VERSION,
                "deterministicSeed": deterministic_seed,
                "terminalState": error_code,
            },
        )


def _anchor_camera(image_size: int) -> dict[str, object]:
    focal = 0.5 * image_size / math.tan(math.radians(42.0) * 0.5)
    return {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            3.2,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
        "intrinsics": [
            focal,
            0.0,
            image_size / 2,
            0.0,
            focal,
            image_size / 2,
            0.0,
            0.0,
            1.0,
        ],
        "nearPlane": 0.01,
        "farPlane": 20.0,
    }
