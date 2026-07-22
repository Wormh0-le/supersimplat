from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from selection_service_companion.binary_scene_snapshot import (
    IncompleteSnapshotUploadError,
    SnapshotUploadError,
)
from selection_service_companion.spatial_scene_working_set import (
    SpatialChunkDescriptor,
    SpatialSceneManifest,
    SpatialSceneStore,
    SpatialSupportBounds,
)


def camera() -> dict[str, object]:
    return {
        "revision": 0,
        "cameraToWorld": [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ],
        "projection": {
            "model": "pinhole",
            "fx": 10.0,
            "fy": 10.0,
            "cx": 5.0,
            "cy": 5.0,
            "width": 10,
            "height": 10,
            "near": 0.1,
            "far": 10.0,
        },
        "conventionVersion": "opencv-camera-to-world/v1",
    }


def chunk_payload(ordinal: int, stable_id: int, mean: tuple[float, float, float]) -> bytes:
    return b"".join(
        (
            struct.pack("<I", ordinal),
            struct.pack("<I", stable_id),
            struct.pack("<3f", *mean),
            struct.pack("<4f", 0.0, 0.0, 0.0, 1.0),
            struct.pack("<3f", 0.0, 0.0, 0.0),
            struct.pack("<f", 0.0),
            struct.pack("<3f", 0.0, 0.0, 0.0),
        )
    )


def descriptor(
    chunk_id: str,
    payload: bytes,
    ordinal: int,
    bounds: SpatialSupportBounds,
) -> SpatialChunkDescriptor:
    return SpatialChunkDescriptor(
        chunk_id=chunk_id,
        chunk_digest="sha256:" + hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        gaussian_count=1,
        global_ordinal_min=ordinal,
        global_ordinal_max=ordinal,
        support_bounds=bounds,
    )


def manifest(*chunks: SpatialChunkDescriptor) -> SpatialSceneManifest:
    return SpatialSceneManifest(
        scene_id="editor-splat:42",
        scene_version="sha256:" + "a" * 64,
        content_digest="sha256:" + "a" * 64,
        target_splat_id="editor-splat:42",
        total_gaussian_count=sum(chunk.gaussian_count for chunk in chunks),
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
        chunks=tuple(chunks),
    )


class SpatialSceneWorkingSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = SpatialSceneStore(Path(self.temporary_directory.name) / "runtime")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_resolves_conservative_camera_chunks_and_keeps_the_token_independent_of_residency(self) -> None:
        support_inside = SpatialSupportBounds.finite((2.4, -1.0, 4.9), (3.5, 1.0, 5.1))
        support_outside = SpatialSupportBounds.finite((20.0, -1.0, 4.0), (21.0, 1.0, 6.0))
        near_boundary = SpatialSupportBounds.finite((-1.0, -1.0, 0.05), (1.0, 1.0, 0.15))
        far_boundary = SpatialSupportBounds.finite((-1.0, -1.0, 9.95), (1.0, 1.0, 10.05))
        payload = chunk_payload(0, 7, (0.0, 0.0, 5.0))
        registered = manifest(
            descriptor("center-outside-support-inside", payload, 0, support_inside),
            descriptor("far-boundary", payload, 1, far_boundary),
            descriptor("near-boundary", payload, 2, near_boundary),
            descriptor("outside", payload, 3, support_outside),
        )
        self.store.register_manifest(registered)

        first = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )
        self.assertEqual(
            first.required_chunk_ids,
            (
                "center-outside-support-inside",
                "far-boundary",
                "near-boundary",
            ),
        )
        self.assertEqual(first.missing_chunk_ids, first.required_chunk_ids)
        self.assertIsNone(first.working_set)

        again = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )
        self.assertEqual(again.working_set_token, first.working_set_token)
        self.assertEqual(again.missing_chunk_ids, first.missing_chunk_ids)

    def test_uploads_only_missing_chunks_atomically_and_assembles_global_order_independent_of_arrival(self) -> None:
        first_payload = chunk_payload(0, 101, (0.0, 0.0, 5.0))
        second_payload = chunk_payload(1, 102, (1.0, 0.0, 5.0))
        broad_bounds = SpatialSupportBounds.finite((-10.0, -10.0, 1.0), (10.0, 10.0, 9.0))
        registered = manifest(
            descriptor("chunk-a", first_payload, 0, broad_bounds),
            descriptor("chunk-b", second_payload, 1, broad_bounds),
        )
        self.store.register_manifest(registered)
        unresolved = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )
        self.assertEqual(unresolved.missing_chunk_ids, ("chunk-a", "chunk-b"))

        admission = self.store.begin_chunk_upload(
            registered.scene_id,
            registered.scene_version,
            unresolved.missing_chunk_ids,
        )
        self.assertEqual(admission.missing_chunk_ids, ("chunk-a", "chunk-b"))
        self.store.accept_chunk(
            admission.upload_id or "", "chunk-b", second_payload,
            "sha256:" + hashlib.sha256(second_payload).hexdigest(),
        )
        with self.assertRaises(IncompleteSnapshotUploadError):
            self.store.commit_chunk_upload(admission.upload_id or "")
        self.store.accept_chunk(
            admission.upload_id or "", "chunk-a", first_payload,
            "sha256:" + hashlib.sha256(first_payload).hexdigest(),
        )
        self.assertEqual(
            self.store.accept_chunk(
                admission.upload_id or "", "chunk-a", first_payload,
                "sha256:" + hashlib.sha256(first_payload).hexdigest(),
            ),
            "alreadyStored",
        )
        self.assertEqual(
            self.store.commit_chunk_upload(admission.upload_id or "").status,
            "committed",
        )
        self.assertEqual(
            self.store.commit_chunk_upload(admission.upload_id or "").status,
            "alreadyCommitted",
        )

        resolved = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )
        self.assertEqual(resolved.missing_chunk_ids, ())
        self.assertIsNotNone(resolved.working_set)
        assert resolved.working_set is not None
        tensors = resolved.working_set.ordered_tensors()
        self.assertEqual(tensors["globalOrdinals"].tolist(), [0, 1])
        self.assertEqual(tensors["stableIds"].tolist(), [101, 102])

        import torch

        from selection_service_companion.gsplat_renderer import _locked_inputs

        inputs = _locked_inputs(
            resolved.working_set,
            {
                "worldToCamera": [
                    1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    0.0, 0.0, 0.0, 1.0,
                ],
                "intrinsics": [10.0, 0.0, 5.0, 0.0, 10.0, 5.0, 0.0, 0.0, 1.0],
            },
            torch.device("cpu"),
        )
        self.assertEqual(inputs["means"].tolist(), [[0.0, 0.0, 5.0], [1.0, 0.0, 5.0]])
        self.assertEqual(inputs["quats"].tolist(), [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])

    def test_retains_a_deterministic_full_chunk_reference_for_selective_parity(self) -> None:
        inside_payload = chunk_payload(0, 101, (0.0, 0.0, 5.0))
        outside_payload = chunk_payload(1, 102, (100.0, 0.0, 5.0))
        registered = manifest(
            descriptor(
                "chunk-inside",
                inside_payload,
                0,
                SpatialSupportBounds.finite((-3.5, -3.5, 1.5), (3.5, 3.5, 8.5)),
            ),
            descriptor(
                "chunk-outside",
                outside_payload,
                1,
                SpatialSupportBounds.finite((96.5, -3.5, 1.5), (103.5, 3.5, 8.5)),
            ),
        )
        self.store.register_manifest(registered)
        admission = self.store.begin_chunk_upload(
            registered.scene_id,
            registered.scene_version,
            ("chunk-inside", "chunk-outside"),
        )
        self.store.accept_chunk(
            admission.upload_id or "",
            "chunk-outside",
            outside_payload,
            "sha256:" + hashlib.sha256(outside_payload).hexdigest(),
        )
        self.store.accept_chunk(
            admission.upload_id or "",
            "chunk-inside",
            inside_payload,
            "sha256:" + hashlib.sha256(inside_payload).hexdigest(),
        )
        self.store.commit_chunk_upload(admission.upload_id or "")

        selective = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )
        full = self.store.full_working_set(
            registered.scene_id, registered.scene_version, camera()
        )

        self.assertEqual(selective.required_chunk_ids, ("chunk-inside",))
        self.assertIsNotNone(selective.working_set)
        self.assertNotEqual(selective.working_set_token, full.working_set_token)
        self.assertEqual(
            full.ordered_tensors()["stableIds"].tolist(), [101, 102]
        )

    def test_falls_back_to_all_chunks_when_one_support_bound_cannot_prove_culling(self) -> None:
        first_payload = chunk_payload(0, 101, (100.0, 0.0, 5.0))
        second_payload = chunk_payload(1, 102, (0.0, 0.0, 5.0))
        registered = manifest(
            descriptor(
                "otherwise-outside",
                first_payload,
                0,
                SpatialSupportBounds.finite((99.0, -1.0, 4.0), (101.0, 1.0, 6.0)),
            ),
            descriptor("unbounded", second_payload, 1, SpatialSupportBounds.unbounded()),
        )
        self.store.register_manifest(registered)

        resolved = self.store.resolve_working_set(
            registered.scene_id, registered.scene_version, camera()
        )

        self.assertTrue(resolved.fallback_all_chunks)
        self.assertEqual(
            resolved.required_chunk_ids, ("otherwise-outside", "unbounded")
        )
        self.assertEqual(resolved.missing_chunk_ids, resolved.required_chunk_ids)

    def test_rejects_wrong_scene_corrupt_bytes_and_releases_staging(self) -> None:
        payload = chunk_payload(0, 7, (0.0, 0.0, 5.0))
        bounds = SpatialSupportBounds.finite((-10.0, -10.0, 1.0), (10.0, 10.0, 9.0))
        registered = manifest(descriptor("chunk-a", payload, 0, bounds))
        self.store.register_manifest(registered)
        with self.assertRaises(SnapshotUploadError):
            self.store.begin_chunk_upload("wrong-scene", registered.scene_version, ("chunk-a",))

        admission = self.store.begin_chunk_upload(
            registered.scene_id, registered.scene_version, ("chunk-a",)
        )
        with self.assertRaises(SnapshotUploadError):
            self.store.accept_chunk(
                admission.upload_id or "", "chunk-a", b"corrupt", "sha256:" + "0" * 64
            )
        self.store.abort_chunk_upload(admission.upload_id or "")
        self.assertEqual(self.store.cleanup_expired(), 0)

    def test_rejects_chunk_ordinal_metadata_outside_the_complete_scene(self) -> None:
        payload = chunk_payload(0, 7, (0.0, 0.0, 5.0))
        valid = manifest(
            descriptor(
                "chunk-a",
                payload,
                0,
                SpatialSupportBounds.finite((-1.0, -1.0, 4.0), (1.0, 1.0, 6.0)),
            )
        )
        invalid = replace(
            valid,
            chunks=(replace(valid.chunks[0], global_ordinal_max=valid.total_gaussian_count),),
        )

        with self.assertRaises(SnapshotUploadError):
            self.store.register_manifest(invalid)


if __name__ == "__main__":
    unittest.main()
