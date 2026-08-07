# Separate Geometry Quality from Route B Prompt Support

Status: accepted

Date: 2026-08-07

The current first-hit TargetGeometryHint can contain a separated support cluster: its robust center/extent are computed from retained samples, but Route B previously consumed the unfiltered points and produced `prompt-inconsistent` masks. The follow-up contract makes the formal `visiblePoints` the retained distinct support, upgrades the Hint schema/policy/digest identity, and separates diagnostic Geometry Quality from per-View Prompt Support.

Prompt Support is globally usable when at least four distinct retained first-hit 3D samples remain and there is no disqualifying geometry reason; a limited hint is promotable only for `separatedSupportFiltered`. Each Generated View must additionally project at least two distinct points into its authoritative image. Other limited reasons fail closed for that View, while Geometry Limited remains visible as a diagnostic and does not itself change Participation.

Old Hint artifacts are incompatible and must be regenerated. The Companion
also verifies the current geometry policy digest and rejects inconsistent
`quality`/`reasons`/`promptSupport` combinations at the Route B trust boundary.
This decision intentionally remains independent SAM 3 Image acquisition: it
does not introduce ArtisanGS-style tracker memory, ordered video, or
multi-view mask aggregation.

## Considered Options

- Keep every limited hint fail-closed: safest, but rejects recoverable separated-support cases.
- Continue using raw visible points: rejected because it caused the observed false Prompt constraints.
- Adopt tracker-based multi-view aggregation: deferred because it changes the current v1 architecture and requires a separate measured ADR.
