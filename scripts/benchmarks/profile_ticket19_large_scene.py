#!/usr/bin/env python3
"""Locked-GPU Ticket 19 large scene, working-set, tensor, RGB, and PNG profile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter

from selection_service_companion.anchor_timing import AnchorServerTiming
from selection_service_companion.gsplat_renderer import (
    GsplatContributorRenderer,
    LockedGsplatBackend,
)
from selection_service_companion.spatial_scene_working_set import (
    SpatialChunkDescriptor,
    SpatialSceneManifest,
    SpatialSceneStore,
    SpatialSupportBounds,
)


GAUSSIAN_COUNT = 200_000
ROWS_PER_CHUNK = 50_000
WIDTH = 128
HEIGHT = 128


def rss_bytes() -> int:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("Linux VmRSS is unavailable")


def measure(name: str, run: object, phases: list[dict[str, object]]) -> object:
    before = rss_bytes()
    started = perf_counter()
    result = run()  # type: ignore[operator]
    phases.append(
        {
            "name": name,
            "milliseconds": (perf_counter() - started) * 1000.0,
            "rssBeforeBytes": before,
            "rssAfterBytes": rss_bytes(),
        }
    )
    return result


def payloads() -> tuple[dict[str, bytes], tuple[SpatialChunkDescriptor, ...]]:
    import torch

    payload_by_id: dict[str, bytes] = {}
    descriptors: list[SpatialChunkDescriptor] = []
    side = int(GAUSSIAN_COUNT**0.5) + 1
    for chunk_index, start in enumerate(range(0, GAUSSIAN_COUNT, ROWS_PER_CHUNK)):
        count = min(ROWS_PER_CHUNK, GAUSSIAN_COUNT - start)
        ordinal = torch.arange(start, start + count, dtype=torch.int32)
        local = torch.arange(start, start + count, dtype=torch.float32)
        means = torch.stack(
            (
                (local.remainder(side) - side / 2) * 0.01,
                (torch.floor(local / side) - side / 2) * 0.01,
                torch.full((count,), 20.0),
            ),
            dim=1,
        )
        rotations = torch.zeros((count, 4), dtype=torch.float32)
        rotations[:, 3] = 1.0
        log_scales = torch.full((count, 3), -3.0, dtype=torch.float32)
        opacity = torch.full((count,), 1.0, dtype=torch.float32)
        dc = torch.zeros((count, 3), dtype=torch.float32)
        dc[:, 0] = 0.4
        payload = b"".join(
            tensor.contiguous().numpy().tobytes()
            for tensor in (
                ordinal,
                ordinal,
                means,
                rotations,
                log_scales,
                opacity,
                dc,
            )
        )
        chunk_id = f"chunk-{chunk_index:04d}"
        digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        payload_by_id[chunk_id] = payload
        descriptors.append(
            SpatialChunkDescriptor(
                chunk_id=chunk_id,
                chunk_digest=digest,
                byte_length=len(payload),
                gaussian_count=count,
                global_ordinal_min=start,
                global_ordinal_max=start + count - 1,
                support_bounds=SpatialSupportBounds.unbounded(),
            )
        )
    return payload_by_id, tuple(descriptors)


def manifest(chunks: tuple[SpatialChunkDescriptor, ...]) -> SpatialSceneManifest:
    digest = "sha256:" + "9" * 64
    return SpatialSceneManifest(
        scene_id="editor-splat:ticket19-large-profile",
        scene_version=digest,
        content_digest=digest,
        target_splat_id="editor-splat:ticket19-large-profile",
        total_gaussian_count=GAUSSIAN_COUNT,
        coordinate_convention="right-handed world coordinates; quaternion xyzw",
        stable_id_schema="uint32",
        attribute_schema="mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
        appearance_policy="effective-editor-dc-sh-bands-0",
        render_configuration={
            "version": "supersplat-effective-rgb-v1",
            "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
            "alphaMode": "opaque-background",
            "shBands": 0,
            "rasterizer": "playcanvas-gsplat-classic",
        },
        sh_float_count_per_gaussian=0,
        chunks=chunks,
    )


def camera() -> tuple[dict[str, object], dict[str, object]]:
    binding = {
        "revision": 0,
        "cameraToWorld": [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ],
        "projection": {
            "model": "pinhole",
            "fx": 100.0,
            "fy": 100.0,
            "cx": WIDTH / 2,
            "cy": HEIGHT / 2,
            "width": WIDTH,
            "height": HEIGHT,
            "near": 0.1,
            "far": 100.0,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }
    renderer = {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": binding["cameraToWorld"],
        "intrinsics": [
            100.0, 0.0, WIDTH / 2,
            0.0, 100.0, HEIGHT / 2,
            0.0, 0.0, 1.0,
        ],
        "nearPlane": 0.1,
        "farPlane": 100.0,
    }
    return binding, renderer


def main() -> None:
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("locked CUDA GPU is unavailable")
    phases: list[dict[str, object]] = []
    payload_by_id, descriptors = measure("scene-creation", payloads, phases)  # type: ignore[misc]
    scene_manifest = manifest(descriptors)
    binding, renderer_camera = camera()
    with tempfile.TemporaryDirectory() as directory:
        store = SpatialSceneStore(Path(directory) / "runtime")
        measure(
            "manifest-registration",
            lambda: store.register_manifest(scene_manifest),
            phases,
        )

        def transfer() -> None:
            admission = store.begin_chunk_upload(
                scene_manifest.scene_id,
                scene_manifest.scene_version,
                tuple(payload_by_id),
            )
            for chunk_id, payload in payload_by_id.items():
                store.accept_chunk(
                    admission.upload_id or "",
                    chunk_id,
                    payload,
                    f"sha256:{hashlib.sha256(payload).hexdigest()}",
                )
            store.commit_chunk_upload(admission.upload_id or "")

        measure("chunk-transfer-validation", transfer, phases)
        resolution = measure(
            "working-set-resolution",
            lambda: store.resolve_working_set(
                scene_manifest.scene_id, scene_manifest.scene_version, binding
            ),
            phases,
        )
        assert resolution.working_set is not None  # type: ignore[union-attr]
        backend = LockedGsplatBackend()
        renderer = GsplatContributorRenderer(backend=backend)

        def render(label: str) -> dict[str, object]:
            timing = AnchorServerTiming()
            artifact = renderer.render_anchor(
                scene_snapshot=resolution.working_set,  # type: ignore[union-attr]
                view_id="anchor-view",
                camera=renderer_camera,
                width=WIDTH,
                height=HEIGHT,
                timing=timing,
                include_reference_contributor=False,
            )
            return {
                "label": label,
                "rgbDigest": artifact.rgb_digest,
                "pngBytes": len(artifact.image_png),
                "serverTiming": timing.header_value(),
                "peakVramBytes": renderer.last_peak_vram_bytes,
                "tensorCache": dict(backend.scene_tensor_cache_stats()),
            }

        cold = measure("cold-gsplat-rgb-png", lambda: render("cold"), phases)
        warm = measure("warm-gsplat-rgb-png", lambda: render("warm"), phases)

    print(
        json.dumps(
            {
                "schemaVersion": 1,
                "gpu": torch.cuda.get_device_name(0),
                "gaussianCount": GAUSSIAN_COUNT,
                "chunkCount": len(descriptors),
                "payloadBytes": sum(len(value) for value in payload_by_id.values()),
                "cold": cold,
                "warm": warm,
                "phases": phases,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
