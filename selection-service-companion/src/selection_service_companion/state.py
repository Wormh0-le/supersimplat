"""Persistent, operator-owned release and model-installation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
from threading import Lock
from typing import Any

from . import PACKAGE_VERSION, PROTOCOL_VERSION


DEFAULT_STATE_DIRECTORY = Path.home() / ".local" / "state" / "supersplat-selection-service"


@dataclass(frozen=True)
class RegisteredSceneSnapshot:
    """Immutable Scene Snapshot payload cached by its editor-owned version."""

    canonical: str
    stable_ids: tuple[int, ...]
    render_config_version: str


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_sha256(value: str, field_name: str = "checkpointDigest") -> str:
    prefix = "sha256:"
    digest = value[len(prefix):] if value.startswith(prefix) else value
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return digest.lower()


@dataclass
class CompanionState:
    directory: Path
    _session_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _scene_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _active_object_selection_session: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _scene_snapshots: dict[tuple[str, str], RegisteredSceneSnapshot] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    @property
    def release_path(self) -> Path:
        return self.directory / "release.json"

    @property
    def models_path(self) -> Path:
        return self.directory / "models.json"

    def install_release(self, release: str, lock_file: Path) -> None:
        if not release.strip():
            raise ValueError("release must not be empty")
        if not lock_file.is_file():
            raise ValueError(f"locked dependency file does not exist: {lock_file}")

        lock_digest = _sha256(lock_file)
        _write_json(
            self.release_path,
            {
                "release": release,
                "lockDigest": f"sha256:{lock_digest}",
                "lockFile": str(lock_file.resolve()),
                "installedAt": datetime.now(UTC).isoformat(),
            },
        )

    def require_release(self) -> dict[str, str]:
        release = _read_json(self.release_path, None)
        if (
            not isinstance(release, dict)
            or not isinstance(release.get("release"), str)
            or not isinstance(release.get("lockDigest"), str)
            or not isinstance(release.get("lockFile"), str)
        ):
            raise ValueError("no locked Companion release is installed; run selection-service install first")

        lock_file = Path(release["lockFile"])
        try:
            expected_digest = _normalise_sha256(release["lockDigest"], "lockDigest")
            actual_digest = _sha256(lock_file)
        except (OSError, ValueError) as error:
            raise ValueError(
                "the installed Companion release lock cannot be verified; run selection-service install again"
            ) from error
        if actual_digest != expected_digest:
            raise ValueError(
                "the installed Companion release lock changed; run selection-service install again"
            )
        return {
            "release": release["release"],
            "lockDigest": f"sha256:{expected_digest}",
            "lockFile": str(lock_file),
        }

    def install_model(self, manifest_path: Path, weights_path: Path) -> dict[str, Any]:
        if not weights_path.is_file():
            raise ValueError(f"model weights do not exist: {weights_path}")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"model manifest does not exist: {manifest_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"model manifest is not valid JSON: {manifest_path}") from error

        if not isinstance(manifest, dict):
            raise ValueError("model manifest must be a JSON object")

        required = (
            "digest",
            "adapterId",
            "modelName",
            "checkpointDigest",
            "sourceCommit",
            "licenseName",
            "licenseUrl",
            "runtimeConfigDigest",
        )
        missing = [key for key in required if not isinstance(manifest.get(key), str) or not manifest[key].strip()]
        if missing:
            raise ValueError(f"model manifest is missing required fields: {', '.join(missing)}")

        expected_digest = _normalise_sha256(manifest["checkpointDigest"])
        actual_digest = _sha256(weights_path)
        if actual_digest != expected_digest:
            raise ValueError("model checkpoint digest does not match the supplied Model Manifest")

        model = {
            "digest": manifest["digest"],
            "adapterId": manifest["adapterId"],
            "modelName": manifest["modelName"],
            "checkpointDigest": f"sha256:{actual_digest}",
            "sourceCommit": manifest["sourceCommit"],
            "licenseName": manifest["licenseName"],
            "licenseUrl": manifest["licenseUrl"],
            "runtimeConfigDigest": manifest["runtimeConfigDigest"],
            "weightsPath": str(weights_path.resolve()),
            "weightsBundled": False,
            "installedAt": datetime.now(UTC).isoformat(),
        }
        models = self.models()
        models = [existing for existing in models if existing.get("digest") != model["digest"]]
        models.append(model)
        _write_json(self.models_path, models)
        return model

    def models(self) -> list[dict[str, Any]]:
        models = _read_json(self.models_path, [])
        if not isinstance(models, list):
            return []
        return [model for model in models if isinstance(model, dict)]

    def available_models(self) -> list[dict[str, Any]]:
        return [model for model in self.models() if self._model_artifact_is_current(model)]

    def open_object_selection_session(self) -> str | None:
        with self._session_lock:
            if self._active_object_selection_session is not None:
                return None
            self._active_object_selection_session = secrets.token_urlsafe(24)
            return self._active_object_selection_session

    def close_object_selection_session(self, session_id: str) -> bool:
        with self._session_lock:
            if self._active_object_selection_session != session_id:
                return False
            self._active_object_selection_session = None
            return True

    def has_object_selection_session(self, session_id: str) -> bool:
        with self._session_lock:
            return self._active_object_selection_session == session_id

    def register_scene_snapshot(self, snapshot: dict[str, Any]) -> None:
        scene_id, scene_version, stable_ids, render_config_version = self._validate_scene_snapshot(snapshot)
        canonical = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
        key = (scene_id, scene_version)
        with self._scene_lock:
            existing = self._scene_snapshots.get(key)
            if existing is not None and existing.canonical != canonical:
                raise ValueError(
                    "a Scene Snapshot version is immutable and cannot be registered with different content"
                )
            self._scene_snapshots[key] = RegisteredSceneSnapshot(
                canonical=canonical,
                stable_ids=tuple(sorted(stable_ids)),
                render_config_version=render_config_version,
            )

    def scene_snapshot(
        self, scene_id: str, scene_version: str
    ) -> RegisteredSceneSnapshot | None:
        with self._scene_lock:
            return self._scene_snapshots.get((scene_id, scene_version))

    def scene_snapshot_stable_ids(
        self, scene_id: str, scene_version: str
    ) -> tuple[int, ...] | None:
        snapshot = self.scene_snapshot(scene_id, scene_version)
        return snapshot.stable_ids if snapshot is not None else None

    def release_object_selection_sessions(self) -> None:
        with self._session_lock:
            self._active_object_selection_session = None

    def _model_artifact_is_current(self, model: dict[str, Any]) -> bool:
        try:
            weights_path = Path(model["weightsPath"])
            expected_digest = _normalise_sha256(model["checkpointDigest"])
            return weights_path.is_file() and _sha256(weights_path) == expected_digest
        except (KeyError, OSError, TypeError, ValueError):
            return False

    def _validate_scene_snapshot(
        self, snapshot: dict[str, Any]
    ) -> tuple[str, str, list[int], str]:
        required_strings = (
            "protocolVersion",
            "sceneId",
            "sceneVersion",
            "coordinateConvention",
            "attributeSchema",
            "appearancePolicy",
        )
        for name in required_strings:
            if not isinstance(snapshot.get(name), str) or not snapshot[name].strip():
                raise ValueError(f"Scene Snapshot {name} must be a non-empty string")
        if snapshot.get("stableIdSchema") != "uint32":
            raise ValueError("Scene Snapshot Stable Gaussian IDs must use the uint32 schema")
        render_configuration = snapshot.get("renderConfiguration")
        if not isinstance(render_configuration, dict):
            raise ValueError("Scene Snapshot render configuration must be an object")
        render_config_version = render_configuration.get("version")
        rasterizer = render_configuration.get("rasterizer")
        if (
            not isinstance(render_config_version, str)
            or not render_config_version.strip()
            or not isinstance(rasterizer, str)
            or not rasterizer.strip()
            or render_configuration.get("alphaMode") != "opaque-background"
        ):
            raise ValueError("Scene Snapshot render configuration is incomplete")
        sh_bands = render_configuration.get("shBands")
        if isinstance(sh_bands, bool) or not isinstance(sh_bands, int) or sh_bands < 0:
            raise ValueError("Scene Snapshot render configuration shBands must be a non-negative integer")
        self._validate_vector(
            render_configuration.get("backgroundRgba"),
            4,
            "render configuration backgroundRgba",
        )
        gaussian_count = snapshot.get("gaussianCount")
        gaussians = snapshot.get("gaussians")
        if (
            isinstance(gaussian_count, bool)
            or not isinstance(gaussian_count, int)
            or gaussian_count < 0
            or not isinstance(gaussians, list)
            or gaussian_count != len(gaussians)
        ):
            raise ValueError("Scene Snapshot Gaussian count must match its Gaussian records")

        stable_ids: list[int] = []
        for gaussian in gaussians:
            if not isinstance(gaussian, dict):
                raise ValueError("Scene Snapshot Gaussian records must be objects")
            stable_id = gaussian.get("stableId")
            if (
                isinstance(stable_id, bool)
                or not isinstance(stable_id, int)
                or stable_id < 0
                or stable_id > 0xFFFFFFFF
                or stable_id in stable_ids
            ):
                raise ValueError(
                    "Scene Snapshot Stable Gaussian IDs must be unique unsigned 32-bit integers"
                )
            stable_ids.append(stable_id)
            self._validate_vector(gaussian.get("mean"), 3, "mean")
            self._validate_vector(gaussian.get("rotation"), 4, "rotation")
            self._validate_vector(gaussian.get("logScale"), 3, "logScale")
            self._validate_scalar(gaussian.get("logitOpacity"), "logitOpacity")
            self._validate_vector(gaussian.get("dc"), 3, "dc")
            sh = gaussian.get("sh")
            if not isinstance(sh, list):
                raise ValueError("Scene Snapshot Gaussian sh must be a numeric array")
            for value in sh:
                self._validate_scalar(value, "sh")

        return (
            snapshot["sceneId"],
            snapshot["sceneVersion"],
            stable_ids,
            render_config_version,
        )

    @staticmethod
    def _validate_vector(value: Any, length: int, field_name: str) -> None:
        if not isinstance(value, list) or len(value) != length:
            raise ValueError(f"Scene Snapshot Gaussian {field_name} must have {length} numeric values")
        for item in value:
            CompanionState._validate_scalar(item, field_name)

    @staticmethod
    def _validate_scalar(value: Any, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Scene Snapshot Gaussian {field_name} must contain finite numeric values")

    def _capacity(self) -> dict[str, int]:
        with self._session_lock:
            return {
                "maximumActiveSessions": 1,
                "activeSessions": int(
                    self._active_object_selection_session is not None
                ),
            }

    def capabilities(self, allowed_editor_origins: list[str]) -> dict[str, Any]:
        release = self.require_release()
        manifests = [
            {
                "digest": model["digest"],
                "adapterId": model["adapterId"],
                "modelName": model["modelName"],
                "weightsBundled": False,
            }
            for model in self.available_models()
            if all(key in model for key in ("digest", "adapterId", "modelName"))
        ]
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serviceBuild": f"selection-service-companion/{PACKAGE_VERSION}+{release['release']}",
            "renderer": {
                "id": "gsplat",
                "status": "unavailable",
                "message": "The gsplat/CUDA adapter is not installed in this Companion control-plane release.",
            },
            "supportedPromptKinds": ["point"],
            "modelManifests": manifests,
            "capacity": self._capacity(),
            "allowedEditorOrigins": allowed_editor_origins,
        }
