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

from .masking import MaskSessionError
from .evidence import selection_result_ids
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


@dataclass(frozen=True)
class PreviewBindings:
    request_id: str
    session_id: str
    target_splat_id: str
    scene_id: str
    scene_version: str
    operation: str
    correction_round: int
    deterministic_seed: str
    prompt_log_revision: int
    frame_set_version: str
    render_config_version: str
    model_manifest_digest: str

    def response_fields(self) -> dict[str, object]:
        return {
            "requestId": self.request_id,
            "sessionId": self.session_id,
            "targetSplatId": self.target_splat_id,
            "sceneId": self.scene_id,
            "sceneVersion": self.scene_version,
            "operation": self.operation,
            "correctionRound": self.correction_round,
            "deterministicSeed": self.deterministic_seed,
            "promptLogRevision": self.prompt_log_revision,
            "frameSetVersion": self.frame_set_version,
            "renderConfigVersion": self.render_config_version,
            "modelManifestDigest": self.model_manifest_digest,
        }


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
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/health":
            try:
                release = self._state.require_release()
            except ValueError as error:
                self._send_unavailable(str(error))
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "serviceBuild": f"selection-service-companion/{release['release']}",
                },
            )
            return
        if self.path == "/capabilities":
            try:
                capabilities = self._state.capabilities(sorted(self._allowed_origins))
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
        if self.path == "/ai-select/anchor-renders":
            self._render_ai_select_anchor()
            return
        if self.path == "/object-selection-sessions":
            self._open_object_selection_session()
            return

        session_id = self._preview_session_id()
        if session_id is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self._preview_object_selection_session(session_id)

    def _render_ai_select_anchor(self) -> None:
        """Route the first v1 AI View through the locked gsplat renderer."""

        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        try:
            request = self._read_json_body()
            response = self._state.render_ai_select_anchor(request)
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "anchorRenderError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        self._send_json(HTTPStatus.OK, response)

    def do_PUT(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        frame_set_version = self._frame_set_version()
        if frame_set_version is not None:
            self._register_frame_set(frame_set_version)
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

    def _open_object_selection_session(self) -> None:
        try:
            request = self._read_json_body()
            self._state.require_release()
            frame_set_version = request.get("frameSetVersion")
            model_manifest_digest = request.get("modelManifestDigest")
            open_request_id = request.get("openRequestId")
            if open_request_id is not None and (
                not isinstance(open_request_id, str) or not open_request_id.strip()
            ):
                raise MaskSessionError(
                    "invalidMaskSession",
                    "Object Selection session openRequestId must be a non-empty string.",
                )
            if frame_set_version is None and model_manifest_digest is None:
                session_id = self._state.open_object_selection_session(
                    open_request_id=open_request_id,
                )
            elif isinstance(frame_set_version, str) and isinstance(
                model_manifest_digest, str
            ):
                session_id = self._state.open_object_selection_session(
                    frame_set_version=frame_set_version,
                    model_manifest_digest=model_manifest_digest,
                    open_request_id=open_request_id,
                )
            else:
                raise MaskSessionError(
                    "invalidMaskSession",
                    "Object Selection mask sessions require both Frame Set and Model Manifest bindings.",
                )
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "maskSessionError",
                    "code": error.code,
                    "message": str(error),
                },
            )
            return
        except ValueError as error:
            self._send_unavailable(str(error))
            return
        if session_id is None:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "busy",
                    "message": "The Companion is already serving one Object Selection Session.",
                },
            )
            return
        self._send_json(
            HTTPStatus.CREATED,
            {
                "status": "accepted",
                "sessionId": session_id,
                **(
                    {"openRequestId": open_request_id}
                    if open_request_id is not None
                    else {}
                ),
            },
        )

    def _preview_object_selection_session(self, session_id: str) -> None:
        if not self._state.has_object_selection_session(session_id):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            request = self._read_json_body()
            bindings = self._preview_bindings(request, session_id)
        except ValueError as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "invalidRequest", "message": str(error)},
            )
            return

        snapshot = self._state.scene_snapshot(
            bindings.scene_id, bindings.scene_version
        )
        if snapshot is None:
            self._send_json(
                HTTPStatus.OK,
                {"status": "sceneCacheMiss", **bindings.response_fields()},
            )
            return
        if snapshot.render_config_version != bindings.render_config_version:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "status": "invalidRequest",
                    "message": "preview render configuration does not match the registered Scene Snapshot",
                },
            )
            return

        try:
            publication = self._state.update_preview_publication(
                bindings=bindings.response_fields(),
                prompt_log=request.get("promptLog"),
            )
        except MaskSessionError as error:
            self._send_json(
                HTTPStatus.CONFLICT,
                {
                    "status": "maskSessionError",
                    "code": error.code,
                    "message": str(error),
                    **bindings.response_fields(),
                },
            )
            return

        selected_ids, uncertain_ids, rejected_ids = selection_result_ids(
            publication.evidence_snapshot
        )
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "complete",
                **publication.bindings,
                "selectedIds": selected_ids,
                "uncertainIds": uncertain_ids,
                "rejectedIds": rejected_ids,
                "frameSet": publication.frame_set,
                "maskSet": publication.mask_set,
                "evidenceSnapshot": publication.evidence_snapshot,
                "coverageReport": self._state.generated_view_policy.public_coverage_report(
                    publication.coverage_report
                ),
            },
        )

    def do_DELETE(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        frame_set_version = self._frame_set_version()
        if frame_set_version is not None:
            if not self._state.release_frame_set(frame_set_version):
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {
                        "status": "frameSetInUse",
                        "message": "The Frame Set belongs to an active Object Selection session.",
                    },
                )
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        open_request_id = self._open_request_id()
        if open_request_id is not None:
            # This is deliberately idempotent: it is the last-resort cleanup
            # path for a session whose successful open response was lost.
            self._state.close_object_selection_session_for_open_request(
                open_request_id
            )
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        preview = self._cancel_preview_request()
        if preview is not None:
            session_id, request_id = preview
            if not self._state.has_object_selection_session(session_id):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not self._state.cancel_mask_update(session_id, request_id):
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {
                        "status": "maskSessionError",
                        "code": "alreadyComplete",
                        "message": "The Mask Set update already completed and cannot be cancelled.",
                        "sessionId": session_id,
                        "requestId": request_id,
                    },
                )
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()
            return

        prefix = "/object-selection-sessions/"
        if not self.path.startswith(prefix):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        session_id = self.path.removeprefix(prefix)
        if not session_id or "/" in session_id or "?" in session_id:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._state.close_object_selection_session(session_id):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def _preview_session_id(self) -> str | None:
        prefix = "/object-selection-sessions/"
        suffix = "/previews"
        if not self.path.startswith(prefix) or not self.path.endswith(suffix):
            return None
        session_id = self.path[len(prefix):-len(suffix)]
        if not session_id or "/" in session_id or "?" in session_id:
            return None
        return unquote(session_id)

    def _cancel_preview_request(self) -> tuple[str, str] | None:
        prefix = "/object-selection-sessions/"
        marker = "/previews/"
        if not self.path.startswith(prefix) or marker not in self.path:
            return None
        session_id, request_id = self.path[len(prefix):].split(marker, 1)
        if not session_id or not request_id or "/" in session_id or "/" in request_id or "?" in request_id:
            return None
        return unquote(session_id), unquote(request_id)

    def _snapshot_key(self) -> tuple[str, str] | None:
        parsed = urlparse(self.path)
        prefix = "/scene-snapshots/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        parts = parsed.path[len(prefix):].split("/")
        if len(parts) != 2 or not all(parts):
            return None
        return unquote(parts[0]), unquote(parts[1])

    def _frame_set_version(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/frame-sets/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        frame_set_version = parsed.path[len(prefix):]
        if not frame_set_version or "/" in frame_set_version:
            return None
        return unquote(frame_set_version)

    def _open_request_id(self) -> str | None:
        parsed = urlparse(self.path)
        prefix = "/object-selection-sessions/open-requests/"
        if parsed.query or not parsed.path.startswith(prefix):
            return None
        encoded_open_request_id = parsed.path[len(prefix):]
        if not encoded_open_request_id or "/" in encoded_open_request_id:
            return None
        return unquote(encoded_open_request_id)

    def _register_frame_set(self, frame_set_version: str) -> None:
        try:
            frame_set = self._read_json_body()
            if frame_set.get("frameSetVersion") != frame_set_version:
                raise MaskSessionError(
                    "invalidFrameSet",
                    "Frame Set route and body bindings must match.",
                )
            self._state.register_frame_set(frame_set)
        except (MaskSessionError, ValueError) as error:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "status": "invalidRequest",
                    "code": error.code if isinstance(error, MaskSessionError) else "invalidFrameSet",
                    "message": str(error),
                },
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {"status": "registered", "frameSetVersion": frame_set_version},
        )

    def _preview_bindings(
        self, request: dict[str, object], route_session_id: str
    ) -> PreviewBindings:
        target = request.get("target")
        if not isinstance(target, dict):
            raise ValueError("preview target must be an object")

        bindings = PreviewBindings(
            request_id=self._request_string(request, "requestId"),
            session_id=self._request_string(request, "sessionId"),
            target_splat_id=self._request_string(request, "targetSplatId"),
            scene_id=self._request_string(request, "sceneId"),
            scene_version=self._request_string(request, "sceneVersion"),
            operation=self._request_string(request, "operation"),
            correction_round=self._request_nonnegative_integer(
                request, "correctionRound"
            ),
            deterministic_seed=self._request_string(request, "deterministicSeed"),
            prompt_log_revision=self._request_nonnegative_integer(
                request, "promptLogRevision"
            ),
            frame_set_version=self._request_string(request, "frameSetVersion"),
            render_config_version=self._request_string(
                request, "renderConfigVersion"
            ),
            model_manifest_digest=self._request_string(
                request, "modelManifestDigest"
            ),
        )
        if bindings.session_id != route_session_id:
            raise ValueError("preview session ID does not match the route")
        if bindings.target_splat_id != self._request_string(target, "targetSplatId"):
            raise ValueError("preview Target Splat ID does not match the target binding")
        if bindings.operation not in {"New", "Add", "Remove", "Refine"}:
            raise ValueError("preview operation is unsupported")
        return bindings

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin in self._allowed_origins

    def _read_json_body(self) -> dict[str, object]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("request Content-Length is invalid") from error
        if content_length <= 0:
            raise ValueError("request must contain a JSON object")
        try:
            value = json.loads(self.rfile.read(content_length))
        except json.JSONDecodeError as error:
            raise ValueError("request body is not valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    @staticmethod
    def _request_string(request: dict[str, object], name: str) -> str:
        value = request.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"preview {name} must be a non-empty string")
        return value

    @staticmethod
    def _request_nonnegative_integer(request: dict[str, object], name: str) -> int:
        value = request.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"preview {name} must be a non-negative integer")
        return value

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_unavailable(self, message: str) -> None:
        self._send_json(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"status": "unavailable", "message": message},
        )

    def _send_json(self, status: HTTPStatus, body: dict[str, object]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
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
