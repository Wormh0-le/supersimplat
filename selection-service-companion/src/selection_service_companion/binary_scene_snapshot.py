"""Public seams for Binary SceneSnapshot Registration v1.

The staged upload implementation intentionally follows the approved protocol
document and red contract tests in the next Ticket 02A slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


BINARY_SCENE_SNAPSHOT_FORMAT = "supersplat-packed-scene-snapshot"
BINARY_SCENE_SNAPSHOT_FORMAT_VERSION = 1


class SnapshotUploadError(ValueError):
    """Base failure for an untrusted binary SceneSnapshot upload."""


class IncompleteSnapshotUploadError(SnapshotUploadError):
    """Raised when commit is attempted before every declared chunk exists."""


class ImmutableSnapshotConflict(SnapshotUploadError):
    """Raised when one immutable registration identity receives different bytes."""


@dataclass(frozen=True)
class BinarySceneSnapshotChunk:
    index: int
    offset: int
    byte_length: int
    digest: str


@dataclass(frozen=True)
class BinarySceneSnapshotManifest:
    scene_id: str
    scene_version: str
    content_digest: str
    content: Mapping[str, object]
    chunk_byte_length: int
    chunks: tuple[BinarySceneSnapshotChunk, ...]


@dataclass(frozen=True)
class SnapshotUploadAdmission:
    status: str
    upload_id: str | None
    missing_chunk_indices: tuple[int, ...]


class BinarySceneSnapshotUploadStore:
    """Atomic Companion staging/cache seam for Ticket 02A."""

    def __init__(self, directory: Path, *, staging_ttl_seconds: float = 600.0) -> None:
        self.directory = directory
        self.staging_ttl_seconds = staging_ttl_seconds

    def begin(self, manifest: BinarySceneSnapshotManifest) -> SnapshotUploadAdmission:
        raise NotImplementedError("Binary SceneSnapshot Registration v1 is not implemented.")

    def accept_chunk(
        self,
        upload_id: str,
        index: int,
        payload: bytes,
        digest: str,
    ) -> None:
        raise NotImplementedError("Binary SceneSnapshot Registration v1 is not implemented.")

    def commit(self, upload_id: str) -> object:
        raise NotImplementedError("Binary SceneSnapshot Registration v1 is not implemented.")

    def abort(self, upload_id: str) -> None:
        raise NotImplementedError("Binary SceneSnapshot Registration v1 is not implemented.")

    def cleanup_expired(self) -> int:
        raise NotImplementedError("Binary SceneSnapshot Registration v1 is not implemented.")
