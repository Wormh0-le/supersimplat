# V2C — Provisional Consensus state + soft-mask readout

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: none
Blocks: V2D

## Final Spec v2.0 mapping

- Final Spec v2.0 §5 (soft-mask readout), §7.1, §3 (Companion ownership);
  `CONTEXT.md` non-normative "Provisional 3D Consensus" / "Evidence-Internal
  Depth"

## Goal

Introduce the Companion-local disposable Provisional 3D Consensus state,
revised once per Included publication, plus its kernel-side consensus
soft-mask readout for residual computation.

## Inputs / preconditions

- Included Stable Masks + Participation (v1.3 semantics carried over);
- same-decision raster family (Ticket 20);
- loop-scoped cache seam keyed by target + dependency identity.

## Outputs / handoff

- Per-Gaussian consensus state maintained in the Companion, alive across
  requests, disposable by policy;
- consensus-state-weighted colored pass inside the same-decision kernel
  family, producing the soft mask readout consumed Companion-side only;
- revision entry point invoked exactly once per Included publication;
- staleness propagation: new Views, Stable Mask revisions or Participation
  changes make dependent consensus/reliability/readiness stale;
- replay support via Companion-side digest/journal.

## Acceptance criteria

- [ ] Soft-mask readout is computed inside the same-decision raster family;
      no independent approximate re-rasterization exists.
- [ ] Consensus is Companion-local disposable derived state: feeds planner
      utility, reliability and weighted aggregation ONLY.
- [ ] It can never execute Native Set/Add/Remove/Intersect, forms no
      cross-target persistent history, and is never an AI Candidate.
- [ ] It does not cross the Browser/Companion boundary as a formal artifact.
- [ ] Cache is keyed by target + dependency identity; incompatible identity
      invalidates deterministically.
- [ ] Exactly one revision per Included publication; replay reconstructs
      equivalent state from digests/journal.
- [ ] Dependency changes stale downstream reliability/readiness rather than
      silently reusing prior state.

## Validation

- Companion consensus revision tests (new View / Mask revision /
  Participation change staleness);
- soft-mask readout kernel/reference parity tests;
- replay/digest round-trip tests.

## Non-goals

- No reliability weighting math (V2D), no aggregation change (V2E), no browser
  protocol artifact, no Candidate publication change.
