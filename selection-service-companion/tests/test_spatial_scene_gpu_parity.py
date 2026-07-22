from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct
import tempfile
import unittest

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


def _locked_gpu_available() -> bool:
    try:
        import gsplat  # noqa: F401
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _payload(
    *,
    ordinal: int,
    stable_id: int,
    mean: tuple[float, float, float],
    sh_float_count: int,
    transformed: bool,
) -> bytes:
    # `transformed` represents already-effective 02A values: a non-identity
    # world/palette transform, anisotropic rotation/scale, and color grade.
    rotation = (
        0.0,
        0.0,
        math.sin(math.pi / 8.0) if transformed else 0.0,
        math.cos(math.pi / 8.0) if transformed else 1.0,
    )
    log_scale = (
        math.log(0.8) if transformed else math.log(0.5),
        math.log(0.2) if transformed else math.log(0.5),
        math.log(0.4) if transformed else math.log(0.5),
    )
    dc = (0.4, -0.1, 0.2) if transformed else (0.1, 0.2, 0.3)
    sh = tuple((index + 1) * 0.001 for index in range(sh_float_count))
    return b"".join(
        (
            struct.pack("<I", ordinal),
            struct.pack("<I", stable_id),
            struct.pack("<3f", *mean),
            struct.pack("<4f", *rotation),
            struct.pack("<3f", *log_scale),
            struct.pack("<f", 3.0),
            struct.pack("<3f", *dc),
            struct.pack(f"<{sh_float_count}f", *sh) if sh_float_count else b"",
        )
    )


def _descriptor(
    chunk_id: str,
    payload: bytes,
    ordinal: int,
    bounds: SpatialSupportBounds,
) -> SpatialChunkDescriptor:
    return SpatialChunkDescriptor(
        chunk_id=chunk_id,
        chunk_digest=_digest(payload),
        byte_length=len(payload),
        gaussian_count=1,
        global_ordinal_min=ordinal,
        global_ordinal_max=ordinal,
        support_bounds=bounds,
    )


