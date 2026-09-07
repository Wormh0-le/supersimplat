"""Shared canonical JSON digest helper for versioned artifact identity.

Artifact digests are Companion-internal identity: the editor binds them
opaquely and never recomputes them. ``canonical_json_digest`` preserves the
legacy sorted JSON encoding used by the existing PromptState/runtime seams.
Route B artifacts use ``route_b_artifact_digest`` so numeric spelling remains
stable after a browser JSON request/response round trip.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Mapping


def _route_b_update(hasher: "hashlib._Hash", value: object) -> None:
    """Stream the Route B canonical encoding into one digest state."""

    if value is None:
        hasher.update(b"null")
        return
    if isinstance(value, bool):
        hasher.update(b"true" if value else b"false")
        return
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Canonical JSON numbers must be finite")
        # JSON.stringify serializes -0 as 0; discard the sign for parity.
        if number == 0.0:
            number = 0.0
        hasher.update(f"n{struct.pack('>d', number).hex()}".encode("ascii"))
        return
    if isinstance(value, str):
        hasher.update(
            json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        return
    if isinstance(value, (list, tuple)):
        hasher.update(b"[")
        for index, item in enumerate(value):
            if index:
                hasher.update(b",")
            _route_b_update(hasher, item)
        hasher.update(b"]")
        return
    if isinstance(value, Mapping):
        hasher.update(b"{")
        for index, key in enumerate(sorted(value)):
            if not isinstance(key, str):
                raise TypeError("Canonical JSON object keys must be strings")
            if index:
                hasher.update(b",")
            hasher.update(json.dumps(key, ensure_ascii=True).encode("utf-8"))
            hasher.update(b":")
            _route_b_update(hasher, value[key])
        hasher.update(b"}")
        return
    raise TypeError("Canonical JSON payload contains an unsupported value")


def canonical_json_digest(payload: Mapping[str, object]) -> str:
    """Digest one JSON-compatible payload with sorted canonical encoding."""

    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, allow_nan=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def route_b_artifact_digest(payload: Mapping[str, object]) -> str:
    """Digest Route B artifacts invariantly across browser JSON round trips."""

    hasher = hashlib.sha256()
    _route_b_update(hasher, payload)
    return f"sha256:{hasher.hexdigest()}"


__all__ = ["canonical_json_digest", "route_b_artifact_digest"]
