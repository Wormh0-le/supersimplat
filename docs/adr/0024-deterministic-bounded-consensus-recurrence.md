# ADR 0024: Adopt a deterministic bounded q+s consensus recurrence

Status: accepted 2026-08-23

Date: 2026-08-23

## Context

The accepted v2 architecture contains a feedback loop:

```text
Consensus
→ soft-mask residual
→ Observation Reliability
→ weighted aggregation
→ revised Consensus
```

The prior documents did not define the state representation, initialization, ordering, convergence, relationship to Core/Frontier revision, or whether View arrival order could change the final result.

A single hard Selected/Rejected/Uncertain state cannot distinguish weakly observed unknown support from strongly observed conflicting support. A one-step update per arriving View is cheap but makes the canonical result order-dependent. Full leave-one-out reliability is statistically attractive but too expensive as the initial interactive production path.

## Decision

1. Represent Provisional Consensus with continuous membership tendency `q ∈ [0,1]` and independent support/knownness `s ∈ [0,1]`, bound to an exact frozen scope revision.
2. Compute the canonical result by a deterministic bounded batch recurrence over the exact current Included Stable observation set.
3. Initialize from a finite Conservative Seed prior plus a uniform aggregate over all current Included Evidence. Seed influence must be bounded and diminish relative to real Evidence.
4. Reliability iteration `r` consumes only consensus iteration `r-1`; same-round feedback is forbidden.
5. Reliability weights semantic P/N only. Raw V remains unweighted.
6. One external input change produces at most one public atomic Consensus Revision. Private bounded Solver Iterations do not become product-visible revisions.
7. Freeze Core/Envelope/Frontier during the solve. Derive and atomically commit scope deltas only after the solve; newly committed scope affects the next solve.
8. Warm starts and incremental caches are optimizations. Canonical cold full solve equivalence is the semantic authority.
9. Non-convergence fails closed as Limited/non-converged and cannot publish a Ready Candidate.
10. Exact soft-mask readout, residual equation, transforms, convergence thresholds, and maximum iterations remain subsequent review/calibration decisions.

## Consequences

- Unknown and conflict become distinguishable through `(q,s)`.
- Canonical output is independent of View arrival order and cache history.
- The internal solve may cost several iterations per observation-set revision, so strict bounds and profiling are required.
- Scope updates cannot recursively amplify consensus inside one revision.
- Incremental performance implementations require cold-solve equivalence tests.
- The prior Candidate and valid observation artifacts survive non-convergence.
- V2C, V2D, and V2E remain parent envelopes and are not yet agent-ready.

## Rejected alternatives

- Hard four-state consensus mapped directly to a soft mask: too discontinuous and conflates unknown with conflict.
- One lagged update per arriving View as canonical truth: order-dependent.
- Production leave-one-out consensus per View: retained as a possible offline reference, not the initial production contract.
