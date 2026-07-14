"""Minimal CORS-protected health and capability HTTP control plane."""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ipaddress
import json
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


def _validate_origin(origin: str) -> str:
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError(f"allowlisted editor origin is invalid: {origin}")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(f"allowlisted editor origin is invalid: {origin}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_endpoint(endpoint: str, profile: str) -> tuple[str, int, str]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError("endpoint must be an HTTP(S) origin without a path")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("endpoint must be an origin without credentials, query, or fragment")
    hostname = parsed.hostname
    if profile == "loopback":
        if not _is_loopback(hostname):
            raise ValueError("the loopback profile only permits a loopback endpoint")
    elif profile == "trusted-lan":
        if parsed.scheme != "https":
            raise ValueError("the trusted-LAN profile requires an HTTPS endpoint")
        if _is_loopback(hostname):
            raise ValueError("the trusted-LAN profile requires a non-loopback endpoint")
    else:
        raise ValueError(f"unknown profile: {profile}")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return hostname, port, parsed.scheme


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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origin_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/health":
            release = self._state.require_release()
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "serviceBuild": f"selection-service-companion/{release['release']}"},
            )
            return
        if self.path == "/capabilities":
            self._send_json(HTTPStatus.OK, self._state.capabilities(sorted(self._allowed_origins)))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in self._allowed_origins

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: HTTPStatus, body: dict) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(
    state: CompanionState,
    endpoint: str,
    profile: str,
    allowed_origins: Iterable[str],
    certificate: Path | None = None,
    private_key: Path | None = None,
) -> ThreadingHTTPServer:
    hostname, port, scheme = _parse_endpoint(endpoint, profile)
    origins = {_validate_origin(origin) for origin in allowed_origins}
    if not origins:
        raise ValueError("at least one exact editor origin must be allowlisted")
    if scheme == "https" and (certificate is None or private_key is None):
        raise ValueError("an HTTPS Companion endpoint requires a certificate and private key")

    handler = partial(CompanionRequestHandler, state=state, allowed_origins=origins)
    server = ThreadingHTTPServer((hostname, port), handler)
    if scheme == "https":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
