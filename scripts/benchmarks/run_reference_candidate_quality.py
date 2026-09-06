#!/usr/bin/env python3
"""Run Ticket 14D quality metrics against the locked GPU reference backend."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
COMPANION_SRC = ROOT / "selection-service-companion/src"
sys.path.insert(0, str(COMPANION_SRC))

from selection_service_companion.camera_binding import (  # noqa: E402
    camera_binding_digest,
)
from selection_service_companion.gaussian_evidence_contract import (  # noqa: E402
    create_evidence_working_set,
)
from selection_service_companion.gsplat_renderer import (  # noqa: E402
    GsplatContributorRenderer,
    GsplatRasterization,
    LockedGsplatBackend,
    REFERENCE_CONTRIBUTOR_EVIDENCE_BACKEND_ID,
    REFERENCE_EVIDENCE_RASTER_IMPLEMENTATION_ID,
    REFERENCE_EVIDENCE_RUNTIME_BUILD_ID,
)
from selection_service_companion.reference_candidate_publication import (  # noqa: E402
    create_reference_candidate_artifact,
)
from selection_service_companion.reference_candidate_quality import (  # noqa: E402
    score_reference_candidate_quality,
)
from selection_service_companion.reference_gaussian_evidence import (  # noqa: E402
    compare_available_reference_artifacts,
    default_reference_evidence_policy,
)
from selection_service_companion.reference_gaussian_evidence_aggregation import (  # noqa: E402
    aggregate_reference_gaussian_evidence,
    default_reference_aggregation_policy,
)
from selection_service_companion.renderer_runtime import (  # noqa: E402
    current_renderer_runtime,
)


WIDTH = 64
HEIGHT = 64
TARGET_IDS = [5, 11]
BACKGROUND_IDS = [9, 13]
ALL_IDS = [5, 9, 11, 13]
MASK_MASS_THRESHOLD = 0.02


def digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def dependency() -> dict[str, object]:
    return {
        "splatId": "editor-splat:ticket-14d-quality",
        "renderStateToken": "render-v1",
        "geometryToken": "geometry-v1",
        "gaussianIdentityToken": "gaussians-v1",
        "worldTransformToken": "transform-v1",
    }


def request_binding() -> dict[str, object]:
    return {
        "targetContextId": "ai-target-context-ticket-14d-quality",
        "contextRevision": 1,
        "dependencyToken": dependency(),
    }


def snapshot() -> dict[str, object]:
    positions = {
        5: (-0.30, 0.0, 2.0),
        11: (-0.08, 0.02, 2.1),
        9: (0.20, -0.01, 2.0),
        13: (0.42, 0.02, 2.1),
    }
    scene_version = digest(b"ticket-14d-locked-gpu-quality-scene-v1")
    return {
        "protocolVersion": "1",
        "sceneId": "ticket-14d-quality-scene",
        "sceneVersion": scene_version,
        "gaussianCount": len(ALL_IDS),
        "coordinateConvention": (
            "right-handed world coordinates; quaternion xyzw"
        ),
        "attributeSchema": (
            "mean:f32x3;rotation:f32x4;logScale:f32x3;"
            "logitOpacity:f32;dc:f32x3;sh:f32x0"
        ),
        "stableIdSchema": "uint32",
        "appearancePolicy": "effective-editor-dc-sh-bands-0",
        "renderConfiguration": {
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        "gaussians": [
            {
                "stableId": stable_id,
                "mean": list(positions[stable_id]),
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "logScale": [-2.15, -2.15, -2.15],
                "logitOpacity": 2.0,
                "dc": [0.2, 0.2, 0.2],
                "sh": [],
            }
            for stable_id in ALL_IDS
        ],
    }


def camera(camera_x: float) -> dict[str, object]:
    return {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": [
            1.0,
            0.0,
            0.0,
            -camera_x,
            0.0,
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
        ],
        "intrinsics": [
            64.0,
            0.0,
            WIDTH / 2,
            0.0,
            64.0,
            HEIGHT / 2,
            0.0,
            0.0,
            1.0,
        ],
        "nearPlane": 0.01,
        "farPlane": 100.0,
    }


def camera_binding(camera_x: float, revision: int) -> dict[str, object]:
    return {
        "revision": revision,
        "cameraToWorld": [
            1.0,
            0.0,
            0.0,
            camera_x,
            0.0,
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
        ],
        "projection": {
            "model": "pinhole",
            "fx": 64.0,
            "fy": 64.0,
            "cx": WIDTH / 2,
            "cy": HEIGHT / 2,
            "width": WIDTH,
            "height": HEIGHT,
            "near": 0.01,
            "far": 100.0,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }


def rendered_mask(
    raster: GsplatRasterization,
    stable_ids: set[int],
) -> list[bool]:
    result: list[bool] = []
    for id_row, weight_row in zip(
        raster.contributor_ids,
        raster.contributor_weights,
        strict=True,
    ):
        for pixel_ids, pixel_weights in zip(id_row, weight_row, strict=True):
            mass = sum(
                float(weight)
                for row_id, weight in zip(pixel_ids, pixel_weights, strict=True)
                if row_id >= 0 and ALL_IDS[row_id] in stable_ids
            )
            result.append(mass >= MASK_MASS_THRESHOLD)
    return result


def mask_artifact(mask: list[bool]) -> dict[str, object]:
    bits = bytearray((len(mask) + 7) // 8)
    for pixel_index, foreground in enumerate(mask):
        if foreground:
            bits[pixel_index // 8] |= 1 << (pixel_index % 8)
    return {
        "encoding": "bitset-lsb-v1",
        "width": WIDTH,
        "height": HEIGHT,
        "data": base64.b64encode(bits).decode("ascii"),
        "digest": digest(bytes(bits)),
    }


def evidence_input(
    *,
    view_id: str,
    binding: dict[str, object],
    rgb_digest: str,
    stable_mask_digest: str,
    working_set: dict[str, object],
    scene_version: str,
) -> dict[str, object]:
    binding_digest = camera_binding_digest(binding)
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:ticket-14d-quality",
        "view": {
            "viewId": view_id,
            "renderStatus": "ready",
            "participation": "included",
            "cameraBindingDigest": binding_digest,
            "rgbDigest": rgb_digest,
            "stableMaskDigest": stable_mask_digest,
        },
        "evidencePolicyDigest": default_reference_evidence_policy()[
            "evidencePolicyDigest"
        ],
        "renderWorkingSet": {
            "targetSplatId": "editor-splat:ticket-14d-quality",
            "dependencyToken": dependency(),
            "cameraBindingDigest": binding_digest,
            "renderWorkingSetToken": scene_version,
            "stableGaussianIds": ALL_IDS,
            "completeness": "complete",
        },
        "evidenceWorkingSet": working_set,
        "rasterImplementationId": REFERENCE_EVIDENCE_RASTER_IMPLEMENTATION_ID,
        "evidenceBackendKind": "reference-contributor",
        "evidenceBackendId": REFERENCE_CONTRIBUTOR_EVIDENCE_BACKEND_ID,
        "runtimeBuildId": REFERENCE_EVIDENCE_RUNTIME_BUILD_ID,
    }


def aggregate_input(
    working_set: dict[str, object],
    views: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "requestBinding": request_binding(),
        "targetSplatId": "editor-splat:ticket-14d-quality",
        "classificationUniverseStableGaussianIds": ALL_IDS,
        "classificationScopeStableGaussianIds": ALL_IDS,
        "evidenceWorkingSet": working_set,
        "views": views,
    }


def comparison_summary(comparison: dict[str, object]) -> dict[str, int]:
    comparisons = comparison["comparisons"]
    assert isinstance(comparisons, list)
    threshold_near_count = sum(
        int(channel["thresholdNearDifferenceCount"])
        for pair in comparisons
        for channel in pair["channels"].values()
    )
    return {
        "availableBackendPairs": len(comparisons),
        "thresholdNearCount": threshold_near_count,
        "classificationDifferenceCount": 0,
    }


def main() -> None:
    import torch

    runtime = current_renderer_runtime().status()
    if runtime.status != "ready":
        raise RuntimeError(
            f"Ticket 14D quality requires the locked renderer runtime: {runtime.message}"
        )
    scene = snapshot()
    scene_version = str(scene["sceneVersion"])
    working_set = create_evidence_working_set(
        {
            "targetSplatId": "editor-splat:ticket-14d-quality",
            "coreTargetStableIds": TARGET_IDS,
            "contextStableGaussianIds": BACKGROUND_IDS,
        }
    )
    backend = LockedGsplatBackend()
    renderer = GsplatContributorRenderer(backend=backend)
    view_records: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    view_specs = [("anchor-view", 0.0, 1), ("key-view-1", 0.12, 2)]
    for view_id, camera_x, revision in view_specs:
        view_camera = camera(camera_x)
        binding = camera_binding(camera_x, revision)
        raster = backend.rasterize(
            snapshot=scene,
            camera=view_camera,
            width=WIDTH,
            height=HEIGHT,
        )
        stable_mask = mask_artifact(rendered_mask(raster, set(TARGET_IDS)))
        rgb = renderer.render_anchor(
            scene_snapshot=scene,
            view_id=view_id,
            camera=view_camera,
            width=WIDTH,
            height=HEIGHT,
        )
        current_input = evidence_input(
            view_id=view_id,
            binding=binding,
            rgb_digest=rgb.rgb_digest,
            stable_mask_digest=str(stable_mask["digest"]),
            working_set=working_set,
            scene_version=scene_version,
        )
        artifact = renderer.compute_reference_evidence(
            admission_input=current_input,
            stable_mask_artifact=stable_mask,
            policy=default_reference_evidence_policy(),
            scene_snapshot=scene,
            camera_binding=binding,
        )
        artifacts.append(artifact)
        view_records.append(
            {"currentInput": current_input, "artifact": artifact}
        )

    aggregation_policy = default_reference_aggregation_policy()
    multi_input = aggregate_input(working_set, view_records)
    multi_result = aggregate_reference_gaussian_evidence(
        multi_input,
        aggregation_policy,
    )
    single_input = aggregate_input(working_set, [view_records[0]])
    single_result = aggregate_reference_gaussian_evidence(
        single_input,
        aggregation_policy,
    )
    excluded_record = deepcopy(view_records[1])
    excluded_record["currentInput"]["view"]["participation"] = "excluded"
    excluded_record.pop("artifact")
    excluded_input = aggregate_input(
        working_set,
        [view_records[0], excluded_record],
    )
    excluded_result = aggregate_reference_gaussian_evidence(
        excluded_input,
        aggregation_policy,
    )
    candidate = create_reference_candidate_artifact(multi_input, multi_result)

    novel_raster = backend.rasterize(
        snapshot=scene,
        camera=camera(-0.12),
        width=WIDTH,
        height=HEIGHT,
    )
    predicted_mask = rendered_mask(
        novel_raster,
        set(multi_result["selectedStableGaussianIds"]),
    )
    ground_truth_mask = rendered_mask(novel_raster, set(TARGET_IDS))
    comparison = compare_available_reference_artifacts(
        [artifacts[0]],
        thresholds={"positiveMass": [1.0]},
        threshold_near_absolute_tolerance=0.001,
    )
    quality = score_reference_candidate_quality(
        {
            "selectedStableGaussianIds": multi_result[
                "selectedStableGaussianIds"
            ],
            "uncertainStableGaussianIds": multi_result[
                "uncertainStableGaussianIds"
            ],
            "rejectedStableGaussianIds": multi_result[
                "rejectedStableGaussianIds"
            ],
            "truthSelectedStableGaussianIds": TARGET_IDS,
            "truthBackgroundStableGaussianIds": BACKGROUND_IDS,
            "singleViewSelectedStableGaussianIds": single_result[
                "selectedStableGaussianIds"
            ],
            "novelViewPredictedMask": predicted_mask,
            "novelViewGroundTruthMask": ground_truth_mask,
            "excludedViewSelectedStableGaussianIds": excluded_result[
                "selectedStableGaussianIds"
            ],
            "expectedExcludedViewSelectedStableGaussianIds": single_result[
                "selectedStableGaussianIds"
            ],
            "referenceComparison": comparison_summary(comparison),
        }
    )
    device = torch.cuda.get_device_properties(torch.cuda.current_device())
    result = {
        "fixtureId": "ticket-14d-locked-gpu-reference-quality/v1",
        "artifactKind": "reference-pre-production",
        "execution": {
            "backend": "locked-gpu-reference-contributor",
            "runtimeStatus": runtime.status,
            "runtimeBuildId": REFERENCE_EVIDENCE_RUNTIME_BUILD_ID,
            "rasterImplementationId": (
                REFERENCE_EVIDENCE_RASTER_IMPLEMENTATION_ID
            ),
            "evidenceBackendId": REFERENCE_CONTRIBUTOR_EVIDENCE_BACKEND_ID,
            "gpuName": device.name,
            "peakVramBytes": renderer.peak_vram_bytes,
        },
        "candidateDigest": candidate["candidateDigest"],
        "candidate": candidate["candidate"],
        "uncertain": candidate["uncertain"],
        "quality": quality,
        "novelView": {
            "cameraX": -0.12,
            "width": WIDTH,
            "height": HEIGHT,
            "maskMassThreshold": MASK_MASS_THRESHOLD,
            "predictedMaskDigest": digest(
                bytes(int(value) for value in predicted_mask)
            ),
            "groundTruthMaskDigest": digest(
                bytes(int(value) for value in ground_truth_mask)
            ),
            "predictedForegroundPixels": sum(predicted_mask),
            "groundTruthForegroundPixels": sum(ground_truth_mask),
        },
        "referenceComparison": comparison,
        "unavailableReferenceBackends": [
            {
                "evidenceBackendKind": "reference-autograd",
                "reason": (
                    "No independent stock-gsplat autograd Evidence producer "
                    "is implemented in this repository."
                ),
            }
        ],
        "sourceEvidenceArtifactDigests": [
            artifact["artifactDigest"] for artifact in artifacts
        ],
        "singleViewSelectedStableGaussianIds": single_result[
            "selectedStableGaussianIds"
        ],
        "multiViewSelectedStableGaussianIds": multi_result[
            "selectedStableGaussianIds"
        ],
        "excludedViewSelectedStableGaussianIds": excluded_result[
            "selectedStableGaussianIds"
        ],
    }
    output = ROOT / "docs/ai-select/benchmarks/14d-reference-candidate-quality.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
