from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    binary_scene_snapshot_content_digest,
    BinarySceneSnapshotManifest,
    BinarySceneSnapshotUploadStore,
    ImmutableSnapshotConflict,
    IncompleteSnapshotUploadError,
    UnknownSnapshotUpload,
)


class BinarySceneSnapshotRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.payload = struct.pack(
            "<I" + "f" * 14,
            7,
            1.0, 2.0, 3.0,
            0.0, 0.0, 0.0, 1.0,
            0.0, 0.0, 0.0,
            0.0,
            0.0, 0.0, 0.0,
        )
        self.store = BinarySceneSnapshotUploadStore(self.directory / "runtime")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def manifest(self, *, scene_id: str = "editor-splat:42") -> BinarySceneSnapshotManifest:
        fields = [
            {"name": "stableIds", "scalarType": "uint32le", "componentCount": 1, "byteOffset": 0, "byteLength": 4},
            {"name": "means", "scalarType": "float32le", "componentCount": 3, "byteOffset": 4, "byteLength": 12},
            {"name": "rotationsXyzw", "scalarType": "float32le", "componentCount": 4, "byteOffset": 16, "byteLength": 16},
            {"name": "logScales", "scalarType": "float32le", "componentCount": 3, "byteOffset": 32, "byteLength": 12},
            {"name": "logitOpacities", "scalarType": "float32le", "componentCount": 1, "byteOffset": 44, "byteLength": 4},
            {"name": "dc", "scalarType": "float32le", "componentCount": 3, "byteOffset": 48, "byteLength": 12},
            {"name": "sh", "scalarType": "float32le", "componentCount": 0, "byteOffset": 60, "byteLength": 0},
        ]
        content = {
            "protocolVersion": "1",
            "gaussianCount": 1,
            "coordinateConvention": "right-handed world coordinates; quaternion xyzw",
            "stableIdSchema": "uint32",
            "attributeSchema": "mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x0",
            "appearancePolicy": "effective-editor-dc-sh-bands-0",
            "renderConfiguration": {
                "version": "supersplat-effective-rgb-v1",
                "backgroundRgba": [0.0, 0.0, 0.0, 1.0],
                "alphaMode": "opaque-background",
                "shBands": 0,
                "rasterizer": "playcanvas-gsplat-classic",
            },
            "shFloatCountPerGaussian": 0,
            "payloadByteLength": len(self.payload),
            "fields": fields,
        }
        chunk_byte_length = 32
        chunks = tuple(
            BinarySceneSnapshotChunk(
                index=index,
                offset=index * chunk_byte_length,
                byte_length=len(self.payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]),
                digest="sha256:" + hashlib.sha256(
                    self.payload[index * chunk_byte_length:(index + 1) * chunk_byte_length]
                ).hexdigest(),
            )
            for index in range((len(self.payload) + chunk_byte_length - 1) // chunk_byte_length)
        )
        content_digest = binary_scene_snapshot_content_digest(
            content,
            (self.payload[chunk.offset:chunk.offset + chunk.byte_length] for chunk in chunks),
        )
        self.assertEqual(
            content_digest,
            "sha256:d2e86ef6efa8979eed111a6d3ecea9419e09bb780b69ab769f279dd768be925e",
        )
        return BinarySceneSnapshotManifest(
            scene_id=scene_id,
            scene_version=content_digest,
            content_digest=content_digest,
            content=content,
            chunk_byte_length=chunk_byte_length,
            chunks=chunks,
        )

    def test_stages_verified_chunks_and_publishes_only_after_atomic_commit(self) -> None:
        manifest = self.manifest()
        first = self.store.begin(manifest)
        retry = self.store.begin(manifest)

        self.assertEqual(first.status, "staged")
        self.assertEqual(retry.upload_id, first.upload_id)
        self.assertEqual(first.missing_chunk_indices, tuple(range(len(manifest.chunks))))
        with self.assertRaises(IncompleteSnapshotUploadError):
            self.store.commit(first.upload_id or "")

        for chunk in manifest.chunks:
            payload = self.payload[chunk.offset:chunk.offset + chunk.byte_length]
            self.store.accept_chunk(first.upload_id or "", chunk.index, payload, chunk.digest)
            self.store.accept_chunk(first.upload_id or "", chunk.index, payload, chunk.digest)

        snapshot = self.store.commit(first.upload_id or "")
        self.assertIsInstance(snapshot.payload, memoryview)
        self.assertEqual(snapshot.content_digest, manifest.content_digest)
        replay = self.store.commit_result(first.upload_id or "")
        self.assertEqual(replay.status, "alreadyCommitted")
        self.assertIs(replay.snapshot, snapshot)
        self.assertEqual(
            self.store.begin(manifest).status,
            "alreadyCommitted",
        )

    def test_content_digest_ignores_the_transport_chunk_boundaries(self) -> None:
        manifest = self.manifest()
        by_small_chunks = binary_scene_snapshot_content_digest(
            manifest.content,
            (self.payload[offset:offset + 7] for offset in range(0, len(self.payload), 7)),
        )

        self.assertEqual(by_small_chunks, manifest.content_digest)

    def test_rejects_an_immutable_conflict_and_cleans_incomplete_uploads(self) -> None:
        manifest = self.manifest()
        admission = self.store.begin(manifest)
        self.assertIsNotNone(admission.upload_id)
        self.assertEqual(self.store.cleanup_expired(), 0)

        conflicting = BinarySceneSnapshotManifest(
            scene_id=manifest.scene_id,
            scene_version=manifest.scene_version,
            content_digest=manifest.content_digest,
            content={
                **manifest.content,
                "renderConfiguration": {
                    **manifest.content["renderConfiguration"],
                    "backgroundRgba": [0.25, 0.0, 0.0, 1.0],
                },
            },
            chunk_byte_length=manifest.chunk_byte_length,
            chunks=manifest.chunks,
        )
        with self.assertRaises(ImmutableSnapshotConflict):
            self.store.begin(conflicting)

        self.store.abort(admission.upload_id or "")
        self.assertEqual(self.store.cleanup_expired(), 0)

    def test_maps_packed_planes_directly_to_vectorized_renderer_inputs(self) -> None:
        import torch

        from selection_service_companion.gsplat_renderer import _locked_inputs

        manifest = self.manifest()
        admission = self.store.begin(manifest)
        for chunk in manifest.chunks:
            payload = self.payload[chunk.offset:chunk.offset + chunk.byte_length]
            self.store.accept_chunk(
                admission.upload_id or "", chunk.index, payload, chunk.digest
            )
        snapshot = self.store.commit(admission.upload_id or "")

        inputs = _locked_inputs(
            snapshot,
            {
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
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ],
                "intrinsics": [
                    100.0,
                    0.0,
                    0.5,
                    0.0,
                    100.0,
                    0.5,
                    0.0,
                    0.0,
                    1.0,
                ],
            },
            torch.device("cpu"),
        )

        self.assertEqual(inputs["means"].tolist(), [[1.0, 2.0, 3.0]])
        self.assertEqual(inputs["quats"].tolist(), [[1.0, 0.0, 0.0, 0.0]])
        self.assertEqual(inputs["colors"].shape, (1, 1, 3))

    def test_validates_mmap_planes_without_scalar_struct_iteration(self) -> None:
        import selection_service_companion.binary_scene_snapshot as binary_snapshot

        manifest = self.manifest()
        admission = self.store.begin(manifest)
        for chunk in manifest.chunks:
            payload = self.payload[chunk.offset:chunk.offset + chunk.byte_length]
            self.store.accept_chunk(
                admission.upload_id or "", chunk.index, payload, chunk.digest
            )

        with mock.patch.object(
            binary_snapshot.struct,
            "iter_unpack",
            side_effect=AssertionError("typed validation must not scalar-iterate payload"),
        ):
            snapshot = self.store.commit(admission.upload_id or "")

        self.assertEqual(snapshot.gaussian_count, 1)

    def test_expires_an_incomplete_staging_upload_without_publishing_it(self) -> None:
        store = BinarySceneSnapshotUploadStore(
            self.directory / "expired-runtime", staging_ttl_seconds=-1.0
        )
        admission = store.begin(self.manifest())

        self.assertEqual(store.cleanup_expired(), 1)
        with self.assertRaises(UnknownSnapshotUpload):
            store.commit(admission.upload_id or "")
        self.assertIsNone(
            store.committed_snapshot("editor-splat:42", self.manifest().scene_version)
        )
