"""Persistent, operator-owned release and model-installation state."""

from __future__ import annotations

import base64
import binascii
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
from .evidence import ContributorRenderer, build_evidence_snapshot
from .generated_views import (
    GeneratedViewPolicy,
    frame_set_payload,
    public_frame_set_payload,
    quality_gate_tracks,
)
from .gsplat_renderer import production_gsplat_renderer, validate_supported_snapshot
from .masking import (
    MaskProduction,
    MaskSessionError,
    PromptableMaskAdapter,
    RegisteredFrameSet,
    SAM31_RUNTIME_CONFIG_DIGEST,
    Sam3PointMaskAdapter,
    register_frame_set,
)
from .renderer_runtime import (
    EXPECTED_RENDERER_LOCK_DIGEST,
    RendererRuntime,
    current_renderer_runtime,
)


DEFAULT_STATE_DIRECTORY = Path.home() / ".local" / "state" / "supersplat-selection-service"

MODEL_MANIFEST_IDENTITY_FIELDS = (
    "digest",
    "adapterId",
    "modelName",
    "checkpointDigest",
    "sourceCommit",
    "licenseName",
    "licenseUrl",
    "runtimeConfigDigest",
)


@dataclass(frozen=True)
class RegisteredSceneSnapshot:
    """Immutable Scene Snapshot payload cached by its editor-owned version."""

    canonical: str
    stable_ids: tuple[int, ...]
    render_config_version: str


@dataclass(frozen=True)
class GeneratedFrameSetResolution:
    """The cached one-rebuild result for a Generated View preview session."""

    source_frame_set_version: str
    frame_set_version: str
    preliminary_rejections: tuple[dict[str, object], ...]
    attempted_view_ids: tuple[str, ...]


@dataclass
class ActiveMaskSession:
    """The rollback-safe, service-owned state for one mask-session lifetime."""

    frame_set_version: str | None = None
    model_manifest_digest: str | None = None
    open_request_id: str | None = None
    prompt_log_canonical: str = "[]"
    prompt_log_revision: int = 0
    completed_updates: dict[str, str] = field(default_factory=dict)
    completed_update_fingerprints: dict[str, str] = field(default_factory=dict)
    completed_evidence_snapshots: dict[str, str] = field(default_factory=dict)
    completed_preview_publications: dict[str, str] = field(default_factory=dict)
    cancelled_request_ids: set[str] = field(default_factory=set)
    in_flight_request_ids: set[str] = field(default_factory=set)
    generated_resolution: GeneratedFrameSetResolution | None = None
    closing: bool = False


@dataclass(frozen=True)
class PreviewPublication:
    """The sole atomically published preview result for one request."""

    bindings: dict[str, Any]
    frame_set: dict[str, object]
    mask_set: dict[str, Any]
    evidence_snapshot: dict[str, Any]
    coverage_report: dict[str, object]


