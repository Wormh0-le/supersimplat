# V2B — Conservative Seed, Core Target, and Discovery Frontier

Status: **reviewed parent envelope — awaiting stage decomposition; not agent-ready**

Blocked by: V2A2 only for the S1 shadow variant; S0 and discovery-scope design are depth-independent  
Blocks: V2E, V2F

## Authority

- Final Spec v2.0 Amendment 002;
- ADR 0023;
- carry-over Stable Gaussian ID, SceneSnapshot, Working Set, Stable Mask, and Participation contracts.

## Goal

Evaluate high-precision S0/S1 Conservative Seed variants while establishing a seed-independent target-scope model that can discover real object support omitted by the initial Seed.

## Reviewed domain model

```text
Seed S_0             high-precision bootstrap prior
Core C_t             current high-confidence target support
Envelope E_t         seed-independent potential discovery scope
Frontier F_t=E_t-C_t reversible unresolved support
```

## Outputs / handoff

- Companion-internal S0 and S1 seed records with Stable IDs and diagnosable scores/reasons;
- graded admission: `seed-core`, `satellite`, `frontier`, `filtered-gross-outlier`;
- scale-aware connectivity that does not silently discard all non-largest components;
- Core state with revision identity and monotonic expansion inside one stable input revision;
- Discovery Envelope and reversible Frontier state with versioned policy identity;
- Core Observation Coverage input and separate Frontier Debt input;
- promotion/rejection journal for Frontier support;
- frozen shadow records comparing S0 and S1.

## Seed variants

### S0

Uses P/N/V support, valid visibility, low conflict, and scale-aware 3D connectivity.

### S1

Adds a soft Gaussian-center depth-consistency feature using V2A2 CWED validity/variance, Gaussian scale, and Mask interior/boundary context. Failing this feature cannot by itself erase plausible support from the Discovery Envelope.

## Seed-independent discovery sources

At minimum, the reviewed architecture preserves:

- Evidence Working Set boundary contact;
- Core-external positive support reached by a new Included Stable View;
- coherent support across multiple Views;
- User Confirmed Expert Recovery observations;
- reviewed TargetGeometryHint-local or Target Splat-local envelope support.

These sources first enter Frontier. Frontier never becomes Candidate membership directly.

## Reviewed acceptance decisions

- [x] Seed is non-ownership, deliberately incomplete, and never a hard Evidence boundary.
- [x] S0 and S1 run in parallel shadow evaluation before production selection.
- [x] Gaussian-center depth consistency is a soft score rather than a permanent binary gate.
- [x] Discovery Envelope is not derived solely from Seed.
- [x] Frontier may grow, shrink, be rejected, or promote into Core.
- [x] Core is monotonic only inside one stable input revision; authoritative revision rotation may rebuild it.
- [x] Core Coverage and Frontier Debt are distinct readiness/planning inputs.
- [x] High Core Coverage alone cannot prove acquisition is complete.

## Validation families for later stages

- S0/S1 seed precision, recall, contamination, and thin/disconnected-structure retention;
- deterministic component/satellite/frontier bookkeeping;
- no-seed-lock adversarial fixtures;
- Core monotonicity inside a revision and explicit rebuild on revision rotation;
- reversible Frontier tests;
- boundary-contact and User Confirmed discovery tests;
- final Candidate quality, automatic View count, latency, and Add/Remove correction burden.

## Non-goals

- No View Utility implementation (V2F).
- No direct Candidate or Native Selection mutation.
- No production seed policy promotion or numeric threshold freeze.
- No requirement that S1 outperform S0 before benchmark evidence exists.
