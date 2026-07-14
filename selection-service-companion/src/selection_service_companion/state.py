"""Persistent, operator-owned release and model-installation state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
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


def _normalise_sha256(value: str) -> str:
    prefix = "sha256:"
    digest = value[len(prefix):] if value.startswith(prefix) else value
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        raise ValueError("checkpointDigest must be a SHA-256 digest")
    return digest.lower()


@dataclass(frozen=True)
class CompanionState:
    directory: Path

    @property
    def release_path(self) -> Path:
        return self.directory / "release.json"

    @property
    def models_path(self) -> Path:
        return self.directory / "models.json"

    def install_release(self, release: str, lock_digest: str) -> None:
        if not release.strip():
            raise ValueError("release must not be empty")
        if not lock_digest.strip():
            raise ValueError("lock digest must not be empty")
        _write_json(
            self.release_path,
            {
                "release": release,
                "lockDigest": lock_digest,
                "installedAt": datetime.now(UTC).isoformat(),
            },
        )

    def require_release(self) -> dict[str, str]:
        release = _read_json(self.release_path, None)
        if not isinstance(release, dict) or not isinstance(release.get("release"), str):
            raise ValueError("no locked Companion release is installed; run selection-service install first")
        return release

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

    def capabilities(self, allowed_editor_origins: list[str]) -> dict[str, Any]:
        release = self.require_release()
        manifests = [
            {
                "digest": model["digest"],
                "adapterId": model["adapterId"],
                "modelName": model["modelName"],
                "weightsBundled": False,
            }
            for model in self.models()
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
            "capacity": {
                "maximumActiveSessions": 1,
                "activeSessions": 0,
            },
            "allowedEditorOrigins": allowed_editor_origins,
        }
