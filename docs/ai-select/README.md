# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendments 007 → 001
→ Final Spec v2.0
→ ADR 0028 → 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

No V2 stage is agent-ready. Runtime remains implemented v1.3.

## Accepted architecture

```text
Seed / TargetScopeState / structured Frontier Debt
→ deterministic bounded q+s Consensus
→ finite layered camera candidates
→ geometry pruning
→ shortlist low-resolution ViewUtilityProbe
→ one winning authoritative View
→ SAM / Evidence / Consensus / Scope
```

The probe is prospective only. It preserves complete-scene occlusion but creates no RGB, Mask, P/N/V, Coverage, Readiness, Candidate, or Native authority. Canonical ranking uses deterministic cost units; measured wall-clock is telemetry/operational safety.

## Documentation lifecycle

Accepted amendments and ADRs are retained and superseded explicitly rather than rewritten. Implemented v1 snapshots remain under `history/v1/`. Superseded unimplemented planning envelopes are deleted and replaced. Context overlays 007–001 are temporary and must be consolidated into root `CONTEXT.md` in one controlled cleanup, then removed.

## Next review

```text
Q9 — V2G / V2I
budgets, structured outcomes, identity hierarchy,
decision journal, replay, cancel/suspend, and Continue Acquisition
```
