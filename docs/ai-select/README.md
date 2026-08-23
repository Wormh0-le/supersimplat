# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendment 004
→ Amendment 003 → Amendment 002 → Amendment 001
→ Final Spec v2.0
→ ADR 0025 / 0024 / 0023 / 0022 / residual 0021 / 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

No V2 stage is agent-ready. Runtime remains the implemented v1.3 baseline.

## Accepted product architecture

```text
Anchor
→ automatic acquisition by default
→ Expert Recovery when needed

Conservative Seed
→ Core + seed-independent Envelope/Frontier
→ deterministic bounded q+s Consensus
→ same-decision P/K/C/F readout
→ trusted regional Reliability
→ weighted P/N + raw V
→ View Utility and bounded acquisition
```

Production keeps one Negative Mass channel. Classified N and leave-one-out Reliability are nonblocking experiment/reference paths.

## Current documents

- `CURRENT-TICKET-SPEC-MAPPING.md` — authority and lifecycle;
- `V2-REVIEW-STATUS.md` — human implementation gate;
- `TRACEABILITY.md` — amended v2 requirement coverage;
- `manifest.json` — machine-readable control plane;
- `TICKET-GRAPH-V2.md` — provisional parent graph;
- context amendments 004/003/002/001 — temporary vocabulary overlays;
- `tickets/v2/` — reviewed/review-required parent envelopes.

## Documentation lifecycle

- Amendments and later ADRs supersede conflicting clauses without rewriting accepted history.
- ADR 0021 is retained and marked partially superseded.
- Old unimplemented V2A/V2B envelopes were deleted because they were temporary planning artifacts.
- Implemented v1 snapshots remain under `history/v1/`.
- Research lives under `docs/research/`; disposable probes under `.scratch/experiments/`.
- Context overlays must eventually be folded into root `CONTEXT.md` in one controlled cleanup, then deleted with superseded definitions.

## Next review

```text
Q6
q/s initialization and update
+ residual-to-Reliability normalization
+ convergence contract
```