@dataclass(frozen=True)
class ResolvedPreviewFrameSet:
    """The version-bound inputs used for one atomic preview publication."""

    bindings: dict[str, Any]
    frame_set: RegisteredFrameSet
    preliminary_rejections: tuple[dict[str, object], ...]
    attempted_view_ids: tuple[str, ...]


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
    _frame_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _mask_lock: Lock = field(default_factory=Lock, init=False, repr=False)
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
    _frame_sets: dict[str, RegisteredFrameSet] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _mask_sessions: dict[str, ActiveMaskSession] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    mask_adapters: dict[str, PromptableMaskAdapter] = field(
        default_factory=lambda: {
            "sam3.1": Sam3PointMaskAdapter(),
        },
        repr=False,
    )
    contributor_renderer: ContributorRenderer | None = field(
        default_factory=production_gsplat_renderer,
        repr=False,
    )
    renderer_runtime: RendererRuntime = field(
        default_factory=current_renderer_runtime,
        repr=False,
    )
    generated_view_policy: GeneratedViewPolicy = field(
        default_factory=GeneratedViewPolicy,
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
        if (
            manifest["adapterId"] == "sam3.1"
            and manifest["runtimeConfigDigest"] != SAM31_RUNTIME_CONFIG_DIGEST
        ):
            raise ValueError(
                "the SAM 3.1 Model Manifest runtimeConfigDigest does not match the pinned Companion runtime configuration"
            )

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
        existing = next(
            (available for available in models if available.get("digest") == model["digest"]),
            None,
        )
        if existing is not None:
            if any(
                existing.get(field) != model[field]
                for field in MODEL_MANIFEST_IDENTITY_FIELDS
            ):
                raise ValueError(
                    "a Model Manifest digest is immutable and cannot be reinstalled with different content"
                )
            # A second verified copy of the same checkpoint may restore a
            # missing artifact at a new path, but cannot alter the manifest
            # identity pinned by active sessions.
            model = {
                **existing,
                "weightsPath": model["weightsPath"],
                "weightsBundled": False,
                "installedAt": model["installedAt"],
            }
            models = [
                model if available.get("digest") == model["digest"] else available
                for available in models
            ]
        else:
            models.append(model)
        _write_json(self.models_path, models)
        return model

    def models(self) -> list[dict[str, Any]]:
        models = _read_json(self.models_path, [])
        if not isinstance(models, list):
            return []
        return [model for model in models if isinstance(model, dict)]

    def available_models(self) -> list[dict[str, Any]]:
        return [
            model
            for model in self.models()
            if (
                self._model_artifact_is_current(model)
                and self._model_runtime_configuration_is_current(model)
            )
        ]

    def open_object_selection_session(
        self,
        *,
        frame_set_version: str | None = None,
        model_manifest_digest: str | None = None,
        open_request_id: str | None = None,
    ) -> str | None:
        if (frame_set_version is None) != (model_manifest_digest is None):
            raise MaskSessionError(
                "invalidMaskSession",
                "Object Selection mask sessions require both Frame Set and Model Manifest bindings.",
            )
        if open_request_id is not None and (
            not isinstance(open_request_id, str) or not open_request_id.strip()
        ):
            raise MaskSessionError(
                "invalidMaskSession",
                "Object Selection session openRequestId must be a non-empty string.",
            )
        with self._session_lock:
            if self._active_object_selection_session is not None:
                session_id = self._active_object_selection_session
                with self._mask_lock:
                    session = self._mask_sessions.get(session_id)
                    if (
                        session is not None
                        and not session.closing
                        and open_request_id is not None
                        and session.open_request_id == open_request_id
                    ):
                        if (
                            session.frame_set_version != frame_set_version
                            or session.model_manifest_digest != model_manifest_digest
                        ):
                            raise MaskSessionError(
                                "openRequestIdConflict",
                                "A repeated Object Selection openRequestId must replay its original Frame Set and Model Manifest bindings.",
                            )
                        return session_id
                self._discard_unclaimed_frame_set(frame_set_version)
                return None
            try:
                if frame_set_version is not None:
                    self._require_frame_set(frame_set_version)
                    self._require_mask_adapter(model_manifest_digest)
            except MaskSessionError:
                self._discard_unclaimed_frame_set(frame_set_version)
                raise
            session_id = secrets.token_urlsafe(24)
            self._active_object_selection_session = session_id
            with self._mask_lock:
                self._mask_sessions[session_id] = ActiveMaskSession(
                    frame_set_version=frame_set_version,
                    model_manifest_digest=model_manifest_digest,
                    open_request_id=open_request_id,
                )
        return session_id

    def close_object_selection_session(self, session_id: str) -> bool:
        with self._session_lock:
            return self._close_active_session_locked(session_id)

    def close_object_selection_session_for_open_request(self, open_request_id: str) -> bool:
        """Idempotently close the active session claimed by an open request.

        The browser uses this recovery path when a successful admission response
        is lost before it learns the generated session ID.
        """

        with self._session_lock:
            session_id = self._active_object_selection_session
            if session_id is None:
                return False
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if session is None or session.open_request_id != open_request_id:
                    return False
            return self._close_active_session_locked(session_id)

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

    def register_frame_set(self, payload: dict[str, Any]) -> RegisteredFrameSet:
        """Cache one immutable Frame Set without exposing model-private handles."""

        frame_set = register_frame_set(payload)
        with self._frame_lock:
            existing = self._frame_sets.get(frame_set.frame_set_version)
            if existing is not None and existing.canonical != frame_set.canonical:
                raise MaskSessionError(
                    "immutableFrameSet",
                    "A Frame Set version cannot be registered with different content.",
                )
            self._frame_sets[frame_set.frame_set_version] = frame_set
        return frame_set

    def release_frame_set(self, frame_set_version: str) -> bool:
        """Idempotently release a Frame Set that no session has claimed."""

        with self._session_lock:
            with self._mask_lock:
                if any(
                    session.frame_set_version == frame_set_version
                    for session in self._mask_sessions.values()
                ):
                    return False
            with self._frame_lock:
                self._frame_sets.pop(frame_set_version, None)
        return True

    def update_mask_session(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> dict[str, Any]:
        """Atomically produce or replay one complete Mask Set."""

        mask_set, _ = self._update_mask_session(
            bindings=bindings,
            prompt_log=prompt_log,
            retain_evidence_lease=False,
        )
        return mask_set

    def update_preview(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compatibility view of one complete preview publication."""

        publication = self.update_preview_publication(
            bindings=bindings,
            prompt_log=prompt_log,
        )
        return publication.mask_set, publication.evidence_snapshot

    def update_preview_publication(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> PreviewPublication:
        """Atomically publish Frame Set, Mask Set, Evidence, and coverage.

        Generated View planning is an internal pre-publication step.  The
        editor sees only the final immutable Frame Set and one complete
        Candidate Object Selection result; an Anchor-only intermediate mask is
        never exposed as a candidate.
        """

        resolved = self._effective_preview_frame_set(
            bindings=bindings,
            prompt_log=prompt_log,
        )
        effective_bindings = resolved.bindings
        request_id = self._mask_binding(effective_bindings, "requestId")
        session_id = self._mask_binding(effective_bindings, "sessionId")
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is not None:
                completed = session.completed_preview_publications.get(request_id)
                if completed is not None:
                    return self._preview_publication_from_canonical(completed)

        mask_set, evidence_lease_claimed = self._update_mask_session(
            bindings=effective_bindings,
            prompt_log=prompt_log,
            retain_evidence_lease=True,
            quality_gate=True,
        )
        evidence_snapshot = self._build_evidence_snapshot(
            bindings=effective_bindings,
            mask_set=mask_set,
            evidence_lease_claimed=evidence_lease_claimed,
        )
        renderer = self.contributor_renderer
        if renderer is None:
            # _build_evidence_snapshot has already returned rendererUnavailable,
            # but keep this explicit for future alternate evidence providers.
            raise MaskSessionError(
                "rendererUnavailable",
                "The gsplat/CUDA Contributor renderer is unavailable for Generated View coverage.",
            )
        snapshot = self.scene_snapshot(
            self._mask_binding(effective_bindings, "sceneId"),
            self._mask_binding(effective_bindings, "sceneVersion"),
        )
        if snapshot is None:
            raise MaskSessionError(
                "sceneCacheMiss",
                "The Scene Snapshot is unavailable for Generated View coverage.",
            )
        coverage_report = self.generated_view_policy.coverage_report(
            scene_snapshot=json.loads(snapshot.canonical),
            frame_set=resolved.frame_set,
            mask_set=mask_set,
            renderer=renderer,
            render_config_version=self._mask_binding(
                effective_bindings, "renderConfigVersion"
            ),
            preliminary_rejections=resolved.preliminary_rejections,
            attempted_view_ids=resolved.attempted_view_ids,
            prompt_log=prompt_log if isinstance(prompt_log, list) else (),
        )
        publication = PreviewPublication(
            bindings=dict(effective_bindings),
            frame_set=public_frame_set_payload(resolved.frame_set),
            mask_set=mask_set,
            evidence_snapshot=evidence_snapshot,
            coverage_report=coverage_report,
        )
        canonical = json.dumps(
            {
                "bindings": publication.bindings,
                "frameSet": publication.frame_set,
                "maskSet": publication.mask_set,
                "evidenceSnapshot": publication.evidence_snapshot,
                "coverageReport": publication.coverage_report,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if (
                current is None
                or current.closing
                or request_id in current.cancelled_request_ids
            ):
                raise MaskSessionError(
                    "cancelled",
                    "The Object Selection session closed before preview publication.",
                )
            existing = current.completed_preview_publications.get(request_id)
            if existing is not None:
                return self._preview_publication_from_canonical(existing)
            current.completed_preview_publications[request_id] = canonical
        return publication

    def _effective_preview_frame_set(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
    ) -> ResolvedPreviewFrameSet:
        """Resolve an existing or newly planned Generated View Frame Set.

        The initial Anchor Frame Set remains a cache key for retry recovery.
        Once a generated version has been prepared, a retry may still carry the
        original version and is deterministically upgraded to the cached final
        version before mask publication.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        requested_frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        model_manifest_digest = self._mask_binding(bindings, "modelManifestDigest")
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                raise MaskSessionError(
                    "unknownSession", "The Object Selection mask session is no longer active."
                )
            if session.closing or request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The Object Selection session is closing."
                )
            if session.model_manifest_digest != model_manifest_digest:
                raise MaskSessionError(
                    "staleManifest", "The Model Manifest does not match this Object Selection session."
                )
            generated_resolution = session.generated_resolution
            current_version = session.frame_set_version
        if generated_resolution is not None:
            if requested_frame_set_version not in {
                generated_resolution.frame_set_version,
                generated_resolution.source_frame_set_version,
            }:
                raise MaskSessionError(
                    "staleFrameSet", "The preview request does not match this Generated View Frame Set."
                )
            frame_set = self._require_frame_set(generated_resolution.frame_set_version)
            return ResolvedPreviewFrameSet(
                bindings={
                    **bindings,
                    "frameSetVersion": generated_resolution.frame_set_version,
                },
                frame_set=frame_set,
                preliminary_rejections=generated_resolution.preliminary_rejections,
                attempted_view_ids=generated_resolution.attempted_view_ids or tuple(
                    frame.view_id for frame in frame_set.ordered_views
                ),
            )
        if current_version != requested_frame_set_version:
            raise MaskSessionError(
                "staleFrameSet", "The preview request Frame Set version does not match this Object Selection session."
            )
        anchor_frame_set = self._require_frame_set(requested_frame_set_version)
        renderer = self.contributor_renderer
        if (
            renderer is None
            or not callable(getattr(renderer, "generate_views", None))
            or len(anchor_frame_set.ordered_views) != 1
        ):
            return ResolvedPreviewFrameSet(
                bindings=dict(bindings),
                frame_set=anchor_frame_set,
                preliminary_rejections=(),
                attempted_view_ids=tuple(
                    frame.view_id for frame in anchor_frame_set.ordered_views
                ),
            )

        planning_id = f"{request_id}:generated-view-plan"
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None or session.closing or request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The Object Selection session is closing."
                )
            if session.in_flight_request_ids:
                raise MaskSessionError(
                    "updateInProgress", "Another Object Selection preview update is still in progress."
                )
            session.in_flight_request_ids.add(planning_id)
        try:
            model, adapter = self._require_mask_adapter(model_manifest_digest)
            cancelled = lambda: self._preview_work_cancelled(session_id, request_id)
            production = adapter.produce_tracks(
                model=model,
                frame_set=anchor_frame_set,
                prompt_log=prompt_log,
                cancelled=cancelled,
            )
            preliminary_tracks, _, _ = self._normalise_mask_production(production)
            self._validate_complete_tracks(
                anchor_frame_set,
                prompt_log if isinstance(prompt_log, list) else [],
                preliminary_tracks,
            )
            scene_id = self._mask_binding(bindings, "sceneId")
            scene_version = self._mask_binding(bindings, "sceneVersion")
            snapshot = self.scene_snapshot(scene_id, scene_version)
            if snapshot is None:
                raise MaskSessionError(
                    "sceneCacheMiss", "The Scene Snapshot is unavailable for Generated View planning."
                )
            anchor_mask_set = {"tracks": preliminary_tracks}
            prepared = self.generated_view_policy.prepare(
                scene_snapshot=json.loads(snapshot.canonical),
                anchor_frame_set=anchor_frame_set,
                anchor_mask_set=anchor_mask_set,
                renderer=renderer,
            )
            if prepared.plan.render_config_version != self._mask_binding(
                bindings, "renderConfigVersion"
            ):
                raise MaskSessionError(
                    "renderConfigMismatch",
                    "Generated Views must use the immutable render configuration bound to this preview trial.",
                )
            preliminary_production = adapter.produce_tracks(
                model=model,
                frame_set=prepared.initial_frame_set,
                prompt_log=prompt_log,
                cancelled=cancelled,
            )
            preliminary_tracks, _, _ = self._normalise_mask_production(
                preliminary_production
            )
            self._validate_complete_tracks(
                prepared.initial_frame_set,
                prompt_log if isinstance(prompt_log, list) else [],
                preliminary_tracks,
            )
            preliminary_mask_set = {"tracks": preliminary_tracks}
            selected = self.generated_view_policy.select_frame_set(
                prepared=prepared,
                scene_snapshot=json.loads(snapshot.canonical),
                preliminary_mask_set=preliminary_mask_set,
                renderer=renderer,
                prompt_log=prompt_log if isinstance(prompt_log, list) else (),
            )
            self.register_frame_set(frame_set_payload(selected.frame_set))
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    session is None
                    or session.closing
                    or request_id in session.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled", "The Object Selection session closed during Generated View planning."
                    )
                session.frame_set_version = selected.frame_set.frame_set_version
                session.generated_resolution = GeneratedFrameSetResolution(
                    source_frame_set_version=requested_frame_set_version,
                    frame_set_version=selected.frame_set.frame_set_version,
                    preliminary_rejections=selected.rejected_views,
                    attempted_view_ids=selected.attempted_view_ids,
                )
            return ResolvedPreviewFrameSet(
                bindings={
                    **bindings,
                    "frameSetVersion": selected.frame_set.frame_set_version,
                },
                frame_set=selected.frame_set,
                preliminary_rejections=selected.rejected_views,
                attempted_view_ids=selected.attempted_view_ids,
            )
        finally:
            self._finish_preview_work(session_id, planning_id)

    def _preview_work_cancelled(self, session_id: str, request_id: str) -> bool:
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            return (
                current is None
                or current.closing
                or request_id in current.cancelled_request_ids
            )

    @staticmethod
    def _preview_publication_from_canonical(canonical: str) -> PreviewPublication:
        try:
            value = json.loads(canonical)
            return PreviewPublication(
                bindings=value["bindings"],
                frame_set=value["frameSet"],
                mask_set=value["maskSet"],
                evidence_snapshot=value["evidenceSnapshot"],
                coverage_report=value["coverageReport"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidPreviewPublication", "The cached preview publication is invalid."
            ) from error

    def _update_mask_session(
        self,
        *,
        bindings: dict[str, Any],
        prompt_log: Any,
        retain_evidence_lease: bool,
        quality_gate: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically produce or replay one complete Mask Set.

        Adapter work happens outside the state lock.  No accepted Prompt Log or
        Mask Set is advanced until the adapter has produced every track/view
        outcome and the request is still current.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        model_manifest_digest = self._mask_binding(bindings, "modelManifestDigest")
        prompt_log_revision = self._mask_binding_revision(bindings)
        if not isinstance(prompt_log, list):
            raise MaskSessionError(
                "invalidPromptLog", "The Mask Set update must contain an ordered Prompt Log."
            )
        try:
            prompt_log_canonical = json.dumps(
                prompt_log, separators=(",", ":"), sort_keys=True
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidPromptLog", "The Prompt Log must be JSON-compatible."
            ) from error
        try:
            request_fingerprint = json.dumps(
                {"bindings": bindings, "promptLog": prompt_log},
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidMaskSession", "The Mask Set request bindings must be JSON-compatible."
            ) from error

        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                raise MaskSessionError(
                    "unknownSession", "The Object Selection mask session is no longer active."
                )
            completed = session.completed_updates.get(request_id)
            if completed is not None:
                if session.completed_update_fingerprints.get(request_id) != request_fingerprint:
                    raise MaskSessionError(
                        "requestIdConflict",
                        "A repeated Mask Set request ID must replay its original bindings and Prompt Log.",
                    )
                if retain_evidence_lease:
                    if session.closing or request_id in session.cancelled_request_ids:
                        raise MaskSessionError(
                            "cancelled",
                            "The Object Selection mask session is closing.",
                        )
                    if request_id not in session.completed_evidence_snapshots:
                        if session.in_flight_request_ids:
                            raise MaskSessionError(
                                "updateInProgress",
                                "Another Object Selection preview update is still in progress.",
                            )
                        session.in_flight_request_ids.add(request_id)
                        return json.loads(completed), True
                return json.loads(completed), False
            if session.closing:
                raise MaskSessionError(
                    "cancelled", "The Object Selection mask session is closing."
                )
            if request_id in session.cancelled_request_ids:
                raise MaskSessionError(
                    "cancelled", "The promptable-mask update was cancelled."
                )
            if session.in_flight_request_ids:
                raise MaskSessionError(
                    "updateInProgress", "Another promptable-mask update is still in progress."
                )
            self._validate_mask_session_bindings(
                session,
                frame_set_version=frame_set_version,
                model_manifest_digest=model_manifest_digest,
            )
            self._validate_prompt_log_revision(
                session,
                prompt_log=prompt_log,
                prompt_log_canonical=prompt_log_canonical,
                prompt_log_revision=prompt_log_revision,
            )
            # Claim the singleton preview pipeline before resolving model/frame
            # assets. A concurrent close then retains its lease and cancels
            # this pending work instead of clearing caches beneath a future
            # model or contributor-renderer call or admitting another update.
            session.in_flight_request_ids.add(request_id)

        try:
            frame_set = self._require_frame_set(frame_set_version)
            model, adapter = self._require_mask_adapter(model_manifest_digest)
        except MaskSessionError:
            self._finish_preview_work(session_id, request_id)
            raise

        cancelled_before_inference = False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None or request_id in session.cancelled_request_ids:
                cancelled_before_inference = True
        if cancelled_before_inference:
            self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )

        def cancelled() -> bool:
            with self._mask_lock:
                current = self._mask_sessions.get(session_id)
                return current is None or request_id in current.cancelled_request_ids

        try:
            production = adapter.produce_tracks(
                model=model,
                frame_set=frame_set,
                prompt_log=prompt_log,
                cancelled=cancelled,
            )
            tracks, diagnostics, threshold = self._normalise_mask_production(production)
            self._validate_complete_tracks(frame_set, prompt_log, tracks)
            if quality_gate and self.contributor_renderer is not None:
                scene_id = self._mask_binding(bindings, "sceneId")
                scene_version = self._mask_binding(bindings, "sceneVersion")
                snapshot = self.scene_snapshot(scene_id, scene_version)
                if snapshot is None:
                    raise MaskSessionError(
                        "sceneCacheMiss",
                        "The Scene Snapshot is unavailable for Generated View quality gating.",
                    )
                tracks, quality_rejections = quality_gate_tracks(
                    scene_snapshot=json.loads(snapshot.canonical),
                    frame_set=frame_set,
                    tracks=tracks,
                    renderer=self.contributor_renderer,
                    prompt_log=prompt_log,
                )
                if quality_rejections:
                    diagnostics = {
                        **(diagnostics or {}),
                        "generatedViewQualityRejections": list(quality_rejections),
                    }
            mask_set = {
                "status": "complete",
                "requestId": request_id,
                "sessionId": session_id,
                "promptLogRevision": prompt_log_revision,
                "frameSetVersion": frame_set_version,
                "modelManifestDigest": model_manifest_digest,
                "tracks": tracks,
            }
            if diagnostics is not None:
                mask_set["diagnostics"] = diagnostics
            mask_set["threshold"] = threshold
            mask_set_canonical = json.dumps(
                mask_set, separators=(",", ":"), sort_keys=True
            )
        except MaskSessionError:
            self._finish_preview_work(session_id, request_id)
            raise
        except Exception as error:
            self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "modelFailure",
                "The promptable-mask adapter failed; verify the installed model runtime and retry.",
            ) from error

        cancelled_after_inference = False
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if current is None or request_id in current.cancelled_request_ids:
                if current is not None:
                    current.in_flight_request_ids.discard(request_id)
                cancelled_after_inference = True
            else:
                if not retain_evidence_lease:
                    current.in_flight_request_ids.discard(request_id)
                current.completed_updates[request_id] = mask_set_canonical
                current.completed_update_fingerprints[request_id] = request_fingerprint
                if prompt_log_revision > current.prompt_log_revision:
                    current.prompt_log_canonical = prompt_log_canonical
                    current.prompt_log_revision = prompt_log_revision
                if current.frame_set_version is None:
                    current.frame_set_version = frame_set_version
                if current.model_manifest_digest is None:
                    current.model_manifest_digest = model_manifest_digest
        if cancelled_after_inference:
            self._finish_closing_session_if_drained(session_id)
            raise MaskSessionError(
                "cancelled", "The promptable-mask update was cancelled."
            )
        self._finish_closing_session_if_drained(session_id)
        return json.loads(mask_set_canonical), retain_evidence_lease

    def build_evidence_snapshot(
        self,
        *,
        bindings: dict[str, Any],
        mask_set: dict[str, Any],
    ) -> dict[str, Any]:
        """Lift a complete Mask Set into its immutable Evidence Snapshot."""

        return self._build_evidence_snapshot(
            bindings=bindings,
            mask_set=mask_set,
            evidence_lease_claimed=False,
        )

    def _build_evidence_snapshot(
        self,
        *,
        bindings: dict[str, Any],
        mask_set: dict[str, Any],
        evidence_lease_claimed: bool,
    ) -> dict[str, Any]:
        """Lift one complete Mask Set into its immutable Evidence Snapshot.

        The completed Mask Set remains the only input accepted from the mask
        stage.  The renderer is invoked outside service locks, while a
        canonical snapshot is cached under the request ID so retries cannot
        reinterpret the same request with a later renderer result.
        """

        request_id = self._mask_binding(bindings, "requestId")
        session_id = self._mask_binding(bindings, "sessionId")
        scene_id = self._mask_binding(bindings, "sceneId")
        scene_version = self._mask_binding(bindings, "sceneVersion")
        frame_set_version = self._mask_binding(bindings, "frameSetVersion")
        lease_owned = False
        try:
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    evidence_lease_claimed
                    and session is not None
                    and request_id in session.in_flight_request_ids
                ):
                    lease_owned = True
                if (
                    session is None
                    or session.closing
                    or request_id in session.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled",
                        "The Object Selection session closed before Evidence Snapshot publication.",
                    )
                completed = session.completed_evidence_snapshots.get(request_id)
                if completed is not None:
                    if lease_owned:
                        session.in_flight_request_ids.discard(request_id)
                    return json.loads(completed)
                completed_mask_set = session.completed_updates.get(request_id)
                canonical_mask_set = json.dumps(
                    mask_set, separators=(",", ":"), sort_keys=True
                )
                if completed_mask_set != canonical_mask_set:
                    raise MaskSessionError(
                        "invalidEvidenceSnapshot",
                        "Evidence Policy must lift the complete immutable Mask Set for this request.",
                    )
                if evidence_lease_claimed:
                    if session.in_flight_request_ids != {request_id}:
                        raise MaskSessionError(
                            "updateInProgress",
                            "Another Object Selection preview update is still in progress.",
                        )
                else:
                    if session.in_flight_request_ids:
                        raise MaskSessionError(
                            "updateInProgress",
                            "Another Object Selection preview update is still in progress.",
                        )
                    # Rendering contributor support is part of the same preview
                    # transaction as mask production. Keep capacity and cancellation
                    # ownership until the immutable Evidence Snapshot is published.
                    session.in_flight_request_ids.add(request_id)
                    lease_owned = True
        except MaskSessionError:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise

        try:
            snapshot = self.scene_snapshot(scene_id, scene_version)
            if snapshot is None:
                raise MaskSessionError(
                    "sceneCacheMiss",
                    "The Scene Snapshot is unavailable for Evidence Policy lifting.",
                )
            frame_set = self._require_frame_set(frame_set_version)
            renderer = self._require_contributor_renderer()
            with self._mask_lock:
                current = self._mask_sessions.get(session_id)
                if (
                    current is None
                    or current.closing
                    or request_id in current.cancelled_request_ids
                ):
                    raise MaskSessionError(
                        "cancelled",
                        "The Object Selection session closed before Evidence Snapshot publication.",
                    )

            evidence_snapshot = build_evidence_snapshot(
                bindings=bindings,
                scene_snapshot=json.loads(snapshot.canonical),
                frame_set=frame_set,
                mask_set=mask_set,
                renderer=renderer,
            )
            canonical_evidence_snapshot = json.dumps(
                evidence_snapshot, separators=(",", ":"), sort_keys=True
            )
        except MaskSessionError:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise
        except Exception as error:
            if lease_owned:
                self._finish_preview_work(session_id, request_id)
            raise MaskSessionError(
                "rendererFailure",
                "The Contributor renderer failed; verify the gsplat/CUDA runtime and retry.",
            ) from error

        cancelled_after_lifting = False
        completed_evidence_snapshot: str | None = None
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if (
                current is None
                or current.closing
                or request_id in current.cancelled_request_ids
            ):
                if current is not None:
                    current.in_flight_request_ids.discard(request_id)
                cancelled_after_lifting = True
            else:
                completed_evidence_snapshot = current.completed_evidence_snapshots.get(
                    request_id
                )
                if completed_evidence_snapshot is None:
                    completed_evidence_snapshot = canonical_evidence_snapshot
                    current.completed_evidence_snapshots[request_id] = (
                        completed_evidence_snapshot
                    )
                current.in_flight_request_ids.discard(request_id)
        if cancelled_after_lifting:
            self._finish_closing_session_if_drained(session_id)
            raise MaskSessionError(
                "cancelled",
                "The Object Selection session closed before Evidence Snapshot publication.",
            )
        self._finish_closing_session_if_drained(session_id)
        assert completed_evidence_snapshot is not None
        return json.loads(completed_evidence_snapshot)

    def cancel_mask_update(self, session_id: str, request_id: str) -> bool:
        """Mark a pending update cancelled without changing the last usable Mask Set."""

        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is None:
                return False
            if request_id in session.completed_evidence_snapshots:
                return False
            session.cancelled_request_ids.add(request_id)
            return True

    def release_object_selection_sessions(self) -> None:
        with self._session_lock:
            session_id = self._active_object_selection_session
            if session_id is None:
                with self._mask_lock:
                    self._mask_sessions.clear()
                self._release_all_transient_caches_locked()
                return
            self._close_active_session_locked(session_id)

    def _finish_preview_work(self, session_id: str, request_id: str) -> None:
        with self._mask_lock:
            current = self._mask_sessions.get(session_id)
            if current is not None:
                current.in_flight_request_ids.discard(request_id)
        self._finish_closing_session_if_drained(session_id)

    def _finish_closing_session_if_drained(self, session_id: str) -> None:
        with self._session_lock:
            if self._active_object_selection_session != session_id:
                return
            with self._mask_lock:
                session = self._mask_sessions.get(session_id)
                if (
                    session is None
                    or not session.closing
                    or session.in_flight_request_ids
                ):
                    return
            self._release_active_session_locked(session_id)

    def _close_active_session_locked(self, session_id: str) -> bool:
        """Close the active singleton while holding `_session_lock`."""

        if self._active_object_selection_session != session_id:
            return False
        with self._mask_lock:
            session = self._mask_sessions.get(session_id)
            if session is not None:
                session.closing = True
                session.cancelled_request_ids.update(session.in_flight_request_ids)
                if session.in_flight_request_ids:
                    # Keep the single-session lease until the adapter has
                    # observed cancellation and returned.  Otherwise a second
                    # session could overlap the first GPU request.
                    return True
        self._release_active_session_locked(session_id)
        return True

    def _release_active_session_locked(self, session_id: str) -> None:
        """Clear the singleton session and caches while holding `_session_lock`."""

        if self._active_object_selection_session != session_id:
            return
        with self._mask_lock:
            self._mask_sessions.pop(session_id, None)
        self._release_all_transient_caches_locked()
        self._active_object_selection_session = None

    def _release_all_transient_caches_locked(self) -> None:
        with self._frame_lock:
            self._frame_sets.clear()
        with self._scene_lock:
            self._scene_snapshots.clear()

    def _discard_unclaimed_frame_set(self, frame_set_version: str | None) -> None:
        if frame_set_version is None:
            return
        with self._mask_lock:
            if any(
                session.frame_set_version == frame_set_version
                for session in self._mask_sessions.values()
            ):
                return
        with self._frame_lock:
            self._frame_sets.pop(frame_set_version, None)

    @staticmethod
    def _normalise_mask_production(
        production: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, float]:
        """Freeze generic diagnostics together with the complete tracks."""

        if not isinstance(production, MaskProduction):
            raise MaskSessionError(
                "incompleteMaskSet",
                "The promptable-mask adapter must bind a threshold with its complete Mask Set.",
            )
        tracks = production.tracks
        diagnostics = production.diagnostics
        threshold = production.threshold
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or threshold < 0
            or threshold > 1
        ):
            raise MaskSessionError(
                "invalidThreshold",
                "Promptable-mask adapter threshold must be a finite probability from zero through one.",
        )
        if diagnostics is None:
            return tracks, None, float(threshold)
        if not isinstance(diagnostics, dict):
            raise MaskSessionError(
                "invalidDiagnostics",
                "Promptable-mask adapter diagnostics must be a JSON object.",
            )
        try:
            # JSON round-tripping rejects runtime handles and makes the cached
            # diagnostic payload independent of any mutable adapter object.
            return (
                tracks,
                json.loads(
                    json.dumps(
                        diagnostics,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    )
                ),
                float(threshold),
            )
        except (TypeError, ValueError) as error:
            raise MaskSessionError(
                "invalidDiagnostics",
                "Promptable-mask adapter diagnostics must be JSON-compatible.",
            ) from error

    @staticmethod
    def _model_runtime_configuration_is_current(model: dict[str, Any]) -> bool:
        return (
            model.get("adapterId") != "sam3.1"
            or model.get("runtimeConfigDigest") == SAM31_RUNTIME_CONFIG_DIGEST
        )

    def _require_frame_set(self, frame_set_version: str) -> RegisteredFrameSet:
        with self._frame_lock:
            frame_set = self._frame_sets.get(frame_set_version)
        if frame_set is None:
            raise MaskSessionError(
                "frameSetUnavailable",
                "The requested Frame Set is unavailable; register the immutable Anchor Frame Set and retry.",
            )
        return frame_set

    def _require_mask_adapter(
        self, model_manifest_digest: str | None
    ) -> tuple[dict[str, Any], PromptableMaskAdapter]:
        if not isinstance(model_manifest_digest, str) or not model_manifest_digest:
            raise MaskSessionError(
                "invalidManifest", "A non-empty Model Manifest digest is required."
            )
        model = next(
            (
                available
                for available in self.available_models()
                if available.get("digest") == model_manifest_digest
            ),
            None,
        )
        if model is None:
            raise MaskSessionError(
                "modelUnavailable",
                "The requested Model Manifest is unavailable or its separately installed weights cannot be verified.",
            )
        adapter_id = model.get("adapterId")
        adapter = self.mask_adapters.get(adapter_id)
        if adapter is None:
            raise MaskSessionError(
                "incompatibleManifest",
                "The installed Model Manifest selects a promptable-mask adapter that is unavailable in this Companion runtime.",
            )
        return model, adapter

    @staticmethod
    def _mask_binding(bindings: dict[str, Any], name: str) -> str:
        value = bindings.get(name)
        if not isinstance(value, str) or not value:
            raise MaskSessionError(
                "invalidMaskSession", f"Mask Set {name} must be a non-empty string."
            )
        return value

    @staticmethod
    def _mask_binding_revision(bindings: dict[str, Any]) -> int:
        revision = bindings.get("promptLogRevision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise MaskSessionError(
                "invalidPromptLog", "Mask Set Prompt Log revision must be a non-negative integer."
            )
        return revision

    @staticmethod
    def _validate_mask_session_bindings(
        session: ActiveMaskSession,
        *,
        frame_set_version: str,
        model_manifest_digest: str,
    ) -> None:
        if (
            session.frame_set_version is not None
            and session.frame_set_version != frame_set_version
        ):
            raise MaskSessionError(
                "staleFrameSet",
                "The Mask Set request Frame Set version does not match this Object Selection session.",
            )
        if (
            session.model_manifest_digest is not None
            and session.model_manifest_digest != model_manifest_digest
        ):
            raise MaskSessionError(
                "staleManifest",
                "The Mask Set request Model Manifest does not match this Object Selection session.",
            )

    @staticmethod
    def _validate_prompt_log_revision(
        session: ActiveMaskSession,
        *,
        prompt_log: list[Any],
        prompt_log_canonical: str,
        prompt_log_revision: int,
    ) -> None:
        if prompt_log_revision != len(prompt_log):
            raise MaskSessionError(
                "invalidPromptLog",
                "Prompt Log revision must equal the number of ordered point prompts.",
            )
        if prompt_log_revision < session.prompt_log_revision:
            raise MaskSessionError(
                "stalePromptLog", "The Mask Set request Prompt Log revision is stale."
            )
        if prompt_log_revision == session.prompt_log_revision:
            if prompt_log_canonical != session.prompt_log_canonical:
                raise MaskSessionError(
                    "stalePromptLog",
                    "The Mask Set request changes an already accepted Prompt Log revision.",
                )
            return
        accepted_prompt_log = json.loads(session.prompt_log_canonical)
        if prompt_log[: len(accepted_prompt_log)] != accepted_prompt_log:
            raise MaskSessionError(
                "stalePromptLog",
                "The Mask Set request must replay the accepted Prompt Log before adding prompts.",
            )

    @staticmethod
    def _is_nonnegative_integer(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    @staticmethod
    def _validate_binary_mask(
        binary_mask: Any,
        *,
        width: int,
        height: int,
    ) -> None:
        if (
            not isinstance(binary_mask, dict)
            or binary_mask.get("width") != width
            or binary_mask.get("height") != height
        ):
            raise MaskSessionError(
                "incompleteMaskSet",
                "Accepted Mask Set frames require a mask with the registered Frame Set dimensions.",
            )

        encoding = binary_mask.get("encoding")
        if encoding == "sparse-points-v1":
            foreground_pixels = binary_mask.get("foregroundPixels")
            if not isinstance(foreground_pixels, list) or not foreground_pixels:
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "Sparse Mask Set frames require one or more foreground pixels.",
                )
            previous_pixel = -1
            for pixel in foreground_pixels:
                if (
                    not isinstance(pixel, list)
                    or len(pixel) != 2
                    or not CompanionState._is_nonnegative_integer(pixel[0])
                    or not CompanionState._is_nonnegative_integer(pixel[1])
                ):
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be in-bounds integer coordinates.",
                    )
                x_px, y_px = pixel
                if x_px >= width or y_px >= height:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be in-bounds integer coordinates.",
                    )
                pixel_index = y_px * width + x_px
                if pixel_index <= previous_pixel:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Sparse Mask Set foreground pixels must be sorted and unique.",
                    )
                previous_pixel = pixel_index
            return

        if encoding == "bitset-lsb-v1":
            encoded_data = binary_mask.get("data")
            if not isinstance(encoded_data, str) or not encoded_data:
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set frames require base64 data."
                )
            try:
                data = base64.b64decode(encoded_data, validate=True)
            except (ValueError, binascii.Error) as error:
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set data must be valid base64."
                ) from error
            pixel_count = width * height
            if len(data) != (pixel_count + 7) // 8 or not any(data):
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "Bitset Mask Set data must contain every registered frame pixel and foreground.",
                )
            trailing_bits = pixel_count % 8
            if trailing_bits and data[-1] & ~((1 << trailing_bits) - 1):
                raise MaskSessionError(
                    "incompleteMaskSet", "Bitset Mask Set data sets bits outside the registered frame."
                )
            return

        raise MaskSessionError(
            "incompleteMaskSet", "Accepted Mask Set frames use an unsupported binary mask encoding."
        )

    @staticmethod
    def _validate_complete_tracks(
        frame_set: RegisteredFrameSet,
        prompt_log: list[Any],
        tracks: Any,
    ) -> None:
        if not isinstance(tracks, list) or not tracks:
            raise MaskSessionError(
                "incompleteMaskSet", "The promptable-mask adapter did not return any Mask Tracks."
            )
        primary_frames: list[dict[str, Any]] | None = None
        track_ids: set[str] = set()
        for track in tracks:
            if (
                not isinstance(track, dict)
                or not isinstance(track.get("trackId"), str)
                or not track["trackId"]
                or track["trackId"] in track_ids
                or track.get("role") not in {"include", "exclude"}
                or not isinstance(track.get("frames"), list)
            ):
                raise MaskSessionError(
                    "incompleteMaskSet", "The promptable-mask adapter returned an invalid Mask Track."
                )
            track_ids.add(track["trackId"])
            frames = track["frames"]
            if len(frames) != len(frame_set.ordered_views):
                raise MaskSessionError(
                    "incompleteMaskSet",
                    "The promptable-mask adapter must return every registered Frame Set view in order.",
                )
            for frame, expected_view in zip(frames, frame_set.ordered_views, strict=True):
                if not isinstance(frame, dict) or frame.get("viewId") != expected_view.view_id:
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "The promptable-mask adapter must return every registered Frame Set view in order.",
                    )
                status = frame.get("status")
                if status not in {"accepted", "not_found", "rejected", "error"}:
                    raise MaskSessionError(
                        "incompleteMaskSet", "The promptable-mask adapter returned an unknown frame outcome."
                    )
                if status == "accepted":
                    CompanionState._validate_binary_mask(
                        frame.get("binaryMask"),
                        width=expected_view.width,
                        height=expected_view.height,
                    )
                elif "binaryMask" in frame or not isinstance(frame.get("rejectionReason"), str) or not frame["rejectionReason"].strip():
                    raise MaskSessionError(
                        "incompleteMaskSet",
                        "Neutral Mask Set outcomes require an actionable reason and no binary mask.",
                    )
            if track["trackId"] == "primary":
                if track["role"] != "include" or primary_frames is not None:
                    raise MaskSessionError(
                        "incompleteMaskSet", "A New Mask Set requires one primary include Mask Track."
                    )
                primary_frames = frames

        if primary_frames is None:
            raise MaskSessionError(
                "incompleteMaskSet", "A New Mask Set requires its primary include Mask Track."
            )
        anchor_view_id = CompanionState._prompt_anchor_view(prompt_log)
        anchor_frame = next(
            (frame for frame in primary_frames if frame["viewId"] == anchor_view_id), None
        )
        if anchor_frame is None or anchor_frame["status"] != "accepted":
            raise MaskSessionError(
                "anchorMaskUnavailable",
                "The Anchor View must have an accepted Mask Set outcome before preview can advance.",
            )

    @staticmethod
    def _prompt_anchor_view(prompt_log: list[Any]) -> str:
        for entry in prompt_log:
            if not isinstance(entry, dict) or entry.get("operation") != "New":
                continue
            prompt = entry.get("prompt")
            if isinstance(prompt, dict) and isinstance(prompt.get("viewId"), str):
                return prompt["viewId"]
        raise MaskSessionError(
            "invalidPromptLog", "A New Mask Set requires an Anchor View prompt."
        )

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
        # Registration is the attribution trust boundary. Reject unsupported
        # SuperSplat semantics before the immutable cache can be observed by a
        # mask/evidence request.
        stable_ids = list(validate_supported_snapshot(snapshot))
        render_configuration = snapshot["renderConfiguration"]
        return (
            snapshot["sceneId"],
            snapshot["sceneVersion"],
            stable_ids,
            render_configuration["version"],
        )

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
            if (
                all(key in model for key in ("digest", "adapterId", "modelName"))
                and model["adapterId"] in self.mask_adapters
            )
        ]
        renderer_capability = self._renderer_capability(release)
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serviceBuild": f"selection-service-companion/{PACKAGE_VERSION}+{release['release']}",
            "renderer": renderer_capability,
            "supportedPromptKinds": ["point"],
            "modelManifests": manifests,
            "capacity": self._capacity(),
            "allowedEditorOrigins": allowed_editor_origins,
        }

    def _renderer_capability(self, release: dict[str, str]) -> dict[str, Any]:
        lock_identity_matches = release["lockDigest"] == EXPECTED_RENDERER_LOCK_DIGEST
        runtime = self.renderer_runtime.status()
        renderer = self.contributor_renderer
        renderer_capability: dict[str, Any]
        if not lock_identity_matches:
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "message": "The installed release does not use the canonical Companion lock for this renderer baseline.",
            }
        elif runtime.status != "ready":
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "message": runtime.message
                or "The gsplat/CUDA runtime is unavailable in this Companion environment.",
            }
            if runtime.cuda_version is not None:
                renderer_capability["cudaVersion"] = runtime.cuda_version
        elif renderer is None:
            renderer_capability = {
                "id": "gsplat",
                "status": "unavailable",
                "cudaVersion": runtime.cuda_version,
                "message": "The locked gsplat/CUDA runtime is verified, but this Companion release has no production Contributor renderer.",
            }
        else:
            renderer_capability = {
                "id": renderer.renderer_id,
                "status": "ready",
                "cudaVersion": runtime.cuda_version,
            }
        return renderer_capability

    def _require_contributor_renderer(self) -> ContributorRenderer:
        renderer = self.contributor_renderer
        if renderer is None:
            raise MaskSessionError(
                "rendererUnavailable",
                "The gsplat/CUDA Contributor renderer is unavailable for Anchor Evidence.",
            )
        if not getattr(renderer, "requires_locked_runtime", False):
            return renderer
        try:
            release = self.require_release()
        except ValueError as error:
            raise MaskSessionError("rendererUnavailable", str(error)) from error
        capability = self._renderer_capability(release)
        if capability["status"] != "ready":
            raise MaskSessionError(
                "rendererUnavailable",
                str(capability.get("message") or "The locked gsplat/CUDA renderer is unavailable."),
            )
        return renderer
