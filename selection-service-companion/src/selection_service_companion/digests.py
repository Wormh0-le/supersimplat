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


def _route_b_canonical_json(value: object) -> str:
    """Encode JSON-compatible values with wire-round-trip-stable numbers.

    The browser parses Companion responses as JavaScript Numbers before it
    sends digest-bound artifacts back. JavaScript therefore turns values such
    as ``1.0`` into ``1`` on the next ``JSON.stringify``. Encoding every
    finite number by its IEEE-754 binary64 bits makes the digest independent of
    that int/float spelling (and matches the browser's single Number value).
    """

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Canonical JSON numbers must be finite")
        # JSON.stringify serializes -0 as 0; discard the sign for parity.
        if number == 0.0:
            number = 0.0
        return f"n{struct.pack('>d', number).hex()}"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_route_b_canonical_json(item) for item in value) + "]"
    if isinstance(value, Mapping):
        entries: list[str] = []
        for key in sorted(value):
            if not isinstance(key, str):
                raise TypeError("Canonical JSON object keys must be strings")
            entries.append(
                f"{json.dumps(key, ensure_ascii=True)}:{_route_b_canonical_json(value[key])}"
            )
        return "{" + ",".join(entries) + "}"
    raise TypeError("Canonical JSON payload contains an unsupported value")


def canonical_json_digest(payload: Mapping[str, object]) -> str:
    """Digest one JSON-compatible payload with sorted canonical encoding."""

    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, allow_nan=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def route_b_artifact_digest(payload: Mapping[str, object]) -> str:
    """Digest Route B artifacts invariantly across browser JSON round trips."""

    encoded = _route_b_canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = ["canonical_json_digest", "route_b_artifact_digest"]
