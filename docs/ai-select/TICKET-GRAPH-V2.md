# AI Select v2.0 — Implementation Ticket Graph

Status: **accepted scope — pending execution; at most one ticket in flight**

Source: `docs/specs/ai-select-final-spec-v2.0.md` (accepted 2026-08-22) with
ADRs [0020](../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md)
and [0021](../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md).
Vocabulary: `CONTEXT.md` (migrated to v2.0).

## Execution rules

- Final Spec v2.0 is the normative specification; runtime behavior remains
  v1.3 until each behavior's ticket lands.
- Tickets execute in dependency order, one at a time; each ticket runs in a
  fresh session driven by its acceptance criteria (`/tdd` inside,
  `/code-review` before commit).
- Calibration-only items (spec §12) are deliberately NOT tickets. Numeric
  thresholds appear in acceptance criteria only as calibration inputs; the
  calibration round (spec §11 metric/ablation families under locked GPU
  gates) fills them after implementation.

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v2.0.md`
2. ADR 0021
3. ADR 0020
4. ADR 0019 (carried over, extended)
5. ADR 0018 (residual effect: single-result authoring carries over; `4–8`
   range superseded by the dual budget)
6. ADR 0016 / 0017 where not superseded
7. unconflicted ADR 0013 / 0015
8. current Ticket mapping + Ticket acceptance criteria
9. implementation and tests

## Ticket set

| ID  | Name                                                     | Spec §   | Blocked by    | Blocks        |
| --- | -------------------------------------------------------- | -------- | ------------- | ------------- |
| V2A | Evidence-Internal Depth + depth-classified Negative Mass | §5       | —             | V2B, V2D, V2E |
| V2B | Conservative Seed Support + Core Target denominator      | §4       | V2A           | V2E, V2F      |
| V2C | Provisional Consensus state + soft-mask readout          | §5, §7.1 | —             | V2D           |
| V2D | Observation Reliability                                  | §7.2     | V2A, V2C      | V2E           |
| V2E | Weighted aggregation revision                            | §7.3     | V2A, V2B, V2D | V2H           |
| V2F | View Utility + layered candidate pool                    | §6.1–6.2 | V2B           | V2G, V2I      |
| V2G | Dual budget, failure semantics, termination              | §6.3–6.4 | V2F           | V2H, V2I      |
| V2H | Terminal publication semantics (auto-publish / Limited)  | §6.4     | V2E, V2G      | V2J           |
| V2I | Browser loop orchestration + attempt semantics           | §3, §8   | V2F, V2G      | V2J           |
| V2J | Acquisition UI + User-added View removal                 | §10      | V2H, V2I      | —             |

## Dependency graph

```text
V2A Evidence-Internal Depth + classified N
 ├──► V2B Conservative Seed Support ──► V2F View Utility ──► V2G Budgets ──┬──► V2H Publication ──┐
 │                                        ▲                                │                      │
 └──► V2D Reliability ◄── V2C Consensus   │                                └──► V2I Orchestration─┤
           │                              │                                                       │
           └──► V2E Aggregation ◄─────────┘ (denominator)                                          ▼
                    │                                                                V2J UI + capability removal
                    └────────────────────► V2H
```

One valid topological order:

```text
V2A, V2C → V2B → {V2D → V2E} ∥ {V2F} → V2G → {V2H, V2I} → V2J
```

V2A and V2C are independent roots. V2F (utility) can proceed in parallel with
the reliability chain once V2B lands. V2J executes the User-added View
capability removal as its runtime cutover (spec-level supersession is
done; shipped behavior changes only when V2J lands).

## Tracer-bullet intent

Each ticket lands a testable increment without breaking v1.3 production
behavior on branch `ai-select-v1`: V2A/V2C add kernel readouts behind identity
gates; V2B/V2D/V2E add Companion-local derived stages that default to
v1.3-equivalent behavior until promoted; V2F–V2I generalize the implemented
generated-view queue into the loop state machine; V2J is the presentation and
capability cutover that executes with the supersession.

## Scope boundaries

- no calibration tickets: every numeric threshold in spec §12 stays a named
  calibration input (`seed precision thresholds`, adjacency k, residual mix,
  warm-up rounds, `r_min`, tightened gain threshold, dual budgets, max
  revisions); tickets implement the parameterized structure only;
- canonical stop-reason naming is a domain-modeling output — V2G records the
  working set and must not freeze names ahead of that pass;
- whole-frame rendered depth stays parked as a separately gated open question;
  no ticket introduces a standalone depth artifact or protocol seam;
- fixed-four remains frozen as regression/ablation baseline only — never an
  in-request fallback, never a user-selectable mode;
- no Companion-autonomous session; all loop traffic uses the existing validated
  request/response transport with per-request identity validation;
- no revival of retired planning controls (persistent Stop/Generate More stay
  retired); post-loop "continue acquisition" is an unset product decision;
- region/per-pixel reliability weight scope is out of scope without benchmark
  evidence;
- semantic-disambiguation utility terms wait until Uncertain states exist via
  reliability.

See `docs/ai-select/tickets/v2/V2A-*` through `V2J-*` for the ticket
contracts.
