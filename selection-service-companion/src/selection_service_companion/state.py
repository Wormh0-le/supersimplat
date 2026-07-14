"""Persistent, operator-owned release and model-installation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
from threading import Lock
from typing import Any

from . import PACKAGE_VERSION, PROTOCOL_VERSION


DEFAULT_STATE_DIRECTORY = Path.home() / ".local" / "state" / "supersplat-selection-service"


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
    _active_object_selection_session: str | None = field(
        default=None,
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
