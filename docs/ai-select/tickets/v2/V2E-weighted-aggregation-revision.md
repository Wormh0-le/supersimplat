# V2E — Weighted aggregation revision

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2A, V2B, V2D
Blocks: V2H

## Final Spec v2.0 mapping

- Final Spec v2.0 §7.3, §4 (Core Target denominator), §5 (classified N)
- Carry-over: existing aggregation policy seam
  (`reference_gaussian_evidence_aggregation.py` — today one-shot at Re-Lift)

## Goal

Revise aggregation to consume depth-classified N and view-level reliability
weights over the seed-based Core Target denominator, revising incrementally
after each Included publication.

## Inputs / preconditions

- Immutable per-View Direct P/N/V including depth-classified N (V2A);
- view-level reliability weights (V2D);
- Core Target denominator state (V2B);
- existing aggregation policy + readiness consumption (Tickets 13/14C/20/21).

## Outputs / handoff

- Revised versioned aggregation policy consuming classified N + reliability
  weights, identity `experimental-v*` staged;
- incremental revision path invoked after each Included publication (today's
  one-shot Re-Lift aggregation generalizes into loop-scoped revision);
- readiness revision consumption: Lift Readiness recomputed over the revised
  aggregate without taking over publication authority;
- Missing/unusable observation semantics preserved as unobserved.

## Acceptance criteria

- [ ] Aggregation consumes immutable per-View P/N/V with depth-classified N
      and view-level reliability weights; P/N weighting only — raw V remains
      unweighted.
- [ ] Missing/unusable observations remain unobserved, never negative
      evidence.
- [ ] Incremental revision after every Included publication produces the same
      result as full recomputation (equivalence test).
- [ ] Denominator is the seed-based monotonic Core Target; shadow-phase dual
      coverage (seed vs whole-Splat) remains reportable.
- [ ] Revised policy identity is exact-key validated and checksum bound,
      staged `experimental-v*`.
- [ ] v1.3 Re-Lift-time aggregation behavior is preserved until supersession
      cutover (no silent semantic drift).

## Validation

- Incremental-vs-full recomputation equivalence tests;
- classified-N consumption tests (front/behind classes weighted distinctly);
- reliability-weight application tests including V-unweighted assertion;
- identity fail-closed tests.

## Non-goals

- No readiness threshold change (V2G/calibration), no publication semantics
  (V2H), no consensus computation (V2C).
