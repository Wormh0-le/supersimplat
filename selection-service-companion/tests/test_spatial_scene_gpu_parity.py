from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotUploadStore,
    parse_binary_scene_snapshot_manifest,
)
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


def _scope_identity(target_splat_id: str, sources: list[dict[str, object]]) -> str:
    return _digest(
        json.dumps(
            {
                "policyId": "visible-editor-splats-conservative/v1",
                "targetSplatId": target_splat_id,
                "sources": sources,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )


def _payload(
    *,
    ordinal: int,
    stable_id: int,
    mean: tuple[float, float, float],
    sh_float_count: int,
    transformed: bool,
    dc_override: tuple[float, float, float] | None = None,
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
    dc = dc_override or (
        (0.4, -0.1, 0.2) if transformed else (0.1, 0.2, 0.3)
    )
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
    def test_production_effective_snapshot_matches_locked_rgb_and_alpha(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        exported = subprocess.run(
            [
                "node",
                str(
                    repository
                    / "scripts/benchmarks/export_ticket19_effective_snapshot_fixture.cjs"
                ),
            ],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        fixture = json.loads(exported.stdout)

        def committed_snapshot(
            record: dict[str, object], directory: Path
        ):
            manifest = parse_binary_scene_snapshot_manifest(record["manifest"])
            payload = base64.b64decode(str(record["payloadBase64"]))
            store = BinarySceneSnapshotUploadStore(directory)
            admission = store.begin(manifest)
            self.assertIsNotNone(admission.upload_id)
            upload_id = admission.upload_id or ""
            for chunk in manifest.chunks:
                body = payload[chunk.offset:chunk.offset + chunk.byte_length]
                store.accept_chunk(upload_id, chunk.index, body, chunk.digest)
            return store, store.commit(upload_id)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _, production = committed_snapshot(
                fixture["production"], root / "production"
            )
            _, expected = committed_snapshot(
                fixture["expected"], root / "expected"
            )
            self.assertEqual(
                list(production.stable_ids()), fixture["expectedStableIds"]
            )
            self.assertEqual(
                list(struct.unpack("<9f", production.field("means"))),
                fixture["expectedMeans"],
            )
            _, renderer_camera = _camera()
            backend = LockedGsplatBackend()
            renderer = GsplatContributorRenderer(backend=backend)
            production_artifact = renderer.render_anchor(
                scene_snapshot=production,
                view_id="anchor-view",
                camera=renderer_camera,
                width=64,
                height=64,
            )
            expected_artifact = renderer.render_anchor(
                scene_snapshot=expected,
                view_id="anchor-view",
                camera=renderer_camera,
                width=64,
                height=64,
            )
            self.assertEqual(
                production_artifact.rgb_digest, expected_artifact.rgb_digest
            )
            self.assertEqual(
                production_artifact.alpha_coverage,
                expected_artifact.alpha_coverage,
            )
            self.assertGreater(production_artifact.alpha_coverage or 0.0, 0.0)
            production.close()
            expected.close()

    def test_visible_non_target_occluder_is_required_for_authoritative_rgb(self) -> None:
        binding, renderer_camera = _camera()
        target = _payload(
            ordinal=0,
            stable_id=11,
            mean=(0.0, 0.0, 5.0),
            sh_float_count=0,
            transformed=False,
            dc_override=(1.5, -1.0, -1.0),
        )
        occluder = _payload(
            ordinal=1,
            stable_id=12,
            mean=(0.0, 0.0, 4.0),
            sh_float_count=0,
            transformed=False,
            dc_override=(-1.0, -1.0, 1.5),
        )
        broad = SpatialSupportBounds.finite((-4.0, -4.0, 1.0), (4.0, 4.0, 9.0))
        common = {
            "coordinate_convention": "right-handed world coordinates; quaternion xyzw",
            "stable_id_schema": "uint32",
            "attribute_schema": "mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
            "appearance_policy": "effective-editor-dc-sh-bands-0",
            "render_configuration": {
                "version": "supersplat-effective-rgb-v1",
                "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
                "alphaMode": "opaque-background",
                "shBands": 0,
                "rasterizer": "playcanvas-gsplat-classic",
            },
            "sh_float_count_per_gaussian": 0,
        }
        scope_manifest = SpatialSceneManifest(
            scene_id="editor-splat:scope-target",
            scene_version="sha256:" + "c" * 64,
            content_digest="sha256:" + "c" * 64,
            target_splat_id="editor-splat:scope-target",
            total_gaussian_count=2,
            chunks=(
                _descriptor("chunk-target", target, 0, broad),
                _descriptor("chunk-visible-occluder", occluder, 1, broad),
            ),
            authoritative_render_scope={
                "policyId": "visible-editor-splats-conservative/v1",
                "targetSplatId": "editor-splat:scope-target",
                "identityDigest": _scope_identity(
                    "editor-splat:scope-target",
                    [
                        {
                            "splatId": "editor-splat:scope-target",
                            "sourceContentDigest": "sha256:" + "e" * 64,
                            "gaussianCount": 1,
                        },
                        {
                            "splatId": "editor-splat:visible-occluder",
                            "sourceContentDigest": "sha256:" + "f" * 64,
                            "gaussianCount": 1,
                        },
                    ],
                ),
                "entries": [
                    {
                        "splatId": "editor-splat:scope-target",
                        "role": "target",
                        "sourceContentDigest": "sha256:" + "e" * 64,
                        "rowOffset": 0,
                        "rowCount": 1,
                        "renderIdStart": 11,
                    },
                    {
                        "splatId": "editor-splat:visible-occluder",
                        "role": "occluder",
                        "sourceContentDigest": "sha256:" + "f" * 64,
                        "rowOffset": 1,
                        "rowCount": 1,
                        "renderIdStart": 12,
                    },
                ],
            },
            **common,
        )
        target_manifest = SpatialSceneManifest(
            scene_id="editor-splat:target-only",
            scene_version="sha256:" + "1" * 64,
            content_digest="sha256:" + "1" * 64,
            target_splat_id="editor-splat:target-only",
            total_gaussian_count=1,
            chunks=(_descriptor("chunk-target", target, 0, broad),),
            **common,
        )

        def resident_working_set(
            root: Path, manifest: SpatialSceneManifest, payloads: dict[str, bytes]
        ) -> tuple[SpatialSceneStore, object]:
            store = SpatialSceneStore(root)
            store.register_manifest(manifest)
            admission = store.begin_chunk_upload(
                manifest.scene_id,
                manifest.scene_version,
                tuple(payloads),
            )
            for chunk_id, payload in payloads.items():
                store.accept_chunk(
                    admission.upload_id or "", chunk_id, payload, _digest(payload)
                )
            store.commit_chunk_upload(admission.upload_id or "")
            resolution = store.resolve_working_set(
                manifest.scene_id, manifest.scene_version, binding
            )
            self.assertEqual(resolution.missing_chunk_ids, ())
            self.assertIsNotNone(resolution.working_set)
            return store, resolution.working_set

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope_store, scope_working_set = resident_working_set(
                root / "scope",
                scope_manifest,
                {"chunk-target": target, "chunk-visible-occluder": occluder},
            )
            target_store, target_working_set = resident_working_set(
                root / "target", target_manifest, {"chunk-target": target}
            )
            backend = LockedGsplatBackend()
            authoritative = backend.rasterize(
                snapshot=scope_working_set,
                camera=renderer_camera,
                width=64,
                height=64,
            )
            full = backend.rasterize(
                snapshot=scope_store.full_working_set(
                    scope_manifest.scene_id, scope_manifest.scene_version, binding
                ),
                camera=renderer_camera,
                width=64,
                height=64,
            )
            target_only = backend.rasterize(
                snapshot=target_working_set,
                camera=renderer_camera,
                width=64,
                height=64,
            )
            self.assertEqual(authoritative.service_rgb_bytes, full.service_rgb_bytes)
            self.assertNotEqual(
                authoritative.service_rgb_bytes, target_only.service_rgb_bytes
            )
            self.assertEqual(
                scope_working_set.manifest.authoritative_render_scope["entries"][1]["role"],
                "occluder",
            )
            del target_store

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
                    include_reference_contributor=True,
                )
                full_artifact = contributor_renderer.render_anchor(
                    scene_snapshot=full_working_set,
                    view_id="anchor-view",
                    camera=renderer_camera,
                    width=64,
                    height=64,
                    include_reference_contributor=True,
                )
                self.assertEqual(selective_artifact.rgb_digest, full_artifact.rgb_digest)
                self.assertEqual(
                    selective_artifact.contributor_digest,
                    full_artifact.contributor_digest,
                )
        stats = backend.scene_tensor_cache_stats()
        self.assertGreaterEqual(stats["hits"], 8)
        self.assertEqual(stats["misses"], 8)


if __name__ == "__main__":
    unittest.main()
