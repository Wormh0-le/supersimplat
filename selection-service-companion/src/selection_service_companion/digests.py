"""Shared canonical JSON digest helper for versioned artifact identity.

Artifact digests are Companion-internal identity: the editor binds them
opaquely and never recomputes them. The canonical encoding is deterministic
for every JSON-compatible payload the Companion itself produced (sorted keys,
tight separators, no NaN/Infinity), so a digest replays exactly across the
admission/replay boundary and across a request/response JSON round trip.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping


def canonical_json_digest(payload: Mapping[str, object]) -> str:
    """Digest one JSON-compatible payload with sorted canonical encoding."""

    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, allow_nan=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = ["canonical_json_digest"]