def _camera() -> tuple[dict[str, object], dict[str, object]]:
    binding: dict[str, object] = {
        "revision": 0,
        "cameraToWorld": [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ],
        "projection": {
            "model": "pinhole",
            "fx": 50.0,
            "fy": 50.0,
            "cx": 32.0,
            "cy": 32.0,
            "width": 64,
            "height": 64,
            "near": 0.1,
            "far": 100.0,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }
    renderer: dict[str, object] = {
        "model": "pinhole",
        "convention": "opencv-world-to-camera",
        "worldToCamera": [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ],
        "intrinsics": [50.0, 0.0, 32.0, 0.0, 50.0, 32.0, 0.0, 0.0, 1.0],
        "nearPlane": 0.1,
        "farPlane": 100.0,
    }
    return binding, renderer


def _global_contributors(raster: object, working_set: object) -> tuple[object, ...]:
    stable_ids = working_set.ordered_tensors()["stableIds"].tolist()
    rows: list[object] = []
    for image_row in raster.contributor_ids:
        pixels: list[object] = []
        for ids in image_row:
            pixels.append(tuple(-1 if index < 0 else stable_ids[index] for index in ids))
        rows.append(tuple(pixels))
    return tuple(rows)


@unittest.skipUnless(_locked_gpu_available(), "locked CUDA gsplat runtime is unavailable")
class SpatialSceneLockedGpuParityTests(unittest.TestCase):
    def test_selective_and_full_typed_paths_match_for_every_supported_sh_degree(self) -> None:
        binding, renderer_camera = _camera()
        backend = LockedGsplatBackend()
        contributor_renderer = GsplatContributorRenderer(backend=backend)
        for sh_degree, sh_float_count in ((0, 0), (1, 9), (2, 24), (3, 45)):
            with self.subTest(sh_degree=sh_degree):
                inside = _payload(
                    ordinal=0,
                    stable_id=101,
                    mean=(0.5, -0.25, 5.0),
                    sh_float_count=sh_float_count,
                    transformed=True,
                )
                outside = _payload(
                    ordinal=1,
                    stable_id=305,
                    mean=(100.0, 0.0, 5.0),
                    sh_float_count=sh_float_count,
                    transformed=False,
                )
                # Stable ID 999 represents a deleted Gaussian. It is absent
                # from both effective chunks and therefore cannot reappear in
                # either tensor path or contributor output.
                manifest = SpatialSceneManifest(
                    scene_id=f"editor-splat:parity-{sh_degree}",
                    scene_version="sha256:" + "a" * 63 + str(sh_degree),
                    content_digest="sha256:" + "a" * 63 + str(sh_degree),
                    target_splat_id=f"editor-splat:parity-{sh_degree}",
                    total_gaussian_count=2,
                    coordinate_convention="right-handed world coordinates; quaternion xyzw",
                    stable_id_schema="uint32",
                    attribute_schema=(
                        "mean:f32x3;rotation:f32x4;logScale:f32x3;"
                        f"logitOpacity:f32;dc:f32x3;sh:f32x{sh_float_count}"
                    ),
                    appearance_policy=f"effective-editor-dc-sh-bands-{sh_degree}",
                    render_configuration={
                        "version": "supersplat-effective-rgb-v1",
                        "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
                        "alphaMode": "opaque-background",
                        "shBands": sh_degree,
                        "rasterizer": "playcanvas-gsplat-classic",
                    },
                    sh_float_count_per_gaussian=sh_float_count,
                    chunks=(
                        _descriptor(
                            "chunk-inside",
                            inside,
                            0,
                            SpatialSupportBounds.finite((-4.0, -4.0, 1.0), (4.0, 4.0, 9.0)),
                        ),
                        _descriptor(
                            "chunk-outside",
                            outside,
                            1,
                            SpatialSupportBounds.finite((96.0, -4.0, 1.0), (104.0, 4.0, 9.0)),
                        ),
                    ),
                )
                with tempfile.TemporaryDirectory() as directory:
                    store = SpatialSceneStore(Path(directory) / "runtime")
                    store.register_manifest(manifest)
                    admission = store.begin_chunk_upload(
                        manifest.scene_id,
                        manifest.scene_version,
                        ("chunk-inside", "chunk-outside"),
                    )
                    self.assertIsNotNone(admission.upload_id)
                    # Reverse arrival order must not affect global tensor order.
                    store.accept_chunk(
                        admission.upload_id or "", "chunk-outside", outside, _digest(outside)
                    )
                    store.accept_chunk(
                        admission.upload_id or "", "chunk-inside", inside, _digest(inside)
                    )
                    store.commit_chunk_upload(admission.upload_id or "")

                    selective_resolution = store.resolve_working_set(
                        manifest.scene_id, manifest.scene_version, binding
                    )
                    self.assertEqual(selective_resolution.required_chunk_ids, ("chunk-inside",))
                    self.assertIsNotNone(selective_resolution.working_set)
                    selective_working_set = selective_resolution.working_set
                    assert selective_working_set is not None
                    full_working_set = store.full_working_set(
                        manifest.scene_id, manifest.scene_version, binding
                    )

                    selective = backend.rasterize(
                        snapshot=selective_working_set,
                        camera=renderer_camera,
                        width=64,
                        height=64,
                    )
                    full = backend.rasterize(
                        snapshot=full_working_set,
                        camera=renderer_camera,
                        width=64,
                        height=64,
                    )

                self.assertEqual(selective.service_rgb_bytes, full.service_rgb_bytes)
                self.assertEqual(selective.service_rgb_digest, full.service_rgb_digest)
                self.assertEqual(selective.alpha, full.alpha)
                self.assertEqual(
                    _global_contributors(selective, selective_working_set),
                    _global_contributors(full, full_working_set),
                )
                self.assertEqual(selective.contributor_weights, full.contributor_weights)
                self.assertNotIn(999, full_working_set.ordered_tensors()["stableIds"].tolist())
                # This is the production contributor publication seam: it
                # consumes working-set tensor IDs and proves their global
                # Stable-ID remapping before it hashes the artifact.
                selective_artifact = contributor_renderer.render_anchor(
                    scene_snapshot=selective_working_set,
                    view_id="anchor-view",
                    camera=renderer_camera,
                    width=64,
                    height=64,
                )
                full_artifact = contributor_renderer.render_anchor(
                    scene_snapshot=full_working_set,
                    view_id="anchor-view",
                    camera=renderer_camera,
                    width=64,
                    height=64,
                )
                self.assertEqual(selective_artifact.rgb_digest, full_artifact.rgb_digest)
                self.assertEqual(
                    selective_artifact.contributor_digest,
                    full_artifact.contributor_digest,
                )


if __name__ == "__main__":
    unittest.main()
