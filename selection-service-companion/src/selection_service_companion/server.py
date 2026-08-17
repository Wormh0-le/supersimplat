"""Minimal CORS-protected health and capability HTTP control plane."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ipaddress
import json
import socket
import ssl
from typing import Iterable
from urllib.parse import unquote, urlparse

from .anchor_timing import AnchorServerTiming
from .binary_scene_snapshot import (
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    ImmutableSnapshotConflict,
    IncompleteSnapshotUploadError,
    SnapshotUploadError,
    UnknownSnapshotUpload,
    parse_binary_scene_snapshot_manifest,
)
from .masking import MaskSessionError
from .spatial_scene_working_set import (
    MAX_SPATIAL_SCENE_CHUNK_BYTES,
    parse_spatial_scene_manifest,
)
from .state import CompanionState


def _is_loopback(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _is_private_lan_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return (
        address.is_private
        and not address.is_loopback
        and not address.is_unspecified
        and not address.is_multicast
        and not address.is_link_local
    )


def _resolve_private_lan_address(hostname: str) -> str:
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = []
            for result in socket.getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            ):
                address = ipaddress.ip_address(result[4][0])
                if address not in addresses:
                    addresses.append(address)
        except (socket.gaierror, ValueError) as error:
            raise ValueError(
                "the trusted-LAN endpoint host must resolve to a private-network address"
            ) from error

    if not addresses or not all(
        _is_private_lan_address(address) for address in addresses
    ):
        raise ValueError(
            "the trusted-LAN endpoint host must resolve only to private-network addresses"
        )
    return str(addresses[0])


@dataclass(frozen=True)
class Endpoint:
    hostname: str
    port: int
    scheme: str
    address_family: int


def _validate_origin(origin: str) -> str:
    parsed = urlparse(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(f"allowlisted editor origin is invalid: {origin}")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(f"allowlisted editor origin is invalid: {origin}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_endpoint(endpoint: str, profile: str) -> Endpoint:
    parsed = urlparse(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("endpoint must be an HTTP(S) origin without a path")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("endpoint must be an origin without credentials, query, or fragment")
    hostname = parsed.hostname
    if profile == "loopback":
        if not _is_loopback(hostname):
            raise ValueError("the loopback profile only permits a loopback endpoint")
        bind_hostname = hostname
    elif profile == "trusted-lan":
        if parsed.scheme != "https":
            raise ValueError("the trusted-LAN profile requires an HTTPS endpoint")
        if _is_loopback(hostname):
            raise ValueError("the trusted-LAN profile requires a non-loopback endpoint")
        bind_hostname = _resolve_private_lan_address(hostname)
    else:
        raise ValueError(f"unknown profile: {profile}")
    try:
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise ValueError("endpoint has an invalid port") from error
    try:
        address_family = (
            socket.AF_INET6
            if ipaddress.ip_address(bind_hostname).version == 6
            else socket.AF_INET
        )
    except ValueError:
        address_family = socket.AF_INET
    return Endpoint(bind_hostname, port, parsed.scheme, address_family)


class CompanionRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, state: CompanionState, allowed_origins: set[str], **kwargs):
        self._state = state
        self._allowed_origins = allowed_origins
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        # Companion diagnostics remain explicit CLI output rather than noisy
        # access logs that could accidentally be mistaken for a readiness API.
        return

    def do_OPTIONS(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-SceneSnapshot-Chunk-Digest, X-Spatial-Scene-Chunk-Digest",
        )
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/health":
            try:
                health = self._state.health()
            except ValueError as error:
                self._send_unavailable(str(error))
                return
            self._send_json(HTTPStatus.OK, health)
            return
        if self.path == "/capabilities":
            try:
                capabilities = self._state.runtime_profile_capabilities(
                    sorted(self._allowed_origins)
                )
            except ValueError as error:
                self._send_unavailable(str(error))
                return
            self._send_json(HTTPStatus.OK, capabilities)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/scene-snapshot-uploads/v1":
            self._begin_binary_scene_snapshot_upload()
            return
        if self.path == "/spatial-scene-manifests/v1":
            self._register_spatial_scene_manifest()
            return
        if self.path == "/spatial-scene-chunk-uploads/v1":
            self._begin_spatial_scene_chunk_upload()
            return
        binary_commit_upload_id = self._binary_snapshot_commit_upload_id()
        if binary_commit_upload_id is not None:
            self._commit_binary_scene_snapshot_upload(binary_commit_upload_id)
            return
        spatial_commit_upload_id = self._spatial_scene_commit_upload_id()
        if spatial_commit_upload_id is not None:
            self._commit_spatial_scene_chunk_upload(spatial_commit_upload_id)
            return
        if self.path == "/ai-select/anchor-renders":
            self._render_ai_select_anchor()
            return
        if self.path == "/ai-select/view-renders":
            self._render_ai_select_view()
            return
        if self.path == "/ai-select/anchor-support-probes":
            self._probe_ai_select_anchor_support()
            return
        if self.path == "/ai-select/mask-proposals":
            self._produce_ai_select_mask_proposals()
            return
        if self.path == "/ai-select/target-geometry-hints":
            self._produce_ai_select_target_geometry_hint()
            return
        if self.path == "/ai-select/local-key-view-plans":
            self._plan_ai_select_local_key_views()
            return
        if self.path == "/ai-select/generated-view-prompts":
            self._synthesize_ai_select_generated_view_prompt()
            return
        if self.path == "/ai-select/image-instance-masks":
            self._produce_ai_select_image_instance_mask()
            return
        if self.path == "/ai-select/image-instance-mask-reviews":
            self._review_ai_select_image_instance_mask()
            return
        if self.path == "/ai-select/candidate-re-lifts":
            self._produce_ai_select_candidate_re_lift()
            return
        if self.path == "/ai-select/direct-evidence":
            self._produce_ai_select_direct_evidence()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _render_ai_select_anchor(self) -> None:
        """Route the first v1 AI View through the locked gsplat renderer."""

        timing = AnchorServerTiming()
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error), server_timing=timing)
            return
        try:
            request = self._read_json_body()
            response = self._state.render_ai_select_anchor(request, timing=timing)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "anchorRenderError",
                    "code": error.code,
                    "message": str(error),
                },
                server_timing=timing,
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
                server_timing=timing,
            )
            return
        self._send_json(HTTPStatus.OK, response, server_timing=timing)

    def _produce_ai_select_candidate_re_lift(self) -> None:
        """Resolve Included Stable View Evidence and publish one Candidate."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.produce_ai_select_candidate_re_lift(request)
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "candidateReLiftError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _produce_ai_select_direct_evidence(self) -> None:
        """Produce one compact production same-decision P/N/V artifact."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.produce_ai_select_direct_evidence(request)
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "directEvidenceError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _probe_ai_select_anchor_support(self) -> None:
        """Route the versioned mask-conditioned Gaussian support gate."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.probe_ai_select_anchor_support(request)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "supportProbeError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _render_ai_select_view(self) -> None:
        """Route one planner-owned Generated View through the locked renderer."""

        timing = AnchorServerTiming()
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error), server_timing=timing)
            return
        try:
            request = self._read_json_body()
            response = self._state.render_ai_select_view(request, timing=timing)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "viewRenderError",
                    "code": error.code,
                    "message": str(error),
                },
                server_timing=timing,
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
                server_timing=timing,
            )
            return
        self._send_json(HTTPStatus.OK, response, server_timing=timing)

    def _produce_ai_select_target_geometry_hint(self) -> None:
        """Route the compact visible-surface Target Geometry Hint derivation."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.produce_ai_select_target_geometry_hint(request)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "geometryHintError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _plan_ai_select_local_key_views(self) -> None:
        """Route one bounded local Key-View batch planning request."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.plan_ai_select_local_key_views(request)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "keyViewPlanError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _synthesize_ai_select_generated_view_prompt(self) -> None:
        """Route one geometry-guided static-image Prompt synthesis attempt."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.synthesize_ai_select_generated_view_prompt(request)
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "promptSynthesisError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _produce_ai_select_image_instance_mask(self) -> None:
        """Route one independent, single-mask SAM 3 Image inference attempt."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.produce_ai_select_image_instance_mask(request)
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "imageInstanceMaskError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _review_ai_select_image_instance_mask(self) -> None:
        """Route one inference-produced Mask Review; no Stable mutation occurs."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.review_ai_select_image_instance_mask(request)
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "imageInstanceMaskReviewError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def _produce_ai_select_mask_proposals(self) -> None:
        """Route one bound PromptState proposal request through the adapter."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.produce_ai_select_mask(request)
        except MaskSessionError as error:
            # MaskSessionError subclasses ValueError, so the actionable 409
            # branch must be matched before the generic 400 validation branch.
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "maskProposalError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def do_PUT(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        spatial_chunk = self._spatial_scene_chunk()
        if spatial_chunk is not None:
            self._upload_spatial_scene_chunk(*spatial_chunk)
            return
        binary_chunk = self._binary_snapshot_chunk()
        if binary_chunk is not None:
            self._upload_binary_scene_snapshot_chunk(*binary_chunk)
            return
        snapshot_key = self._snapshot_key()
        if snapshot_key is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            snapshot = self._read_json_body()
            if (
                snapshot.get("sceneId") != snapshot_key[0]
                or snapshot.get("sceneVersion") != snapshot_key[1]
            ):
                raise ValueError("Scene Snapshot route and body bindings must match")
            self._state.register_scene_snapshot(snapshot)
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "registered",
                "sceneId": snapshot_key[0],
                "sceneVersion": snapshot_key[1],
            },
        )

    def _begin_binary_scene_snapshot_upload(self) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            manifest = parse_binary_scene_snapshot_manifest(
                self._read_json_body(maximum_bytes=2 * 1024 * 1024)
            )
            self._state.cleanup_expired_binary_scene_snapshot_uploads()
            admission = self._state.begin_binary_scene_snapshot_upload(manifest)
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        except ValueError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidRequest", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": admission.status,
                "missingChunkIndices": list(admission.missing_chunk_indices),
                **(
                    {"uploadId": admission.upload_id}
                    if admission.upload_id is not None
                    else {}
                ),
            },
        )

    def _register_spatial_scene_manifest(self) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            manifest = parse_spatial_scene_manifest(
                self._read_json_body(maximum_bytes=2 * 1024 * 1024)
            )
            self._state.cleanup_expired_spatial_scene_chunk_uploads()
            registration = self._state.register_spatial_scene_manifest(manifest)
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidManifest", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": registration.status,
                "registrationId": registration.registration_id,
                "sceneId": registration.scene_id,
                "sceneVersion": registration.scene_version,
                "contentDigest": registration.content_digest,
            },
        )

    def _begin_spatial_scene_chunk_upload(self) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body(maximum_bytes=2 * 1024 * 1024)
            scene_id = request.get("sceneId")
            scene_version = request.get("sceneVersion")
            chunk_ids = request.get("chunkIds")
            if (
                not isinstance(scene_id, str)
                or not scene_id
                or not isinstance(scene_version, str)
                or not scene_version
                or not isinstance(chunk_ids, list)
                or any(not isinstance(chunk_id, str) for chunk_id in chunk_ids)
            ):
                raise SnapshotUploadError("Spatial Scene chunk upload bindings are invalid")
            self._state.cleanup_expired_spatial_scene_chunk_uploads()
            admission = self._state.begin_spatial_scene_chunk_upload(
                scene_id, scene_version, tuple(chunk_ids)
            )
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": admission.status,
                "missingChunkIds": list(admission.missing_chunk_ids),
                **(
                    {"uploadId": admission.upload_id}
                    if admission.upload_id is not None
                    else {}
                ),
            },
        )

    def _upload_spatial_scene_chunk(self, upload_id: str, chunk_id: str) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/octet-stream":
                raise SnapshotUploadError(
                    "Spatial Scene chunks must use application/octet-stream"
                )
            digest = self.headers.get("X-Spatial-Scene-Chunk-Digest")
            if not isinstance(digest, str) or not digest:
                raise SnapshotUploadError("Spatial Scene chunk digest header is required")
            status = self._state.accept_spatial_scene_chunk(
                upload_id,
                chunk_id,
                self._read_binary_body(MAX_SPATIAL_SCENE_CHUNK_BYTES),
                digest,
            )
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except UnknownSnapshotUpload as error:
            self._send_binary_snapshot_error(
                HTTPStatus.NOT_FOUND, "uploadMissing", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {"status": status, "uploadId": upload_id, "chunkId": chunk_id},
        )

    def _commit_spatial_scene_chunk_upload(self, upload_id: str) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            self._read_json_body(maximum_bytes=1024)
            commit = self._state.commit_spatial_scene_chunk_upload(upload_id)
        except IncompleteSnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "incompleteUpload", str(error)
            )
            return
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except UnknownSnapshotUpload as error:
            self._send_binary_snapshot_error(
                HTTPStatus.NOT_FOUND, "uploadMissing", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": commit.status,
                "sceneId": commit.scene_id,
                "sceneVersion": commit.scene_version,
                "committedChunkIds": list(commit.committed_chunk_ids),
            },
        )

    def _upload_binary_scene_snapshot_chunk(
        self, upload_id: str, index: int
    ) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/octet-stream":
                raise SnapshotUploadError(
                    "Binary Scene Snapshot chunks must use application/octet-stream"
                )
            digest = self.headers.get("X-SceneSnapshot-Chunk-Digest")
            if not isinstance(digest, str) or not digest:
                raise SnapshotUploadError(
                    "Binary Scene Snapshot chunk digest header is required"
                )
            status = self._state.accept_binary_scene_snapshot_chunk(
                upload_id,
                index,
                self._read_binary_body(MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES),
                digest,
            )
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except UnknownSnapshotUpload as error:
            self._send_binary_snapshot_error(
                HTTPStatus.NOT_FOUND, "uploadMissing", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {"status": status, "uploadId": upload_id, "index": index},
        )

    def _commit_binary_scene_snapshot_upload(self, upload_id: str) -> None:
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            self._read_json_body(maximum_bytes=1024)
            commit = self._state.commit_binary_scene_snapshot_upload(upload_id)
        except IncompleteSnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "incompleteUpload", str(error)
            )
            return
        except ImmutableSnapshotConflict as error:
            self._send_binary_snapshot_error(
                HTTPStatus.CONFLICT, "immutableConflict", str(error)
            )
            return
        except UnknownSnapshotUpload as error:
            self._send_binary_snapshot_error(
                HTTPStatus.NOT_FOUND, "uploadMissing", str(error)
            )
            return
        except SnapshotUploadError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidUpload", str(error)
            )
            return
        except ValueError as error:
            self._send_binary_snapshot_error(
                HTTPStatus.BAD_REQUEST, "invalidRequest", str(error)
            )
            return
        snapshot = commit.snapshot
        self._send_json(
            HTTPStatus.OK,
            {
                "status": commit.status,
                "sceneId": snapshot.scene_id,
                "sceneVersion": snapshot.scene_version,
                "contentDigest": snapshot.content_digest,
            },
        )

    def do_DELETE(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        target_prefix = "/ai-select/targets/"
        if self.path.startswith(target_prefix):
            target_context_id = unquote(self.path[len(target_prefix):])
            try:
                self._state.dispose_ai_select_target(target_context_id)
            except ValueError as error:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"status": "invalidRequest", "message": str(error)},
                )
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        binary_upload_id = self._binary_snapshot_upload_id()
        if binary_upload_id is not None:
            self._state.abort_binary_scene_snapshot_upload(binary_upload_id)
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        spatial_upload_id = self._spatial_scene_upload_id()
        if spatial_upload_id is not None:
            self._state.abort_spatial_scene_chunk_upload(spatial_upload_id)
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        spatial_registration_id = self._spatial_scene_manifest_registration_id()
        if spatial_registration_id is not None:
            self._state.release_spatial_scene_manifest(spatial_registration_id)
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _snapshot_key(self) -> tuple[str, str] | None:
        parsed = urlparse(self.path)
        prefix = "/scene-snapshots/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        parts = parsed.path[len(prefix):].split("/")
        if len(parts) != 2 or not all(parts):
            return None
        return unquote(parts[0]), unquote(parts[1])

    def _binary_snapshot_chunk(self) -> tuple[str, int] | None:
        parsed = urlparse(self.path)
        prefix = "/scene-snapshot-uploads/v1/"
        suffix = "/chunks/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        remainder = parsed.path[len(prefix):]
        if suffix not in remainder:
            return None
        upload_id, encoded_index = remainder.split(suffix, 1)
        if (
            not upload_id
            or "/" in upload_id
            or not encoded_index
            or "/" in encoded_index
            or not encoded_index.isdecimal()
        ):
            return None
        return unquote(upload_id), int(encoded_index)

    def _binary_snapshot_commit_upload_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/scene-snapshot-uploads/v1/"
        suffix = "/commit"
        if (
            parsed.query
            or not parsed.path.startswith(prefix)
            or not parsed.path.endswith(suffix)
        ):
            return None
        upload_id = parsed.path[len(prefix):-len(suffix)]
        if not upload_id or "/" in upload_id:
            return None
        return unquote(upload_id)

    def _binary_snapshot_upload_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/scene-snapshot-uploads/v1/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        upload_id = parsed.path[len(prefix):]
        if not upload_id or "/" in upload_id:
            return None
        return unquote(upload_id)

    def _spatial_scene_chunk(self) -> tuple[str, str] | None:
        parsed = urlparse(self.path)
        prefix = "/spatial-scene-chunk-uploads/v1/"
        suffix = "/chunks/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        remainder = parsed.path[len(prefix):]
        if suffix not in remainder:
            return None
        upload_id, encoded_chunk_id = remainder.split(suffix, 1)
        if (
            not upload_id
            or "/" in upload_id
            or not encoded_chunk_id
            or "/" in encoded_chunk_id
        ):
            return None
        return unquote(upload_id), unquote(encoded_chunk_id)

    def _spatial_scene_commit_upload_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/spatial-scene-chunk-uploads/v1/"
        suffix = "/commit"
        if (
            parsed.query
            or not parsed.path.startswith(prefix)
            or not parsed.path.endswith(suffix)
        ):
            return None
        upload_id = parsed.path[len(prefix):-len(suffix)]
        if not upload_id or "/" in upload_id:
            return None
        return unquote(upload_id)

    def _spatial_scene_upload_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/spatial-scene-chunk-uploads/v1/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        upload_id = parsed.path[len(prefix):]
        if not upload_id or "/" in upload_id:
            return None
        return unquote(upload_id)

    def _spatial_scene_manifest_registration_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/spatial-scene-manifests/v1/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        registration_id = parsed.path[len(prefix):]
        if not registration_id or "/" in registration_id:
            return None
        return unquote(registration_id)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin in self._allowed_origins

    def _read_json_body(self, *, maximum_bytes: int | None = None) -> dict[str, object]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("request Content-Length is invalid") from error
        if content_length <= 0:
            raise ValueError("request must contain a JSON object")
        if maximum_bytes is not None and content_length > maximum_bytes:
            raise ValueError("request body exceeds the route limit")
        try:
            value = json.loads(self.rfile.read(content_length))
        except json.JSONDecodeError as error:
            raise ValueError("request body is not valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def _read_binary_body(self, maximum_bytes: int) -> bytes:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise SnapshotUploadError("Binary Scene Snapshot chunk Content-Length is invalid") from error
        if content_length <= 0 or content_length > maximum_bytes:
            raise SnapshotUploadError(
                "Binary Scene Snapshot chunk exceeds the bounded byte limit"
            )
        payload = self.rfile.read(content_length)
        if len(payload) != content_length:
            raise SnapshotUploadError("Binary Scene Snapshot chunk body is truncated")
        return payload

    def _send_binary_snapshot_error(
        self, status: HTTPStatus, code: str, message: str
    ) -> None:
        self._send_json(status, {"status": "snapshotUploadError", "code": code, "message": message})

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_unavailable(
        self, message: str, *, server_timing: AnchorServerTiming | None = None
    ) -> None:
        self._send_json(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"status": "unavailable", "message": message},
            server_timing=server_timing,
        )

    def _send_json(
        self,
        status: HTTPStatus,
        body: dict[str, object],
        *,
        server_timing: AnchorServerTiming | None = None,
    ) -> None:
        if server_timing is None:
            encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        else:
            with server_timing.measure('json-base64'):
                encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        if server_timing is not None:
            self.send_header("Server-Timing", server_timing.header_value())
            if self.headers.get("Origin") is not None:
                self.send_header("Access-Control-Expose-Headers", "Server-Timing")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ThreadingIPv6HTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def create_server(
    state: CompanionState,
    endpoint: str,
    profile: str,
    allowed_origins: Iterable[str],
    certificate: Path | None = None,
    private_key: Path | None = None,
) -> ThreadingHTTPServer:
    parsed_endpoint = _parse_endpoint(endpoint, profile)
    origins = {_validate_origin(origin) for origin in allowed_origins}
    if not origins:
        raise ValueError("at least one exact editor origin must be allowlisted")
    if parsed_endpoint.scheme == "https":
        if certificate is None or private_key is None:
            raise ValueError("an HTTPS Companion endpoint requires a certificate and private key")
        if not certificate.is_file() or not private_key.is_file():
            raise ValueError("the HTTPS Companion certificate and private key must exist before binding")

    handler = partial(CompanionRequestHandler, state=state, allowed_origins=origins)
    server_class = (
        ThreadingIPv6HTTPServer
        if parsed_endpoint.address_family == socket.AF_INET6
        else ThreadingHTTPServer
    )
    server = server_class((parsed_endpoint.hostname, parsed_endpoint.port), handler)
    if parsed_endpoint.scheme == "https":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        try:
            context.load_cert_chain(certificate, private_key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        except Exception:
            server.server_close()
            raise
    return server
