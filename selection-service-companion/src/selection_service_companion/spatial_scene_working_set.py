"""Typed CameraBinding working sets over immutable spatial SceneSnapshot chunks.

This is deliberately separate from Binary SceneSnapshot Registration v1. A
spatial manifest describes a complete effective editor snapshot while its
chunk payloads become resident only through verified, atomic batch commits.
Neither validation nor working-set assembly creates Python records per
Gaussian; mmap-backed planes flow straight into tensor operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import shutil
from threading import RLock
import time
from typing import Any, Mapping, Sequence
import warnings

from .binary_scene_snapshot import (
    ImmutableSnapshotConflict,
    IncompleteSnapshotUploadError,
    SnapshotUploadError,
    UnknownSnapshotUpload,
)


SPATIAL_SCENE_MANIFEST_FORMAT = "supersplat-spatial-scene-manifest"
SPATIAL_SCENE_MANIFEST_FORMAT_VERSION = 1
SPATIAL_SCENE_CHUNK_FORMAT = "supersplat-spatial-scene-chunk"
SPATIAL_SCENE_CHUNK_FORMAT_VERSION = 1
MAX_SPATIAL_SCENE_CHUNK_BYTES = 4 * 1024 * 1024
MAX_SPATIAL_SCENE_CHUNK_COUNT = 4096
MAX_SPATIAL_SCENE_MANIFEST_BYTES = 2 * 1024 * 1024
_VALIDITY_CUT = 1.0 / 255.0
_OPACITY_GUARD = 1.0 - 2.0 ** -12
_WORLD_EPSILON = 1e-5
_SCALE_EPSILON = 2.0 ** -18
_MAX_FINITE_SCALE = 1e12
_FRUSTUM_PIXEL_MARGIN = 2.0


@dataclass(frozen=True)
class SpatialSupportBounds:
    """A conservative world-space support envelope or an explicit fallback."""

    kind: str
    minimum: tuple[float, float, float] | None = None
    maximum: tuple[float, float, float] | None = None

    @classmethod
    def finite(
        cls,
        minimum: tuple[float, float, float],
        maximum: tuple[float, float, float],
    ) -> "SpatialSupportBounds":
        return cls("finite", tuple(minimum), tuple(maximum))

    @classmethod
    def empty(cls) -> "SpatialSupportBounds":
        return cls("empty")

    @classmethod
    def unbounded(cls) -> "SpatialSupportBounds":
        return cls("unbounded")


@dataclass(frozen=True)
class SpatialChunkDescriptor:
    chunk_id: str
    chunk_digest: str
    byte_length: int
    gaussian_count: int
    global_ordinal_min: int
    global_ordinal_max: int
    support_bounds: SpatialSupportBounds


@dataclass(frozen=True)
class SpatialSceneManifest:
    scene_id: str
    scene_version: str
    content_digest: str
    target_splat_id: str
    total_gaussian_count: int
    coordinate_convention: str
    stable_id_schema: str
    attribute_schema: str
    appearance_policy: str
    render_configuration: Mapping[str, object]
    sh_float_count_per_gaussian: int
    chunks: tuple[SpatialChunkDescriptor, ...]
    protocol_version: str = "1"
    format: str = SPATIAL_SCENE_MANIFEST_FORMAT
    format_version: int = SPATIAL_SCENE_MANIFEST_FORMAT_VERSION
    chunk_format: str = SPATIAL_SCENE_CHUNK_FORMAT
    chunk_format_version: int = SPATIAL_SCENE_CHUNK_FORMAT_VERSION


@dataclass(frozen=True)
class SpatialManifestRegistration:
    status: str
    registration_id: str
    scene_id: str
    scene_version: str
    content_digest: str


@dataclass(frozen=True)
class SpatialChunkUploadAdmission:
    status: str
    upload_id: str | None
    missing_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpatialChunkUploadCommit:
    status: str
    scene_id: str
    scene_version: str
    committed_chunk_ids: tuple[str, ...]


@dataclass
class _RegisteredManifest:
    manifest: SpatialSceneManifest
    identity: str
    registration_id: str


@dataclass
class _StagedChunkUpload:
    scene_id: str
    scene_version: str
    registration_id: str
    chunk_ids: tuple[str, ...]
    directory: Path
    updated_at: float


@dataclass
class _CompletedChunkUpload:
    scene_id: str
    scene_version: str
    chunk_ids: tuple[str, ...]
    completed_at: float


@dataclass
class ResidentSpatialChunk:
    """One immutable chunk retained as a read-only mmap."""

    descriptor: SpatialChunkDescriptor
    sh_float_count_per_gaussian: int
    path: Path
    payload: memoryview
    _mapping: mmap.mmap

    def field(self, name: str) -> memoryview:
        count = self.descriptor.gaussian_count
        lengths = {
            "globalOrdinals": count * 4,
            "stableIds": count * 4,
            "means": count * 3 * 4,
            "rotationsXyzw": count * 4 * 4,
            "logScales": count * 3 * 4,
            "logitOpacities": count * 4,
            "dc": count * 3 * 4,
            "sh": count * self.sh_float_count_per_gaussian * 4,
        }
        if name not in lengths:
            raise KeyError(name)
        offset = 0
        for candidate in (
            "globalOrdinals",
            "stableIds",
            "means",
            "rotationsXyzw",
            "logScales",
            "logitOpacities",
            "dc",
            "sh",
        ):
            length = lengths[candidate]
            if candidate == name:
                return self.payload[offset:offset + length]
            offset += length
        raise KeyError(name)

    def close(self) -> None:
        self.payload.release()
        self._mapping.close()


@dataclass
class SpatialWorkingSet:
    """A deterministic resident subset with tensor-row order restored globally."""

    manifest: SpatialSceneManifest
    chunks: tuple[ResidentSpatialChunk, ...]
    working_set_token: str
    _cached_tensors: dict[str, Any] | None = None

    def ordered_tensors(self) -> Mapping[str, Any]:
        """Return CPU tensors ordered by global ordinal without Python Gaussian rows."""

        if self._cached_tensors is not None:
            return self._cached_tensors
        try:
            import torch
        except ImportError as error:
            raise SnapshotUploadError(
                "Spatial Scene working sets require the locked renderer runtime"
            ) from error

        if not self.chunks:
            raise SnapshotUploadError("Spatial Scene working set has no resident chunks")
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="The given buffer is not writable.*",
                category=UserWarning,
            )
            ordinal_parts = [
                torch.frombuffer(chunk.field("globalOrdinals"), dtype=torch.int32)
                for chunk in self.chunks
            ]
            stable_parts = [
                torch.frombuffer(chunk.field("stableIds"), dtype=torch.int32)
                for chunk in self.chunks
            ]
            float_shapes = {
                "means": 3,
                "rotationsXyzw": 4,
                "logScales": 3,
                "logitOpacities": 1,
                "dc": 3,
                "sh": self.manifest.sh_float_count_per_gaussian,
            }
            float_parts: dict[str, list[Any]] = {name: [] for name in float_shapes}
            for chunk in self.chunks:
                count = chunk.descriptor.gaussian_count
                for name, components in float_shapes.items():
                    expected = count * components
                    values = (
                        torch.empty(expected, dtype=torch.float32)
                        if expected == 0
                        else torch.frombuffer(chunk.field(name), dtype=torch.float32)
                    )
                    if values.numel() != expected:
                        raise SnapshotUploadError(
                            "Spatial Scene chunk field length is inconsistent"
                        )
                    shape = (count,) if components == 1 else (count, components)
                    float_parts[name].append(values.reshape(shape))

        global_ordinals = torch.cat(ordinal_parts).to(torch.int64)
        if torch.unique(global_ordinals).numel() != global_ordinals.numel():
            raise SnapshotUploadError(
                "Spatial Scene working set has duplicate global ordinals"
            )
        order = torch.argsort(global_ordinals, stable=True)
        stable_ids = torch.cat(stable_parts).to(torch.int64)
        stable_ids = torch.bitwise_and(stable_ids, 0xFFFFFFFF)[order]
        if torch.unique(stable_ids).numel() != stable_ids.numel():
            raise SnapshotUploadError(
                "Spatial Scene working set has duplicate Stable Gaussian IDs"
            )
        tensors: dict[str, Any] = {
            "globalOrdinals": global_ordinals[order],
            "stableIds": stable_ids,
        }
        for name, parts in float_parts.items():
            if not parts:
                continue
            tensors[name] = torch.cat(parts)[order]
        self._cached_tensors = tensors
        return tensors


@dataclass(frozen=True)
class SpatialWorkingSetResolution:
    scene_id: str
    scene_version: str
    camera_binding: Mapping[str, object]
    working_set_token: str
    required_chunk_ids: tuple[str, ...]
    missing_chunk_ids: tuple[str, ...]
    fallback_all_chunks: bool
    working_set: SpatialWorkingSet | None


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise SnapshotUploadError("Spatial Scene protocol values must be canonical JSON") from error


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _manifest_wire(manifest: SpatialSceneManifest) -> dict[str, object]:
    def support_bounds(bounds: SpatialSupportBounds) -> dict[str, object]:
        result: dict[str, object] = {"kind": bounds.kind}
        if bounds.minimum is not None:
            result["min"] = list(bounds.minimum)
        if bounds.maximum is not None:
            result["max"] = list(bounds.maximum)
        return result

    return {
        "format": manifest.format,
        "formatVersion": manifest.format_version,
        "chunkFormat": manifest.chunk_format,
        "chunkFormatVersion": manifest.chunk_format_version,
        "protocolVersion": manifest.protocol_version,
        "sceneId": manifest.scene_id,
        "sceneVersion": manifest.scene_version,
        "contentDigest": manifest.content_digest,
        "targetSplatId": manifest.target_splat_id,
        "totalGaussianCount": manifest.total_gaussian_count,
        "coordinateConvention": manifest.coordinate_convention,
        "stableIdSchema": manifest.stable_id_schema,
        "attributeSchema": manifest.attribute_schema,
        "appearancePolicy": manifest.appearance_policy,
        "renderConfiguration": manifest.render_configuration,
        "shFloatCountPerGaussian": manifest.sh_float_count_per_gaussian,
        "chunks": [
            {
                "chunkId": chunk.chunk_id,
                "chunkDigest": chunk.chunk_digest,
                "byteLength": chunk.byte_length,
                "gaussianCount": chunk.gaussian_count,
                "globalOrdinalMin": chunk.global_ordinal_min,
                "globalOrdinalMax": chunk.global_ordinal_max,
                "supportBounds": support_bounds(chunk.support_bounds),
            }
            for chunk in manifest.chunks
        ],
    }


def spatial_manifest_registration_id(manifest: SpatialSceneManifest) -> str:
    return "spatial-manifest-" + hashlib.sha256(
        _canonical_json(_manifest_wire(manifest)).encode("utf-8")
    ).hexdigest()


def _is_digest(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    return len(value) == len("sha256:") + 64 and all(
        character in "0123456789abcdef" for character in value[len("sha256:"):].lower()
    )


def _validate_support_bounds(bounds: SpatialSupportBounds) -> None:
    if bounds.kind == "empty":
        if bounds.minimum is not None or bounds.maximum is not None:
            raise SnapshotUploadError("Empty Spatial Scene support bounds must not carry extents")
        return
    if bounds.kind == "unbounded":
        if bounds.minimum is not None or bounds.maximum is not None:
            raise SnapshotUploadError("Unbounded Spatial Scene support bounds must not carry extents")
        return
    if bounds.kind != "finite" or bounds.minimum is None or bounds.maximum is None:
        raise SnapshotUploadError("Spatial Scene support bounds are invalid")
    if len(bounds.minimum) != 3 or len(bounds.maximum) != 3:
        raise SnapshotUploadError("Spatial Scene support bounds must have three axes")
    if any(not math.isfinite(value) for value in (*bounds.minimum, *bounds.maximum)):
        raise SnapshotUploadError("Spatial Scene support bounds must be finite")
    if any(minimum > maximum for minimum, maximum in zip(bounds.minimum, bounds.maximum, strict=True)):
        raise SnapshotUploadError("Spatial Scene support bounds have an inverted axis")


def _expected_chunk_byte_length(count: int, sh_float_count: int) -> int:
    return count * (64 + 4 * sh_float_count)


def _validate_manifest(manifest: SpatialSceneManifest) -> None:
    if (
        manifest.format != SPATIAL_SCENE_MANIFEST_FORMAT
        or manifest.format_version != SPATIAL_SCENE_MANIFEST_FORMAT_VERSION
        or manifest.chunk_format != SPATIAL_SCENE_CHUNK_FORMAT
        or manifest.chunk_format_version != SPATIAL_SCENE_CHUNK_FORMAT_VERSION
        or manifest.protocol_version != "1"
    ):
        raise SnapshotUploadError("Spatial Scene manifest schema is unsupported")
    if (
        not manifest.scene_id
        or manifest.scene_id != manifest.target_splat_id
        or manifest.scene_version != manifest.content_digest
        or not _is_digest(manifest.scene_version)
    ):
        raise SnapshotUploadError("Spatial Scene manifest identity is invalid")
    if manifest.total_gaussian_count < 0 or manifest.sh_float_count_per_gaussian not in (0, 9, 24, 45):
        raise SnapshotUploadError("Spatial Scene manifest count or SH schema is invalid")
    if len(manifest.chunks) > MAX_SPATIAL_SCENE_CHUNK_COUNT:
        raise SnapshotUploadError("Spatial Scene manifest exceeds the bounded chunk count")
    if len(_canonical_json(_manifest_wire(manifest)).encode("utf-8")) > MAX_SPATIAL_SCENE_MANIFEST_BYTES:
        raise SnapshotUploadError("Spatial Scene manifest exceeds the bounded JSON limit")
    chunk_ids = tuple(chunk.chunk_id for chunk in manifest.chunks)
    if chunk_ids != tuple(sorted(chunk_ids)) or len(set(chunk_ids)) != len(chunk_ids):
        raise SnapshotUploadError("Spatial Scene chunk IDs must be unique and sorted")
    if sum(chunk.gaussian_count for chunk in manifest.chunks) != manifest.total_gaussian_count:
        raise SnapshotUploadError("Spatial Scene manifest Gaussian count is incomplete")
    for chunk in manifest.chunks:
        if (
            not chunk.chunk_id
            or not _is_digest(chunk.chunk_digest)
            or chunk.gaussian_count <= 0
            or chunk.byte_length != _expected_chunk_byte_length(
                chunk.gaussian_count, manifest.sh_float_count_per_gaussian
            )
            or chunk.byte_length > MAX_SPATIAL_SCENE_CHUNK_BYTES
            or chunk.global_ordinal_min < 0
            or chunk.global_ordinal_max < chunk.global_ordinal_min
            or chunk.global_ordinal_max >= manifest.total_gaussian_count
            or chunk.global_ordinal_max - chunk.global_ordinal_min + 1 < chunk.gaussian_count
        ):
            raise SnapshotUploadError("Spatial Scene chunk descriptor is invalid")
        _validate_support_bounds(chunk.support_bounds)


def _camera_components(
    camera_binding: Mapping[str, object],
) -> tuple[tuple[float, ...], tuple[float, float, float, float, int, int, float, float]] | None:
    try:
        if camera_binding.get("conventionVersion") != "opencv-camera-to-world/v1":
            return None
        matrix_value = camera_binding.get("cameraToWorld")
        projection_value = camera_binding.get("projection")
        if not isinstance(matrix_value, Sequence) or isinstance(matrix_value, (str, bytes)):
            return None
        if not isinstance(projection_value, Mapping) or projection_value.get("model") != "pinhole":
            return None
        matrix = tuple(float(value) for value in matrix_value)
        if len(matrix) != 16 or any(not math.isfinite(value) for value in matrix):
            return None
        if matrix[12:] != (0.0, 0.0, 0.0, 1.0):
            return None
        fx = float(projection_value["fx"])
        fy = float(projection_value["fy"])
        cx = float(projection_value["cx"])
        cy = float(projection_value["cy"])
        width = int(projection_value["width"])
        height = int(projection_value["height"])
        near = float(projection_value["near"])
        far = float(projection_value["far"])
        if (
            not all(math.isfinite(value) for value in (fx, fy, cx, cy, near, far))
            or fx <= 0.0
            or fy <= 0.0
            or width <= 0
            or height <= 0
            or near <= 0.0
            or far <= near
        ):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    tx, ty, tz = matrix[3], matrix[7], matrix[11]
    world_to_camera = (
        matrix[0], matrix[4], matrix[8], -(matrix[0] * tx + matrix[4] * ty + matrix[8] * tz),
        matrix[1], matrix[5], matrix[9], -(matrix[1] * tx + matrix[5] * ty + matrix[9] * tz),
        matrix[2], matrix[6], matrix[10], -(matrix[2] * tx + matrix[6] * ty + matrix[10] * tz),
    )
    return world_to_camera, (fx, fy, cx, cy, width, height, near, far)


def _intersects_camera_frustum(
    bounds: SpatialSupportBounds,
    camera_binding: Mapping[str, object],
) -> bool | None:
    """Return False only for a proven outside conservative bound.

    ``None`` means the relation cannot be proven safely and makes the caller
    request all chunks. The two-pixel image-plane expansion and world epsilon
    mirror the editor's manifest support contract.
    """

    if bounds.kind == "empty":
        return False
    if bounds.kind != "finite" or bounds.minimum is None or bounds.maximum is None:
        return None
    components = _camera_components(camera_binding)
    if components is None:
        return None
    matrix, (fx, fy, cx, cy, width, height, near, far) = components
    points: list[tuple[float, float, float]] = []
    for x in (bounds.minimum[0], bounds.maximum[0]):
        for y in (bounds.minimum[1], bounds.maximum[1]):
            for z in (bounds.minimum[2], bounds.maximum[2]):
                points.append((
                    matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
                    matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
                    matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11],
                ))
    if any(not all(math.isfinite(component) for component in point) for point in points):
        return None
    if max(point[2] for point in points) < near - _WORLD_EPSILON:
        return False
    if min(point[2] for point in points) > far + _WORLD_EPSILON:
        return False
    # Any bound crossing the camera plane is a perspective ambiguity. It must
    # be included rather than rejected from an invalid projected interval.
    if min(point[2] for point in points) <= 0.0:
        return None
    left = lambda point: fx * point[0] + (cx + _FRUSTUM_PIXEL_MARGIN) * point[2]
    right = lambda point: fx * point[0] - (width + _FRUSTUM_PIXEL_MARGIN - cx) * point[2]
    top = lambda point: fy * point[1] + (cy + _FRUSTUM_PIXEL_MARGIN) * point[2]
    bottom = lambda point: fy * point[1] - (height + _FRUSTUM_PIXEL_MARGIN - cy) * point[2]
    if max(left(point) for point in points) < -_WORLD_EPSILON:
        return False
    if min(right(point) for point in points) > _WORLD_EPSILON:
        return False
    if max(top(point) for point in points) < -_WORLD_EPSILON:
        return False
    if min(bottom(point) for point in points) > _WORLD_EPSILON:
        return False
    return True


def _working_set_token(
    manifest: SpatialSceneManifest,
    camera_binding: Mapping[str, object],
    chunks: Sequence[SpatialChunkDescriptor],
) -> str:
    value = {
        "format": "supersplat-camera-working-set-v1",
        "sceneId": manifest.scene_id,
        "sceneVersion": manifest.scene_version,
        "cameraBinding": camera_binding,
        "chunks": [
            {"chunkId": chunk.chunk_id, "chunkDigest": chunk.chunk_digest}
            for chunk in chunks
        ],
    }
    return _digest(_canonical_json(value).encode("utf-8"))


def _validate_chunk_payload(
    manifest: SpatialSceneManifest,
    descriptor: SpatialChunkDescriptor,
    payload: bytes | memoryview,
) -> None:
    """Use tensor views to validate one raw chunk without Gaussian dict/list rows."""

    if len(payload) != descriptor.byte_length:
        raise SnapshotUploadError("Spatial Scene chunk payload has the wrong byte length")
    if _digest(bytes(payload)) != descriptor.chunk_digest:
        raise SnapshotUploadError("Spatial Scene chunk payload does not match its digest")
    try:
        import torch
    except ImportError as error:
        raise SnapshotUploadError(
            "Spatial Scene chunk validation requires the locked renderer runtime"
        ) from error

    view = memoryview(payload)
    count = descriptor.gaussian_count
    lengths = {
        "globalOrdinals": count * 4,
        "stableIds": count * 4,
        "means": count * 3 * 4,
        "rotationsXyzw": count * 4 * 4,
        "logScales": count * 3 * 4,
        "logitOpacities": count * 4,
        "dc": count * 3 * 4,
        "sh": count * manifest.sh_float_count_per_gaussian * 4,
    }
    offset = 0
    fields: dict[str, memoryview] = {}
    for name, length in lengths.items():
        fields[name] = view[offset:offset + length]
        offset += length
    validation_error: str | None = None
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The given buffer is not writable.*",
            category=UserWarning,
        )
        ordinals = torch.frombuffer(fields["globalOrdinals"], dtype=torch.int32).to(torch.int64)
        if (
            torch.unique(ordinals).numel() != ordinals.numel()
            or bool((ordinals < descriptor.global_ordinal_min).any().item())
            or bool((ordinals > descriptor.global_ordinal_max).any().item())
        ):
            validation_error = "Spatial Scene chunk global ordinals are invalid"
        stable_ids = torch.frombuffer(fields["stableIds"], dtype=torch.int32)
        if torch.unique(stable_ids).numel() != stable_ids.numel():
            validation_error = "Spatial Scene chunk Stable Gaussian IDs must be unique"
        float_values: dict[str, Any] = {}
        for name in ("means", "rotationsXyzw", "logScales", "logitOpacities", "dc", "sh"):
            values = (
                torch.empty(0, dtype=torch.float32)
                if len(fields[name]) == 0
                else torch.frombuffer(fields[name], dtype=torch.float32)
            )
            if values.numel() and not bool(torch.isfinite(values).all().item()):
                validation_error = "Spatial Scene chunk floating-point values must be finite"
            float_values[name] = values
        rotations = float_values["rotationsXyzw"].reshape(-1, 4)
        if bool((rotations.square().sum(dim=1) <= 0.0).any().item()):
            validation_error = "Spatial Scene chunk rotations must be non-zero"
        if validation_error is None:
            _validate_declared_support_bounds(
                descriptor.support_bounds,
                float_values["means"].reshape(-1, 3),
                rotations,
                float_values["logScales"].reshape(-1, 3),
                float_values["logitOpacities"],
            )
    for field in fields.values():
        field.release()
    view.release()
    if validation_error is not None:
        raise SnapshotUploadError(validation_error)


def _validate_declared_support_bounds(
    declared: SpatialSupportBounds,
    means: Any,
    rotations_xyzw: Any,
    log_scales: Any,
    logit_opacities: Any,
) -> None:
    """Prove that a manifest bound covers its actual typed chunk payload."""

    import torch

    scales = log_scales.exp()
    norms = rotations_xyzw.square().sum(dim=1).sqrt()
    opacity = logit_opacities.sigmoid()
    unsafe = (
        ~torch.isfinite(scales).all(dim=1)
        | (scales <= 0.0).any(dim=1)
        | (scales > _MAX_FINITE_SCALE).any(dim=1)
        | ~torch.isfinite(norms)
        | (norms <= 0.0)
        | ~torch.isfinite(opacity)
    )
    if bool(unsafe.any().item()):
        if declared.kind != "unbounded":
            raise SnapshotUploadError(
                "Spatial Scene chunk needs unbounded support fallback for unsafe values"
            )
        return
    nonempty = opacity >= _VALIDITY_CUT * _OPACITY_GUARD
    if not bool(nonempty.any().item()):
        if declared.kind not in ("empty", "unbounded"):
            raise SnapshotUploadError("Spatial Scene chunk declared finite support for empty payload")
        return
    if declared.kind == "unbounded":
        return
    if declared.kind != "finite" or declared.minimum is None or declared.maximum is None:
        raise SnapshotUploadError("Spatial Scene chunk support bounds omit possible contributors")
    normalized = rotations_xyzw / norms[:, None]
    x, y, z, w = normalized.unbind(dim=1)
    rows = (
        torch.stack((1 - 2 * (y.square() + z.square()), 2 * (x * y - z * w), 2 * (x * z + y * w)), dim=1),
        torch.stack((2 * (x * y + z * w), 1 - 2 * (x.square() + z.square()), 2 * (y * z - x * w)), dim=1),
        torch.stack((2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x.square() + y.square())), dim=1),
    )
    support_radius = torch.sqrt(
        torch.clamp(2.0 * torch.log(torch.clamp(opacity, min=_VALIDITY_CUT) / _VALIDITY_CUT), min=0.0)
    )
    epsilon = _WORLD_EPSILON + _SCALE_EPSILON * torch.maximum(
        torch.ones_like(scales[:, 0]), scales.max(dim=1).values
    )
    extents = torch.stack(
        (
            support_radius * torch.sqrt((rows[0].square() * scales.square()).sum(dim=1)) + epsilon,
            support_radius * torch.sqrt((rows[1].square() * scales.square()).sum(dim=1)) + epsilon,
            support_radius * torch.sqrt((rows[2].square() * scales.square()).sum(dim=1)) + epsilon,
        ),
        dim=1,
    )
    actual_minimum = (means - extents)[nonempty].amin(dim=0)
    actual_maximum = (means + extents)[nonempty].amax(dim=0)
    declared_minimum = torch.tensor(declared.minimum, dtype=torch.float32)
    declared_maximum = torch.tensor(declared.maximum, dtype=torch.float32)
    tolerance = _WORLD_EPSILON * 2.0
    if bool((actual_minimum < declared_minimum - tolerance).any().item()) or bool(
        (actual_maximum > declared_maximum + tolerance).any().item()
    ):
        raise SnapshotUploadError(
            "Spatial Scene chunk support bounds do not cover its typed payload"
        )


class SpatialSceneStore:
    """Own immutable global manifests and target-local validated residency."""

    def __init__(self, directory: Path, *, staging_ttl_seconds: float = 600.0) -> None:
        self.directory = directory
        self.staging_ttl_seconds = staging_ttl_seconds
        self._staging_directory = directory / "spatial-staging"
        self._committed_directory = directory / "spatial-committed"
        self._lock = RLock()
        self._manifests: dict[tuple[str, str], _RegisteredManifest] = {}
        self._registration_keys: dict[str, tuple[str, str]] = {}
        self._resident: dict[tuple[str, str, str], ResidentSpatialChunk] = {}
        self._staged: dict[str, _StagedChunkUpload] = {}
        self._completed: dict[str, _CompletedChunkUpload] = {}

    def register_manifest(self, manifest: SpatialSceneManifest) -> SpatialManifestRegistration:
        _validate_manifest(manifest)
        identity = _canonical_json(_manifest_wire(manifest))
        registration_id = spatial_manifest_registration_id(manifest)
        key = (manifest.scene_id, manifest.scene_version)
        with self._lock:
            existing = self._manifests.get(key)
            if existing is not None:
                if existing.identity != identity:
                    raise ImmutableSnapshotConflict(
                        "a Spatial Scene manifest version is immutable and cannot change"
                    )
                return SpatialManifestRegistration(
                    "alreadyRegistered",
                    existing.registration_id,
                    manifest.scene_id,
                    manifest.scene_version,
                    manifest.content_digest,
                )
            self._manifests[key] = _RegisteredManifest(manifest, identity, registration_id)
            self._registration_keys[registration_id] = key
            return SpatialManifestRegistration(
                "registered",
                registration_id,
                manifest.scene_id,
                manifest.scene_version,
                manifest.content_digest,
            )

    def begin_chunk_upload(
        self,
        scene_id: str,
        scene_version: str,
        chunk_ids: Sequence[str],
    ) -> SpatialChunkUploadAdmission:
        key = (scene_id, scene_version)
        requested = tuple(chunk_ids)
        with self._lock:
            registered = self._manifests.get(key)
            if registered is None:
                raise SnapshotUploadError("Spatial Scene manifest is absent or has the wrong scene version")
            descriptor_ids = {chunk.chunk_id for chunk in registered.manifest.chunks}
            if (
                not requested
                or requested != tuple(sorted(requested))
                or len(set(requested)) != len(requested)
                or any(chunk_id not in descriptor_ids for chunk_id in requested)
            ):
                raise SnapshotUploadError("Spatial Scene chunk upload IDs are invalid")
            missing_residency = tuple(
                chunk_id
                for chunk_id in requested
                if (scene_id, scene_version, chunk_id) not in self._resident
            )
            if not missing_residency:
                return SpatialChunkUploadAdmission("alreadyCommitted", None, ())
            identity = _canonical_json({
                "registrationId": registered.registration_id,
                "chunkIds": list(requested),
            })
            upload_id = "spatial-upload-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
            staged = self._staged.get(upload_id)
            if staged is not None:
                staged.updated_at = time.time()
                return SpatialChunkUploadAdmission(
                    "staged", upload_id, self._missing_staged_chunk_ids(staged)
                )
            directory = self._staging_directory / upload_id
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "identity.json").write_text(identity + "\n", encoding="utf-8")
            staged = _StagedChunkUpload(
                scene_id, scene_version, registered.registration_id, requested, directory, time.time()
            )
            self._staged[upload_id] = staged
            return SpatialChunkUploadAdmission(
                "staged", upload_id, self._missing_staged_chunk_ids(staged)
            )

    def accept_chunk(
        self,
        upload_id: str,
        chunk_id: str,
        payload: bytes,
        digest: str,
    ) -> str:
        with self._lock:
            staged = self._staged.get(upload_id)
            if staged is None:
                raise UnknownSnapshotUpload("the Spatial Scene chunk upload is absent or expired")
            registered = self._registered_for_stage(staged)
            if chunk_id not in staged.chunk_ids:
                raise SnapshotUploadError("Spatial Scene chunk upload requested an unknown chunk ID")
            descriptor = self._descriptor(registered.manifest, chunk_id)
            if digest.lower() != descriptor.chunk_digest:
                raise ImmutableSnapshotConflict("Spatial Scene chunk digest conflicts with its manifest")
            if len(payload) != descriptor.byte_length or _digest(payload) != descriptor.chunk_digest:
                raise SnapshotUploadError("Spatial Scene chunk bytes do not match their manifest digest")
            destination = self._staged_chunk_path(staged, chunk_id)
            if destination.exists():
                if destination.read_bytes() == payload:
                    staged.updated_at = time.time()
                    return "alreadyStored"
                raise ImmutableSnapshotConflict("Spatial Scene chunk cannot be overwritten")
            temporary = destination.with_suffix(".tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, destination)
            staged.updated_at = time.time()
            return "stored"

    def commit_chunk_upload(self, upload_id: str) -> SpatialChunkUploadCommit:
        with self._lock:
            completed = self._completed.get(upload_id)
            if completed is not None:
                return SpatialChunkUploadCommit(
                    "alreadyCommitted", completed.scene_id, completed.scene_version, completed.chunk_ids
                )
            staged = self._staged.get(upload_id)
            if staged is None:
                raise UnknownSnapshotUpload("the Spatial Scene chunk upload is absent or expired")
            missing = self._missing_staged_chunk_ids(staged)
            if missing:
                raise IncompleteSnapshotUploadError(
                    "Spatial Scene chunk upload is incomplete: " + ", ".join(missing)
                )
            registered = self._registered_for_stage(staged)
            new_chunks: list[ResidentSpatialChunk] = []
            created_paths: list[Path] = []
            try:
                for chunk_id in staged.chunk_ids:
                    resident_key = (staged.scene_id, staged.scene_version, chunk_id)
                    if resident_key in self._resident:
                        continue
                    descriptor = self._descriptor(registered.manifest, chunk_id)
                    source = self._staged_chunk_path(staged, chunk_id)
                    payload = source.read_bytes()
                    _validate_chunk_payload(registered.manifest, descriptor, payload)
                    destination = self._committed_chunk_path(registered.registration_id, chunk_id)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_suffix(f".{upload_id}.tmp")
                    temporary.write_bytes(payload)
                    os.replace(temporary, destination)
                    created_paths.append(destination)
                    new_chunks.append(self._map_chunk(destination, descriptor, registered.manifest))
            except Exception:
                for chunk in new_chunks:
                    chunk.close()
                for path in created_paths:
                    path.unlink(missing_ok=True)
                raise
            for chunk in new_chunks:
                self._resident[(staged.scene_id, staged.scene_version, chunk.descriptor.chunk_id)] = chunk
            self._completed[upload_id] = _CompletedChunkUpload(
                staged.scene_id, staged.scene_version, staged.chunk_ids, time.time()
            )
            self._discard_staged_locked(upload_id)
            return SpatialChunkUploadCommit(
                "committed", staged.scene_id, staged.scene_version, staged.chunk_ids
            )

    def abort_chunk_upload(self, upload_id: str) -> None:
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
                for upload_id, record in self._completed.items()
                if record.completed_at < cutoff
            ]
            for upload_id in completed:
                self._completed.pop(upload_id, None)
            return len(expired) + len(completed)

    def release_manifest(self, registration_id: str) -> None:
        with self._lock:
            key = self._registration_keys.pop(registration_id, None)
            if key is None:
                return
            registered = self._manifests.pop(key, None)
            if registered is None:
                return
            for resident_key in [candidate for candidate in self._resident if candidate[:2] == key]:
                self._resident.pop(resident_key).close()
            for upload_id, staged in list(self._staged.items()):
                if staged.registration_id == registration_id:
                    self._discard_staged_locked(upload_id)
            shutil.rmtree(self._committed_directory / registration_id, ignore_errors=True)

    def resolve_working_set(
        self,
        scene_id: str,
        scene_version: str,
        camera_binding: Mapping[str, object],
    ) -> SpatialWorkingSetResolution:
        key = (scene_id, scene_version)
        with self._lock:
            registered = self._manifests.get(key)
            if registered is None:
                raise SnapshotUploadError("Spatial Scene manifest is absent or has the wrong scene version")
            required, fallback_all = self._required_chunks(registered.manifest, camera_binding)
            token = _working_set_token(registered.manifest, camera_binding, required)
            missing = tuple(
                descriptor.chunk_id
                for descriptor in required
                if (scene_id, scene_version, descriptor.chunk_id) not in self._resident
            )
            working_set = None
            if not missing:
                working_set = SpatialWorkingSet(
                    registered.manifest,
                    tuple(
                        self._resident[(scene_id, scene_version, descriptor.chunk_id)]
                        for descriptor in required
                    ),
                    token,
                )
            return SpatialWorkingSetResolution(
                scene_id,
                scene_version,
                dict(camera_binding),
                token,
                tuple(descriptor.chunk_id for descriptor in required),
                missing,
                fallback_all,
                working_set,
            )

    def full_working_set(
        self,
        scene_id: str,
        scene_version: str,
        camera_binding: Mapping[str, object],
    ) -> SpatialWorkingSet:
        """Assemble the immutable all-chunk reference without JSON expansion.

        This exists for fixture parity and fail-safe recovery. It requires all
        payloads to be validated and resident; it never promotes a partial
        reference as an authoritative render input.
        """

        key = (scene_id, scene_version)
        with self._lock:
            registered = self._manifests.get(key)
            if registered is None:
                raise SnapshotUploadError(
                    "Spatial Scene manifest is absent or has the wrong scene version"
                )
            missing = tuple(
                descriptor.chunk_id
                for descriptor in registered.manifest.chunks
                if (scene_id, scene_version, descriptor.chunk_id) not in self._resident
            )
            if missing:
                raise IncompleteSnapshotUploadError(
                    "Spatial Scene full reference is missing: " + ", ".join(missing)
                )
            descriptors = registered.manifest.chunks
            return SpatialWorkingSet(
                registered.manifest,
                tuple(
                    self._resident[(scene_id, scene_version, descriptor.chunk_id)]
                    for descriptor in descriptors
                ),
                _working_set_token(
                    registered.manifest, camera_binding, descriptors
                ),
            )

    @staticmethod
    def _descriptor(manifest: SpatialSceneManifest, chunk_id: str) -> SpatialChunkDescriptor:
        for descriptor in manifest.chunks:
            if descriptor.chunk_id == chunk_id:
                return descriptor
        raise SnapshotUploadError("Spatial Scene manifest does not contain the chunk")

    def _required_chunks(
        self,
        manifest: SpatialSceneManifest,
        camera_binding: Mapping[str, object],
    ) -> tuple[tuple[SpatialChunkDescriptor, ...], bool]:
        decisions = [
            _intersects_camera_frustum(descriptor.support_bounds, camera_binding)
            for descriptor in manifest.chunks
        ]
        if any(decision is None for decision in decisions):
            return manifest.chunks, True
        required = tuple(
            descriptor
            for descriptor, decision in zip(manifest.chunks, decisions, strict=True)
            if decision
        )
        # An empty selected set cannot currently produce the required complete
        # contributor artifact. Use reference/full mode instead of publishing a
        # partial background-only observation.
        return (required, False) if required else (manifest.chunks, True)

    def _registered_for_stage(self, staged: _StagedChunkUpload) -> _RegisteredManifest:
        registered = self._manifests.get((staged.scene_id, staged.scene_version))
        if registered is None or registered.registration_id != staged.registration_id:
            raise SnapshotUploadError("Spatial Scene upload no longer owns its manifest")
        return registered

    def _missing_staged_chunk_ids(self, staged: _StagedChunkUpload) -> tuple[str, ...]:
        return tuple(
            chunk_id
            for chunk_id in staged.chunk_ids
            if (staged.scene_id, staged.scene_version, chunk_id) not in self._resident
            and not self._staged_chunk_path(staged, chunk_id).is_file()
        )

    def _committed_chunk_path(self, registration_id: str, chunk_id: str) -> Path:
        return self._committed_directory / registration_id / f"{chunk_id}.bin"

    @staticmethod
    def _staged_chunk_path(staged: _StagedChunkUpload, chunk_id: str) -> Path:
        return staged.directory / f"{chunk_id}.bin"

    @staticmethod
    def _map_chunk(
        path: Path,
        descriptor: SpatialChunkDescriptor,
        manifest: SpatialSceneManifest,
    ) -> ResidentSpatialChunk:
        source = path.open("rb")
        try:
            mapping = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
        finally:
            source.close()
        return ResidentSpatialChunk(
            descriptor,
            manifest.sh_float_count_per_gaussian,
            path,
            memoryview(mapping),
            mapping,
        )

    def _discard_staged_locked(self, upload_id: str) -> None:
        staged = self._staged.pop(upload_id, None)
        if staged is not None:
            shutil.rmtree(staged.directory, ignore_errors=True)


def parse_spatial_scene_manifest(value: object) -> SpatialSceneManifest:
    """Parse the small untrusted global manifest; binary payloads stay raw."""

    if not isinstance(value, Mapping):
        raise SnapshotUploadError("Spatial Scene manifest must be an object")
    chunks_value = value.get("chunks")
    if not isinstance(chunks_value, Sequence) or isinstance(chunks_value, (str, bytes)):
        raise SnapshotUploadError("Spatial Scene manifest chunks must be an array")

    def string(name: str) -> str:
        candidate = value.get(name)
        if not isinstance(candidate, str) or not candidate:
            raise SnapshotUploadError(f"Spatial Scene manifest {name} must be a string")
        return candidate

    def integer(name: str) -> int:
        candidate = value.get(name)
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            raise SnapshotUploadError(f"Spatial Scene manifest {name} must be an integer")
        return candidate

    descriptors: list[SpatialChunkDescriptor] = []
    for raw in chunks_value:
        if not isinstance(raw, Mapping):
            raise SnapshotUploadError("Spatial Scene chunk descriptor must be an object")
        support_raw = raw.get("supportBounds")
        if not isinstance(support_raw, Mapping) or not isinstance(support_raw.get("kind"), str):
            raise SnapshotUploadError("Spatial Scene chunk support bounds are absent")
        kind = support_raw["kind"]
        if kind == "empty":
            support = SpatialSupportBounds.empty()
        elif kind == "unbounded":
            support = SpatialSupportBounds.unbounded()
        elif kind == "finite":
            minimum = support_raw.get("min")
            maximum = support_raw.get("max")
            if (
                not isinstance(minimum, Sequence)
                or isinstance(minimum, (str, bytes))
                or not isinstance(maximum, Sequence)
                or isinstance(maximum, (str, bytes))
                or len(minimum) != 3
                or len(maximum) != 3
            ):
                raise SnapshotUploadError("Spatial Scene finite support bounds are invalid")
            try:
                support = SpatialSupportBounds.finite(
                    tuple(float(component) for component in minimum),  # type: ignore[arg-type]
                    tuple(float(component) for component in maximum),  # type: ignore[arg-type]
                )
            except (TypeError, ValueError) as error:
                raise SnapshotUploadError("Spatial Scene finite support bounds are invalid") from error
        else:
            raise SnapshotUploadError("Spatial Scene support bound kind is unsupported")

        def chunk_string(name: str) -> str:
            candidate = raw.get(name)
            if not isinstance(candidate, str) or not candidate:
                raise SnapshotUploadError(f"Spatial Scene chunk {name} must be a string")
            return candidate

        def chunk_integer(name: str) -> int:
            candidate = raw.get(name)
            if isinstance(candidate, bool) or not isinstance(candidate, int):
                raise SnapshotUploadError(f"Spatial Scene chunk {name} must be an integer")
            return candidate

        descriptors.append(SpatialChunkDescriptor(
            chunk_string("chunkId"),
            chunk_string("chunkDigest"),
            chunk_integer("byteLength"),
            chunk_integer("gaussianCount"),
            chunk_integer("globalOrdinalMin"),
            chunk_integer("globalOrdinalMax"),
            support,
        ))
    render_configuration = value.get("renderConfiguration")
    if not isinstance(render_configuration, Mapping):
        raise SnapshotUploadError("Spatial Scene manifest renderConfiguration must be an object")
    manifest = SpatialSceneManifest(
        scene_id=string("sceneId"),
        scene_version=string("sceneVersion"),
        content_digest=string("contentDigest"),
        target_splat_id=string("targetSplatId"),
        total_gaussian_count=integer("totalGaussianCount"),
        coordinate_convention=string("coordinateConvention"),
        stable_id_schema=string("stableIdSchema"),
        attribute_schema=string("attributeSchema"),
        appearance_policy=string("appearancePolicy"),
        render_configuration=dict(render_configuration),
        sh_float_count_per_gaussian=integer("shFloatCountPerGaussian"),
        chunks=tuple(descriptors),
        protocol_version=string("protocolVersion"),
        format=string("format"),
        format_version=integer("formatVersion"),
        chunk_format=string("chunkFormat"),
        chunk_format_version=integer("chunkFormatVersion"),
    )
    _validate_manifest(manifest)
    return manifest
