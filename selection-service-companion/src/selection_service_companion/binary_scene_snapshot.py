"""Typed, staged Binary SceneSnapshot Registration v1 support.

This module is the Companion-side trust boundary for the browser's effective
SceneSnapshot. It intentionally keeps payload bytes mmap-backed: no upload is
converted into a per-Gaussian Python record collection or canonical JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import re
import shutil
import struct
from threading import RLock
import time
from types import MappingProxyType
from typing import Any, Iterable, Mapping
import warnings


BINARY_SCENE_SNAPSHOT_FORMAT = "supersplat-packed-scene-snapshot"
BINARY_SCENE_SNAPSHOT_FORMAT_VERSION = 1
BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION = "1"
MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES = 4 * 1024 * 1024
MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT = 4096
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIELD_LAYOUT: tuple[tuple[str, str, int], ...] = (
    ("stableIds", "uint32le", 1),
    ("means", "float32le", 3),
    ("rotationsXyzw", "float32le", 4),
    ("logScales", "float32le", 3),
    ("logitOpacities", "float32le", 1),
    ("dc", "float32le", 3),
    ("sh", "float32le", 0),
)
_SH_FLOAT_COUNTS = {0, 9, 24, 45}
_SUPPORTED_COORDINATE_CONVENTION = "right-handed world coordinates; quaternion xyzw"
_SUPPORTED_RENDER_CONFIGURATION_VERSION = "supersplat-effective-rgb-v1"
_SUPPORTED_RASTERIZER = "playcanvas-gsplat-classic"


class SnapshotUploadError(ValueError):
    """Base failure for an untrusted binary SceneSnapshot upload."""


class IncompleteSnapshotUploadError(SnapshotUploadError):
    """Raised when commit is attempted before every declared chunk exists."""


class ImmutableSnapshotConflict(SnapshotUploadError):
    """Raised when one immutable registration identity receives different bytes."""


class UnknownSnapshotUpload(SnapshotUploadError):
    """Raised when an upload ID no longer identifies a staged upload."""


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
    format: str = BINARY_SCENE_SNAPSHOT_FORMAT
    format_version: int = BINARY_SCENE_SNAPSHOT_FORMAT_VERSION


@dataclass(frozen=True)
class SnapshotUploadAdmission:
    status: str
    upload_id: str | None
    missing_chunk_indices: tuple[int, ...]


@dataclass(frozen=True)
class SnapshotUploadCommit:
    """One idempotent commit acknowledgement and its immutable snapshot."""

    status: str
    snapshot: "PackedBinarySceneSnapshot"


@dataclass(frozen=True)
class PackedBinarySceneSnapshot:
    """One committed typed payload retained directly in a read-only mmap."""

    scene_id: str
    scene_version: str
    content_digest: str
    content: Mapping[str, object]
    path: Path
    payload: memoryview
    _mapping: mmap.mmap

    @property
    def gaussian_count(self) -> int:
        return _integer(self.content.get("gaussianCount"), "gaussianCount")

    @property
    def render_config_version(self) -> str:
        render_configuration = _mapping(self.content.get("renderConfiguration"), "renderConfiguration")
        return _string(render_configuration.get("version"), "renderConfiguration.version")

    @property
    def sh_float_count_per_gaussian(self) -> int:
        return _integer(
            self.content.get("shFloatCountPerGaussian"),
            "shFloatCountPerGaussian",
        )

    def field(self, name: str) -> memoryview:
        for field in _fields_from_content(self.content):
            if field.name == name:
                return self.payload[field.byte_offset:field.byte_offset + field.byte_length]
        raise KeyError(name)

    def stable_ids(self) -> memoryview:
        return self.field("stableIds").cast("I")

    def close(self) -> None:
        """Release an unpublished mmap after validation or publication failure."""

        self.payload.release()
        self._mapping.close()


@dataclass(frozen=True)
class _PackedField:
    name: str
    scalar_type: str
    component_count: int
    byte_offset: int
    byte_length: int


@dataclass
class _StagedUpload:
    manifest: BinarySceneSnapshotManifest
    logical_identity: str
    transfer_identity: str
    directory: Path
    updated_at: float


@dataclass(frozen=True)
class _CommittedSnapshot:
    logical_identity: str
    snapshot: PackedBinarySceneSnapshot


@dataclass(frozen=True)
class _CompletedUpload:
    logical_identity: str
    snapshot: PackedBinarySceneSnapshot
    completed_at: float


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SnapshotUploadError(f"Binary Scene Snapshot {field_name} must be an object")
    return value


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotUploadError(f"Binary Scene Snapshot {field_name} must be a non-empty string")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SnapshotUploadError(f"Binary Scene Snapshot {field_name} must be a non-negative integer")
    return value


def _digest(value: object, field_name: str) -> str:
    result = _string(value, field_name).lower()
    if not _DIGEST_PATTERN.fullmatch(result):
        raise SnapshotUploadError(f"Binary Scene Snapshot {field_name} must be a SHA-256 digest")
    return result


def _json_identity(value: object) -> str:
    try:
        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise SnapshotUploadError("Binary Scene Snapshot manifest contains unsupported values") from error


def _field_layout(
    gaussian_count: int, sh_float_count: int
) -> tuple[_PackedField, ...]:
    byte_offset = 0
    fields: list[_PackedField] = []
    for name, scalar_type, default_component_count in _FIELD_LAYOUT:
        component_count = (
            sh_float_count if name == "sh" else default_component_count
        )
        scalar_size = 4
        byte_length = gaussian_count * component_count * scalar_size
        fields.append(
            _PackedField(
                name=name,
                scalar_type=scalar_type,
                component_count=component_count,
                byte_offset=byte_offset,
                byte_length=byte_length,
            )
        )
        byte_offset += byte_length
    return tuple(fields)


def _fields_from_content(content: Mapping[str, object]) -> tuple[_PackedField, ...]:
    gaussian_count = _integer(content.get("gaussianCount"), "content.gaussianCount")
    sh_float_count = _integer(
        content.get("shFloatCountPerGaussian"),
        "content.shFloatCountPerGaussian",
    )
    return _field_layout(gaussian_count, sh_float_count)


def _validate_render_configuration(content: Mapping[str, object]) -> Mapping[str, object]:
    render_configuration = _mapping(
        content.get("renderConfiguration"), "content.renderConfiguration"
    )
    _string(render_configuration.get("version"), "content.renderConfiguration.version")
    if render_configuration.get("alphaMode") != "opaque-background":
        raise SnapshotUploadError("Binary Scene Snapshot alpha semantics are unsupported")
    _string(render_configuration.get("rasterizer"), "content.renderConfiguration.rasterizer")
    sh_bands = _integer(render_configuration.get("shBands"), "content.renderConfiguration.shBands")
    if sh_bands > 3:
        raise SnapshotUploadError("Binary Scene Snapshot shBands must be from 0 through 3")
    background = render_configuration.get("backgroundRgba")
    if not isinstance(background, list) or len(background) != 4:
        raise SnapshotUploadError("Binary Scene Snapshot backgroundRgba must contain four finite numbers")
    for value in background:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise SnapshotUploadError("Binary Scene Snapshot backgroundRgba must contain four finite numbers")
    if float(background[3]) != 1.0:
        raise SnapshotUploadError("Opaque Binary Scene Snapshots require background alpha 1")
    return render_configuration


def _validate_content(content: Mapping[str, object]) -> tuple[_PackedField, ...]:
    if content.get("protocolVersion") != BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION:
        raise SnapshotUploadError("Binary Scene Snapshot protocolVersion is unsupported")
    gaussian_count = _integer(content.get("gaussianCount"), "content.gaussianCount")
    if gaussian_count <= 0:
        raise SnapshotUploadError("Binary Scene Snapshot gaussianCount must be positive")
    if content.get("coordinateConvention") != _SUPPORTED_COORDINATE_CONVENTION:
        raise SnapshotUploadError("Binary Scene Snapshot coordinate convention is unsupported")
    if content.get("stableIdSchema") != "uint32":
        raise SnapshotUploadError("Binary Scene Snapshot Stable Gaussian IDs must use uint32")
    sh_float_count = _integer(
        content.get("shFloatCountPerGaussian"),
        "content.shFloatCountPerGaussian",
    )
    if sh_float_count not in _SH_FLOAT_COUNTS:
        raise SnapshotUploadError("Binary Scene Snapshot SH schema is unsupported")
    expected_attribute_schema = (
        "mean:f32x3;rotation:f32x4;logScale:f32x3;"
        f"logitOpacity:f32;dc:f32x3;sh:f32x{sh_float_count}"
    )
    if content.get("attributeSchema") != expected_attribute_schema:
        raise SnapshotUploadError("Binary Scene Snapshot attribute schema is unsupported")
    available_bands = {0: 0, 9: 1, 24: 2, 45: 3}[sh_float_count]
    if content.get("appearancePolicy") != f"effective-editor-dc-sh-bands-{available_bands}":
        raise SnapshotUploadError("Binary Scene Snapshot appearance policy is unsupported")
    render_configuration = _validate_render_configuration(content)
    if (
        render_configuration.get("version") != _SUPPORTED_RENDER_CONFIGURATION_VERSION
        or render_configuration.get("rasterizer") != _SUPPORTED_RASTERIZER
    ):
        raise SnapshotUploadError("Binary Scene Snapshot renderer semantics are unsupported")
    if _integer(render_configuration.get("shBands"), "content.renderConfiguration.shBands") > available_bands:
        raise SnapshotUploadError("Binary Scene Snapshot SH data does not support the declared shBands")
    fields = _field_layout(gaussian_count, sh_float_count)
    field_records = content.get("fields")
    if not isinstance(field_records, list) or len(field_records) != len(fields):
        raise SnapshotUploadError("Binary Scene Snapshot fields must describe the fixed packed layout")
    for expected, value in zip(fields, field_records, strict=True):
        field = _mapping(value, "content.fields entry")
        if field != {
            "name": expected.name,
            "scalarType": expected.scalar_type,
            "componentCount": expected.component_count,
            "byteOffset": expected.byte_offset,
            "byteLength": expected.byte_length,
        }:
            raise SnapshotUploadError("Binary Scene Snapshot fields do not match the fixed packed layout")
    payload_byte_length = _integer(content.get("payloadByteLength"), "content.payloadByteLength")
    expected_payload_byte_length = sum(field.byte_length for field in fields)
    if payload_byte_length != expected_payload_byte_length:
        raise SnapshotUploadError("Binary Scene Snapshot payloadByteLength does not match its packed fields")
    return fields


def _validate_manifest(manifest: BinarySceneSnapshotManifest) -> tuple[_PackedField, str, str]:
    if (
        manifest.format != BINARY_SCENE_SNAPSHOT_FORMAT
        or manifest.format_version != BINARY_SCENE_SNAPSHOT_FORMAT_VERSION
    ):
        raise SnapshotUploadError("Binary Scene Snapshot format is unsupported")
    scene_id = _string(manifest.scene_id, "sceneId")
    scene_version = _digest(manifest.scene_version, "sceneVersion")
    content_digest = _digest(manifest.content_digest, "contentDigest")
    if scene_version != content_digest:
        raise SnapshotUploadError("Binary Scene Snapshot sceneVersion must equal its contentDigest")
    content = _mapping(manifest.content, "content")
    fields = _validate_content(content)
    if (
        isinstance(manifest.chunk_byte_length, bool)
        or not isinstance(manifest.chunk_byte_length, int)
        or manifest.chunk_byte_length <= 0
        or manifest.chunk_byte_length > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES
    ):
        raise SnapshotUploadError("Binary Scene Snapshot chunkByteLength is outside the bounded limit")
    if not manifest.chunks or len(manifest.chunks) > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT:
        raise SnapshotUploadError("Binary Scene Snapshot chunk plan is outside the bounded limit")
    payload_byte_length = sum(field.byte_length for field in fields)
    expected_chunk_count = math.ceil(payload_byte_length / manifest.chunk_byte_length)
    if len(manifest.chunks) != expected_chunk_count:
        raise SnapshotUploadError("Binary Scene Snapshot chunk plan does not cover the payload")
    expected_offset = 0
    for index, chunk in enumerate(manifest.chunks):
        if (
            chunk.index != index
            or chunk.offset != expected_offset
            or chunk.byte_length <= 0
            or chunk.byte_length > manifest.chunk_byte_length
            or _digest(chunk.digest, f"chunk {index} digest") != chunk.digest.lower()
        ):
            raise SnapshotUploadError("Binary Scene Snapshot chunk plan is malformed")
        expected_length = min(manifest.chunk_byte_length, payload_byte_length - expected_offset)
        if chunk.byte_length != expected_length:
            raise SnapshotUploadError("Binary Scene Snapshot chunk plan is not contiguous")
        expected_offset += chunk.byte_length
    if expected_offset != payload_byte_length:
        raise SnapshotUploadError("Binary Scene Snapshot chunk plan does not cover the payload")
    logical_identity = _json_identity(
        {
            "format": manifest.format,
            "formatVersion": manifest.format_version,
            "sceneId": scene_id,
            "sceneVersion": scene_version,
            "contentDigest": content_digest,
            "content": content,
        }
    )
    transfer_identity = _json_identity(
        {
            "logical": json.loads(logical_identity),
            "chunkByteLength": manifest.chunk_byte_length,
            "chunks": [
                {
                    "index": chunk.index,
                    "offset": chunk.offset,
                    "byteLength": chunk.byte_length,
                    "digest": chunk.digest.lower(),
                }
                for chunk in manifest.chunks
            ],
        }
    )
    return fields, logical_identity, transfer_identity


def parse_binary_scene_snapshot_manifest(
    value: object,
) -> BinarySceneSnapshotManifest:
    top_level = _mapping(value, "manifest")
    content = _mapping(top_level.get("content"), "manifest.content")
    transfer = _mapping(top_level.get("transfer"), "manifest.transfer")
    chunks_value = transfer.get("chunks")
    if not isinstance(chunks_value, list):
        raise SnapshotUploadError("Binary Scene Snapshot transfer chunks must be an array")
    chunks: list[BinarySceneSnapshotChunk] = []
    for value_index, chunk_value in enumerate(chunks_value):
        chunk = _mapping(chunk_value, f"manifest.transfer.chunks[{value_index}]")
        chunks.append(
            BinarySceneSnapshotChunk(
                index=_integer(chunk.get("index"), f"chunk {value_index} index"),
                offset=_integer(chunk.get("offset"), f"chunk {value_index} offset"),
                byte_length=_integer(chunk.get("byteLength"), f"chunk {value_index} byteLength"),
                digest=_digest(chunk.get("digest"), f"chunk {value_index} digest"),
            )
        )
    manifest = BinarySceneSnapshotManifest(
        format=_string(top_level.get("format"), "manifest.format"),
        format_version=_integer(top_level.get("formatVersion"), "manifest.formatVersion"),
        scene_id=_string(top_level.get("sceneId"), "manifest.sceneId"),
        scene_version=_digest(top_level.get("sceneVersion"), "manifest.sceneVersion"),
        content_digest=_digest(top_level.get("contentDigest"), "manifest.contentDigest"),
        content=json.loads(_json_identity(content)),
        chunk_byte_length=_integer(transfer.get("chunkByteLength"), "manifest.transfer.chunkByteLength"),
        chunks=tuple(chunks),
    )
    _validate_manifest(manifest)
    return manifest


def _digest_metadata(hasher: hashlib._Hash, content: Mapping[str, object]) -> None:
    hasher.update(f"{BINARY_SCENE_SNAPSHOT_FORMAT}-v{BINARY_SCENE_SNAPSHOT_FORMAT_VERSION}\0".encode("utf-8"))
    render_configuration = _validate_render_configuration(content)
    strings = (
        _string(content.get("coordinateConvention"), "content.coordinateConvention"),
        _string(content.get("stableIdSchema"), "content.stableIdSchema"),
        _string(content.get("attributeSchema"), "content.attributeSchema"),
        _string(content.get("appearancePolicy"), "content.appearancePolicy"),
        _string(render_configuration.get("version"), "content.renderConfiguration.version"),
        _string(render_configuration.get("alphaMode"), "content.renderConfiguration.alphaMode"),
        _string(render_configuration.get("rasterizer"), "content.renderConfiguration.rasterizer"),
    )
    for value in strings:
        encoded = value.encode("utf-8")
        hasher.update(struct.pack("<I", len(encoded)))
        hasher.update(encoded)
    hasher.update(struct.pack("<I", _integer(content.get("gaussianCount"), "content.gaussianCount")))
    hasher.update(struct.pack("<I", _integer(content.get("shFloatCountPerGaussian"), "content.shFloatCountPerGaussian")))
    hasher.update(struct.pack("<I", _integer(render_configuration.get("shBands"), "content.renderConfiguration.shBands")))
    background = render_configuration["backgroundRgba"]
    assert isinstance(background, list)
    for value in background:
        hasher.update(struct.pack("<f", float(value)))
    for field in _fields_from_content(content):
        hasher.update(struct.pack("<I", field.component_count))


def _content_digest(
    content: Mapping[str, object], payload_chunks: Iterable[bytes | memoryview]
) -> str:
    hasher = hashlib.sha256()
    _digest_metadata(hasher, content)
    for payload_chunk in payload_chunks:
        hasher.update(payload_chunk)
    return f"sha256:{hasher.hexdigest()}"


def binary_scene_snapshot_content_digest(
    content: Mapping[str, object], payload_chunks: Iterable[bytes | memoryview]
) -> str:
    """Return the chunking-independent v1 digest for a validated typed payload."""

    _validate_content(content)
    return _content_digest(content, payload_chunks)


def _validate_typed_payload(snapshot: PackedBinarySceneSnapshot) -> None:
    """Validate mmap planes with tensors, never Python records per Gaussian.

    The locked renderer extra supplies PyTorch. These CPU views share the mmap
    until a later renderer call explicitly moves them to CUDA; they neither
    create a list/dict representation nor mutate browser-owned payload bytes.
    """

    try:
        import torch
    except ImportError as error:
        raise SnapshotUploadError(
            "Binary Scene Snapshot validation requires the locked renderer runtime"
        ) from error

    if len(snapshot.payload) != _integer(
        snapshot.content.get("payloadByteLength"), "content.payloadByteLength"
    ):
        raise SnapshotUploadError("Binary Scene Snapshot mmap payload is truncated")

    # `torch.frombuffer` correctly retains a read-only mmap view, but emits a
    # generic warning intended for callers that plan to mutate it. This code
    # only reads validation tensors and renderer code immediately copies to its
    # target device before mutation.
    validation_error: str | None = None
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The given buffer is not writable.*",
            category=UserWarning,
        )
        # Signed int32 is a bijection over uint32 bit patterns, so it retains
        # exact Stable Gaussian ID uniqueness without a Python integer set.
        stable_ids = torch.frombuffer(
            snapshot.field("stableIds"), dtype=torch.int32
        )
        if torch.unique(stable_ids).numel() != stable_ids.numel():
            validation_error = (
                "Binary Scene Snapshot Stable Gaussian IDs must be unique"
            )
        del stable_ids
        for field_name in (
            "means",
            "rotationsXyzw",
            "logScales",
            "logitOpacities",
            "dc",
            "sh",
        ):
            field = snapshot.field(field_name)
            if len(field) == 0:
                continue
            values = torch.frombuffer(field, dtype=torch.float32)
            if not bool(torch.isfinite(values).all().item()):
                validation_error = (
                    "Binary Scene Snapshot floating-point payload values must be finite"
                )
            del values
            field.release()
        rotations = torch.frombuffer(
            snapshot.field("rotationsXyzw"), dtype=torch.float32
        ).reshape(-1, 4)
        if bool((rotations.square().sum(dim=1) <= 0.0).any().item()):
            validation_error = (
                "Binary Scene Snapshot rotations must be non-zero quaternions"
            )
        del rotations
    if validation_error is not None:
        raise SnapshotUploadError(validation_error)


class BinarySceneSnapshotUploadStore:
    """Stages bounded raw chunks and atomically publishes mmap-backed snapshots."""

    def __init__(self, directory: Path, *, staging_ttl_seconds: float = 600.0) -> None:
        self.directory = directory
        self.staging_ttl_seconds = staging_ttl_seconds
        self._staging_directory = directory / "staging"
        self._committed_directory = directory / "committed"
        self._lock = RLock()
        self._staged: dict[str, _StagedUpload] = {}
        self._committed: dict[tuple[str, str], _CommittedSnapshot] = {}
        self._completed_uploads: dict[str, _CompletedUpload] = {}

    def begin(self, manifest: BinarySceneSnapshotManifest) -> SnapshotUploadAdmission:
        _, logical_identity, transfer_identity = _validate_manifest(manifest)
        key = (manifest.scene_id, manifest.scene_version)
        upload_id = "upload-" + hashlib.sha256(transfer_identity.encode("utf-8")).hexdigest()
        with self._lock:
            committed = self._committed.get(key)
            if committed is not None:
                if committed.logical_identity != logical_identity:
                    raise ImmutableSnapshotConflict(
                        "a Scene Snapshot version is immutable and cannot receive different content"
                    )
                return SnapshotUploadAdmission("alreadyCommitted", None, ())
            staged = self._staged.get(upload_id)
            if staged is not None:
                if staged.logical_identity != logical_identity:
                    raise ImmutableSnapshotConflict("the staged upload identity conflicts with immutable content")
                staged.updated_at = time.time()
                return SnapshotUploadAdmission(
                    "staged",
                    upload_id,
                    self._missing_chunk_indices(staged),
                )
            if any(
                candidate.manifest.scene_id == manifest.scene_id
                and candidate.manifest.scene_version == manifest.scene_version
                and candidate.logical_identity != logical_identity
                for candidate in self._staged.values()
            ):
                raise ImmutableSnapshotConflict(
                    "a staged Scene Snapshot version cannot receive different content"
                )
            directory = self._staging_directory / upload_id
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "manifest.json").write_text(
                transfer_identity + "\n", encoding="utf-8"
            )
            staged = _StagedUpload(
                manifest=manifest,
                logical_identity=logical_identity,
                transfer_identity=transfer_identity,
                directory=directory,
                updated_at=time.time(),
            )
            self._staged[upload_id] = staged
            return SnapshotUploadAdmission(
                "staged", upload_id, self._missing_chunk_indices(staged)
            )

    def accept_chunk(
        self,
        upload_id: str,
        index: int,
        payload: bytes,
        digest: str,
    ) -> str:
        with self._lock:
            staged = self._staged.get(upload_id)
            if staged is None:
                raise UnknownSnapshotUpload("the Binary Scene Snapshot upload is absent or expired")
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(staged.manifest.chunks):
                raise SnapshotUploadError("Binary Scene Snapshot chunk index is invalid")
            expected = staged.manifest.chunks[index]
            if digest.lower() != expected.digest.lower():
                raise ImmutableSnapshotConflict("Binary Scene Snapshot chunk digest does not match its manifest")
            if len(payload) != expected.byte_length:
                raise SnapshotUploadError("Binary Scene Snapshot chunk byte length does not match its manifest")
            actual_digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
            if actual_digest != expected.digest.lower():
                raise SnapshotUploadError("Binary Scene Snapshot chunk body does not match its SHA-256 digest")
            destination = self._chunk_path(staged, index)
            if destination.exists():
                existing = destination.read_bytes()
                if existing == payload:
                    staged.updated_at = time.time()
                    return "alreadyStored"
                raise ImmutableSnapshotConflict("Binary Scene Snapshot chunk cannot be overwritten with different bytes")
            temporary = destination.with_suffix(".tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, destination)
            staged.updated_at = time.time()
            return "stored"

    def commit(self, upload_id: str) -> PackedBinarySceneSnapshot:
        """Commit a staged upload, preserving the historical snapshot-only seam."""

        return self.commit_result(upload_id).snapshot

    def commit_result(self, upload_id: str) -> SnapshotUploadCommit:
        """Atomically publish an upload and retain an idempotent replay record."""

        with self._lock:
            completed = self._completed_uploads.get(upload_id)
            if completed is not None:
                return SnapshotUploadCommit("alreadyCommitted", completed.snapshot)
            staged = self._staged.get(upload_id)
            if staged is None:
                raise UnknownSnapshotUpload("the Binary Scene Snapshot upload is absent or expired")
            missing = self._missing_chunk_indices(staged)
            if missing:
                raise IncompleteSnapshotUploadError(
                    "Binary Scene Snapshot upload is incomplete: " + ", ".join(map(str, missing))
                )
            manifest = staged.manifest
            logical_identity = staged.logical_identity
            key = (manifest.scene_id, manifest.scene_version)
            committed = self._committed.get(key)
            if committed is not None:
                if committed.logical_identity != logical_identity:
                    raise ImmutableSnapshotConflict("a Scene Snapshot version is immutable and cannot receive different content")
                self._discard_staged_locked(upload_id)
                self._completed_uploads[upload_id] = _CompletedUpload(
                    logical_identity, committed.snapshot, time.time()
                )
                return SnapshotUploadCommit("alreadyCommitted", committed.snapshot)

            # This store-local lock deliberately covers the bounded disk commit.
            # It keeps abort/cleanup and competing commits from racing the same
            # staging directory; no state or GPU lock is held here.
            try:
                actual_content_digest = _content_digest(
                    manifest.content,
                    self._staged_payload_chunks(staged),
                )
                if actual_content_digest != manifest.content_digest:
                    raise ImmutableSnapshotConflict(
                        "Binary Scene Snapshot payload does not match its immutable content digest"
                    )
                snapshot = self._write_and_map_committed_snapshot(manifest, staged)
            except Exception:
                self._discard_staged_locked(upload_id)
                raise

            self._committed[key] = _CommittedSnapshot(logical_identity, snapshot)
            self._completed_uploads[upload_id] = _CompletedUpload(
                logical_identity, snapshot, time.time()
            )
            self._discard_staged_locked(upload_id)
            return SnapshotUploadCommit("committed", snapshot)

    def abort(self, upload_id: str) -> None:
        with self._lock:
            self._discard_staged_locked(upload_id)

    def cleanup_expired(self) -> int:
        cutoff = time.time() - self.staging_ttl_seconds
        with self._lock:
            expired = [
                upload_id
                for upload_id, staged in self._staged.items()
                if staged.updated_at < cutoff
            ]
            for upload_id in expired:
                self._discard_staged_locked(upload_id)
            completed = [
                upload_id
                for upload_id, completion in self._completed_uploads.items()
                if completion.completed_at < cutoff
            ]
            for upload_id in completed:
                self._completed_uploads.pop(upload_id, None)
            return len(expired) + len(completed)

    def committed_snapshot(
        self, scene_id: str, scene_version: str
    ) -> PackedBinarySceneSnapshot | None:
        with self._lock:
            committed = self._committed.get((scene_id, scene_version))
            return committed.snapshot if committed is not None else None

    def _write_and_map_committed_snapshot(
        self,
        manifest: BinarySceneSnapshotManifest,
        staged: _StagedUpload,
    ) -> PackedBinarySceneSnapshot:
        self._committed_directory.mkdir(parents=True, exist_ok=True)
        logical_hash = hashlib.sha256(staged.logical_identity.encode("utf-8")).hexdigest()
        destination = self._committed_directory / f"{logical_hash}.bin"
        temporary = destination.with_suffix(".tmp")
        snapshot: PackedBinarySceneSnapshot | None = None
        try:
            with temporary.open("wb") as output:
                for chunk in manifest.chunks:
                    with self._chunk_path(staged, chunk.index).open("rb") as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            with temporary.open("rb") as source:
                mapping = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
            content = MappingProxyType(json.loads(_json_identity(manifest.content)))
            snapshot = PackedBinarySceneSnapshot(
                scene_id=manifest.scene_id,
                scene_version=manifest.scene_version,
                content_digest=manifest.content_digest,
                content=content,
                path=destination,
                payload=memoryview(mapping),
                _mapping=mapping,
            )
            _validate_typed_payload(snapshot)
            os.replace(temporary, destination)
            return snapshot
        except Exception:
            if snapshot is not None:
                snapshot.close()
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _chunk_path(staged: _StagedUpload, index: int) -> Path:
        return staged.directory / f"chunk-{index:08d}.bin"

    def _missing_chunk_indices(self, staged: _StagedUpload) -> tuple[int, ...]:
        return tuple(
            chunk.index
            for chunk in staged.manifest.chunks
            if not self._chunk_path(staged, chunk.index).is_file()
        )

    def _staged_payload_chunks(self, staged: _StagedUpload) -> Iterable[bytes]:
        for chunk in staged.manifest.chunks:
            with self._chunk_path(staged, chunk.index).open("rb") as source:
                while payload := source.read(1024 * 1024):
                    yield payload

    def _discard_staged_locked(self, upload_id: str) -> None:
        staged = self._staged.pop(upload_id, None)
        if staged is not None:
            shutil.rmtree(staged.directory, ignore_errors=True)


__all__ = [
    "BINARY_SCENE_SNAPSHOT_FORMAT",
    "BINARY_SCENE_SNAPSHOT_FORMAT_VERSION",
    "BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION",
    "MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES",
    "MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT",
    "BinarySceneSnapshotChunk",
    "binary_scene_snapshot_content_digest",
    "BinarySceneSnapshotManifest",
    "BinarySceneSnapshotUploadStore",
    "ImmutableSnapshotConflict",
    "IncompleteSnapshotUploadError",
    "PackedBinarySceneSnapshot",
    "SnapshotUploadAdmission",
    "SnapshotUploadCommit",
    "SnapshotUploadError",
    "UnknownSnapshotUpload",
    "parse_binary_scene_snapshot_manifest",
]
