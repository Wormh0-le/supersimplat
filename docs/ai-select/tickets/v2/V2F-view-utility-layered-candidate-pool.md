# V2F — View Utility + layered candidate pool

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2B
Blocks: V2G, V2I

## Final Spec v2.0 mapping

- Final Spec v2.0 §6.1–6.2; `CONTEXT.md` non-normative "View Utility"

## Goal

Implement the prospective View Utility scorer and the layered candidate pool,
with the deterministic hint-based first View, replacing the fixed-four /
`4–8` initial plan as the product acquisition path.

## Inputs / preconditions

- Core Target denominator + dual coverage (V2B);
- existing hint-offset machinery, feasibility gates and generated-view
  controller pattern (`src/ai-select/generated-view-controller.ts`);
- Observation Coverage / View Diversity realized measures (v1.3 carry-over).

## Outputs / handoff

- Deterministic first-View rule: hint-projection-largest feasible candidate
  (consensus does not exist yet — a technical boundary, not a special
  channel);
- layered candidate pool: existing hint offsets + local sphere sampling
  around the hint center, unified through existing feasibility gates
  (clipping, projection size, hint visibility, nonblank RGB); layer
  combination ablatable;
- View Utility scorer: predicted marginal Visible Mass gain over the Core
  Target denominator, directional-diversity increment, duplication penalty,
  feasibility/cost;
- incremental rescoring triggered by every Included publication (per-View
  delta where possible);
- policy identity `view-utility-policy/experimental-v*`.

## Acceptance criteria

- [ ] Realized / prospective / readiness separation of concerns holds: View
      Utility only scores candidates; it never publishes or gates readiness.
- [ ] Planner consumes readiness reasons but never takes over Candidate
      publication.
- [ ] First post-Anchor View is deterministic and hint-based; later Views are
      utility-driven.
- [ ] Candidate pool layers pass the existing feasibility gates; no new
      feasibility semantics invented.
- [ ] Utility terms limited to the calibration scope; semantic-disambiguation
      terms are deferred until reliability establishes Uncertain states.
- [ ] Utility policy is versioned, deterministically replayable with a
      deterministic tie-break; same inputs → same choice, tested.
- [ ] Rescoring fires after every Included publication; incremental result
      equals full rescore (equivalence test).
- [ ] Policy staged `experimental-v*`; promotion by explicit key change.

## Validation

- Determinism/replay tests (fixed seed + inputs → identical sequence);
- layered-pool feasibility gate tests;
- incremental-vs-full rescoring equivalence tests;
- first-View determinism test.

## Non-goals

- No budget/stop logic (V2G), no loop state machine (V2I), no readiness
  policy change, no fixed-four product path (frozen baseline only).
