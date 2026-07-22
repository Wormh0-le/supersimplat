from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from selection_service_companion.binary_scene_snapshot import (
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    BinarySceneSnapshotUploadStore,
    ImmutableSnapshotConflict,
    IncompleteSnapshotUploadError,
)


class BinarySceneSnapshotRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.payload = bytes(range(32))
        self.store = BinarySceneSnapshotUploadStore(self.directory / "runtime")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def manifest(self, *, scene_id: str = "editor-splat:42") -> BinarySceneSnapshotManifest:
        chunks = tuple(
            BinarySceneSnapshotChunk(
                index=index,
                offset=index * 16,
                byte_length=len(self.payload[index * 16:(index + 1) * 16]),
                digest="sha256:" + hashlib.sha256(
                    self.payload[index * 16:(index + 1) * 16]
                ).hexdigest(),
            )
            for index in range(2)
        )
        return BinarySceneSnapshotManifest(
            scene_id=scene_id,
            scene_version="sha256:logical-content",
            content_digest="sha256:logical-content",
            content={
                "format": "supersplat-packed-scene-snapshot",
                "formatVersion": 1,
                "payloadByteLength": len(self.payload),
            },
            chunk_byte_length=16,
            chunks=chunks,
        )

    def test_stages_verified_chunks_and_publishes_only_after_atomic_commit(self) -> None:
        manifest = self.manifest()
        first = self.store.begin(manifest)
        retry = self.store.begin(manifest)

        self.assertEqual(first.status, "staged")
        self.assertEqual(retry.upload_id, first.upload_id)
        self.assertEqual(first.missing_chunk_indices, (0, 1))
        with self.assertRaises(IncompleteSnapshotUploadError):
            self.store.commit(first.upload_id or "")

        for chunk in manifest.chunks:
            payload = self.payload[chunk.offset:chunk.offset + chunk.byte_length]
            self.store.accept_chunk(first.upload_id or "", chunk.index, payload, chunk.digest)
            self.store.accept_chunk(first.upload_id or "", chunk.index, payload, chunk.digest)

        snapshot = self.store.commit(first.upload_id or "")
        self.assertIsInstance(snapshot.payload, memoryview)
        self.assertEqual(snapshot.content_digest, manifest.content_digest)
        self.assertEqual(
            self.store.begin(manifest).status,
            "alreadyCommitted",
        )

    def test_rejects_an_immutable_conflict_and_cleans_incomplete_uploads(self) -> None:
        manifest = self.manifest()
        admission = self.store.begin(manifest)
        self.assertIsNotNone(admission.upload_id)
        self.assertEqual(self.store.cleanup_expired(), 0)

        conflicting = BinarySceneSnapshotManifest(
            scene_id=manifest.scene_id,
            scene_version=manifest.scene_version,
            content_digest=manifest.content_digest,
            content={**manifest.content, "payloadByteLength": 31},
            chunk_byte_length=manifest.chunk_byte_length,
            chunks=manifest.chunks,
        )
        with self.assertRaises(ImmutableSnapshotConflict):
            self.store.begin(conflicting)

        self.store.abort(admission.upload_id or "")
        self.assertEqual(self.store.cleanup_expired(), 0)
