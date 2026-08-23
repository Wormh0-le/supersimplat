# ADR 0023: Stage depth support and require seed-independent discovery

Status: accepted (companion to Final Spec v2.0 Amendment 002; accepted 2026-08-23)

Date: 2026-08-23

## Context

Final Spec v2.0 initially coupled three decisions:

1. add a kernel-internal expected-depth readout;
2. classify production Negative Mass by depth and make it a prerequisite of Reliability/Aggregation;
3. initialize Observation Coverage and View Utility from a Conservative Seed-derived Core denominator.

Repository review found that pinned gsplat already returns projected Gaussian depth as `meta["depths"]`, while the project-owned Direct Evidence ABI simply does not pass it into the custom kernel. Depth moments can therefore be added without inventing a new visibility authority.

The more ambitious classified-N proposal is different: final per-pixel expected depth is known only after the contribution chain is accumulated, while assigning each contribution a front/near/behind class may require a second traversal or retained accepted-contribution state. Seed2GS supports a depth-aware conservative seed, but it does not establish that depth-classified production Negative Evidence improves this project's existing `alpha × T` P/N/V pipeline.

A second review found a product-level feedback risk. If Seed alone initializes the Core denominator, Coverage, View Utility, and next-View selection, an omitted real object part can remain invisible to every downstream decision. Monotonic Core growth prevents denominator shrinkage but does not discover support that never enters the initial scope.

## Decision

1. Rename the internal expected-depth statistic **Contribution-Weighted Expected Depth (CWED)**. Accumulate `M0 = Σw`, `M1 = Σwz`, and `M2 = Σwz²` from the accepted Direct Evidence sequence; derive CWED and depth variance only where contribution mass is valid. CWED is not first-hit or authoritative surface depth.
2. Keep these moments Companion-internal and out of the Browser protocol.
3. Evaluate two Conservative Seed variants in parallel:
   - S0: current P/N/V semantic support plus visibility and scale-aware connectivity;
   - S1: S0 plus a soft Gaussian-center depth-consistency score using CWED validity/variance and Gaussian scale.
4. A failed S1 depth score cannot erase plausible support from discovery. Seed admission is graded (`seed-core`, `satellite`, `frontier`, `filtered-gross-outlier`) and diagnosable rather than a permanent binary ownership gate.
5. Separate target scope into Conservative Seed, Core Target Set, seed-independent Discovery Envelope, and reversible Discovery Frontier. Core is monotonic only within one stable input revision; an authoritative revision may rotate and rebuild it.
6. Core Observation Coverage and Frontier Debt remain distinct. Readiness cannot use high Core Coverage as proof that no relevant support remains undiscovered.
7. View Utility must support Core exploitation, Frontier discovery, Uncertain resolution, directional diversity, and cost. Seed influence may dominate early framing but must decline as iterative state becomes available; bounded exploration remains possible.
8. Move depth-classified Negative Evidence to a nonblocking experiment (`V2AX`). Current production retains one Negative Mass channel. V2AX does not block Consensus, Reliability, Aggregation, Utility, or orchestration.
9. Promotion of classified N requires a later explicit decision after frozen real-scene quality and performance gates, including schema/reference/identity migration.

## Supersession

This ADR partially supersedes ADR 0021:

- ADR 0021 decisions to keep depth readouts internal and share the accepted Direct Evidence sequence remain current;
- its terminology is narrowed to CWED and depth moments;
- its mandatory in-place classified-N production migration and direct dependency into Reliability/Aggregation are superseded;
- its soft-mask readout decision remains pending the V2C recurrence review.

## Consequences

- The v2 critical path can implement Reliability and Weighted Aggregation using the existing immutable P/N/V contract.
- Depth-aware Seed remains a first-class experiment without forcing a premature production Evidence schema migration.
- The planner gains an explicit discovery path independent of the initial Seed, reducing confirmation lock-in at the cost of more state, calibration, and exploration work.
- Core stability and Frontier reversibility are separated: Core does not oscillate inside a stable revision, while uncertain discovery can be added and removed without corrupting Coverage.
- V2A and V2B remain parent envelopes and must still be decomposed before implementation.
- ADR 0021 is retained for history and marked partially superseded rather than rewritten away.
