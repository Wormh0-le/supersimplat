# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendment 003
→ Amendment 002
→ Amendment 001
→ Final Spec v2.0
→ ADR 0024 / 0023 / 0022 / residual 0021 / 0020
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
→ Core Target
+
seed-independent Discovery Envelope / reversible Frontier
→ Core Coverage + Frontier Debt
→ deterministic bounded q+s Consensus recurrence
→ View Utility and bounded acquisition
```

Current production keeps one Negative Mass channel. Depth-classified N is a nonblocking V2AX experiment.

The accepted consensus recurrence uses:

```text
finite Seed prior + uniform aggregate
→ q^(0), s^(0)
→ lagged Reliability
→ weighted P/N + raw V
→ bounded q/s update
→ one atomic Consensus Revision
→ post-solve Scope Delta
```

## Current documents

- `CURRENT-TICKET-SPEC-MAPPING.md` — authority and lifecycle;
- `V2-REVIEW-STATUS.md` — human implementation gate;
- `TRACEABILITY.md` — amended v2 requirement coverage;
- `manifest.json` — machine-readable control plane;
- `TICKET-GRAPH-V2.md` — provisional parent graph;
- context amendments 003/002/001 — temporary vocabulary overlays;
- `tickets/v2/` — reviewed/review-required parent envelopes.

## Documentation lifecycle

- Amendments and later ADRs supersede conflicting clauses without rewriting accepted history.
- ADR 0021 is retained and marked partially superseded.
- Old V2A/V2B envelope files were deleted because they were unimplemented temporary planning artifacts.
- Implemented v1 control-plane snapshots remain under `history/v1/`.
- Research lives under `docs/research/`; disposable probes under `.scratch/experiments/`.
- Context overlays must eventually be folded into root `CONTEXT.md` in one controlled cleanup, then deleted with superseded definitions.

## Next review

```text
Q5
Consensus readout + Reliability residual:
soft foreground, support/trust, Frontier protection, and pixel gating
```
