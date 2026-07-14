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
from urllib.parse import urlparse

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
            "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
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
        if self.path != "/object-selection-sessions":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self._discard_request_body()
        try:
            self._state.require_release()
        except ValueError as error:
            self._send_unavailable(str(error))
            return

        session_id = self._state.open_object_selection_session()
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
            HTTPStatus.CREATED, {"status": "accepted", "sessionId": session_id}
        )

    def do_DELETE(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
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

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin in self._allowed_origins

    def _discard_request_body(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length > 0:
            self.rfile.read(content_length)

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
