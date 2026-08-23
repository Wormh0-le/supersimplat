# AI Select Documentation Migration Status

Status: **v2 current/historical control-plane separation complete**  
Updated: 2026-08-23

## Completed

- Final Spec v2.0 is the current normative target.
- The shipped v1.3 runtime is explicitly distinguished from the v2 target.
- `CURRENT-TICKET-SPEC-MAPPING.md`, `TRACEABILITY.md`, and `manifest.json` now describe v2 planning rather than v1 closure.
- Exact v1 mapping, traceability, manifest and ticket graph snapshots are preserved under `history/v1/`.
- `TICKET-GRAPH.md` is now a compatibility redirect instead of a competing authority.
- `TICKET-GRAPH-V2.md` is marked provisional and review-required.
- `V2-REVIEW-STATUS.md` blocks implementation until ticket-specific review closes.
- agent guidance distinguishes accepted v2 scope, shipped v1 behavior, and explicit cutovers.
- root-level v1 tickets and old audits/evidence are classified as historical.
- temporary executable work remains under `.scratch/experiments/ai-select-v1/`.

## Current state

```text
normative target = Final Spec v2.0
shipped runtime  = Final Spec v1.3 implementation
review frontier  = V2A, then V2C
agent-ready      = none
in flight        = none
```

## Remaining work

This migration does not resolve the substantive V2 design blockers. The next work is the guided review sequence in `V2-REVIEW-STATUS.md`, followed by ticket decomposition, calibration ownership, production-identity promotion and release qualification.

## Deprecation policy

- Historical files are retained only when they preserve implementation or decision provenance.
- Compatibility redirects may remain while external tooling still references them.
- Redundant intermediate narratives should be deleted rather than maintained as a second source of truth.
- A deprecated file must say what replaced it and must not advertise a current frontier.
