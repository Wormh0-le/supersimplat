# AI Select Final Spec v2.0 Amendment 002 — Seed-independent discovery and staged depth evidence

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 and Amendment 001  
**Decision record:** `docs/adr/0023-stage-depth-support-and-require-seed-independent-discovery.md`

## 1. Purpose

This amendment closes the first technical review of the v2 acquisition architecture. It keeps a precision-first Conservative Seed, but prevents that seed from becoming a hidden target-membership authority. It also narrows the depth contract and removes mandatory depth-classified Negative Mass from the v2 critical path until benchmark evidence justifies promotion.

The accepted principles are:

```text
Conservative Seed = high-precision bootstrap prior
Core Target Set    = current high-confidence target support
Discovery Envelope = seed-independent potential discovery scope
Discovery Frontier = reversible unresolved support outside Core
```

## 2. Superseded clauses

This amendment supersedes conflicting parts of Final Spec v2.0:

- §4 clauses that let the seed-derived denominator stand in for the complete potential target scope;
- §5 terminology that treated the expected-depth readout as local surface truth;
- §5 and §7 clauses that made depth-classified Negative Mass mandatory production Evidence and a prerequisite of Reliability/Aggregation;
- §6.2 clauses that scored View Utility only over the current Core Target denominator;
- §11–§12 validation language where it assumed one mandatory classified-N production migration.

ADR 0021 remains historical authority for adopting kernel-internal depth moments and avoiding a new Browser depth protocol. Its mandatory classified-N production decision is partially superseded by ADR 0023.

## 3. Contribution-Weighted Expected Depth

The internal depth statistic is named **Contribution-Weighted Expected Depth (CWED)**. For one pixel and the same accepted Direct Evidence contribution sequence:

```text
M0 = Σ w_i
M1 = Σ w_i z_i
M2 = Σ w_i z_i²
CWED = M1 / M0
DepthVariance = max(0, M2 / M0 - CWED²)
```

where `w_i = alpha_i × incoming-transmittance` and `z_i` is the projection depth already aligned with the projected Gaussian row.

Normative constraints:

- `M0/M1/M2`, CWED validity, and depth variance are Companion-internal readouts;
- they use the accepted Direct Evidence sequence and do not create a Browser/Companion depth artifact;
- CWED is not first-hit depth, authoritative visible-surface depth, or Gaussian ownership;
- a pixel below the calibrated minimum `M0` is depth-invalid rather than assigned a trusted CWED;
- high depth variance weakens depth-consistency influence instead of creating a hard rejection.

## 4. Conservative Seed variants

Two seed variants are evaluated in parallel under frozen shadow benchmarks:

### S0 — Evidence and connectivity

```text
high positive support
+ sufficient Visible Mass
+ low semantic conflict
+ scale-aware 3D connectivity
```

### S1 — S0 plus soft center-depth consistency

S1 adds a Gaussian-center depth-consistency score derived from projected center depth, CWED validity/variance, Gaussian scale, and whether the center lies in strong Mask interior or a boundary band.

S1 depth consistency is a **soft admission feature**, not a permanent binary exclusion gate. A Gaussian that does not enter Seed Core may remain `satellite`, `frontier`, or `filtered-gross-outlier` with a recorded reason. Failure of the S1 depth score never removes plausible support from the Discovery Envelope by itself.

No production seed variant is selected until S0/S1 calibration compares seed precision/recall, contamination, thin-structure loss, final Candidate quality, View count, latency, and manual correction burden.

## 5. Target-scope model

For one stable target-input revision:

```text
S0              Conservative Seed Support
C_t             Core Target Set
E_t             Discovery Envelope
F_t = E_t - C_t Discovery Frontier
```

### 5.1 Core Target Set

- `C_0` starts from the accepted Conservative Seed;
- Core contains high-confidence target support used by Core Observation Coverage;
- Core may expand but does not shrink within one stable input revision;
- authoritative Stable Mask, Participation, or equivalent input revision may rotate the Core revision and rebuild it rather than preserving an early mistake forever;
- Core is not Candidate membership and never mutates Native Selection.

### 5.2 Discovery Envelope

The Discovery Envelope is deliberately seed-independent. It is a broad, target-local potential support scope derived from versioned combinations of:

- TargetGeometryHint-local spatial support;
- conservative neighborhoods around known target support;
- Evidence Working Set boundary contact;
- Core-external support reached by a new Stable Mask;
- local Target Splat chunks or support admitted by the reviewed envelope policy;
- User Confirmed Expert Recovery observations.

The Envelope may include background and is never ownership.

### 5.3 Discovery Frontier

The Frontier is reversible derived state. It may grow, shrink, be rejected, or be promoted into Core. It never enters Candidate application directly.

Promotion from Frontier to Core requires versioned evidence such as coherent positive support across Views, adequate visibility, acceptable conflict, and reviewed spatial/connectivity conditions. Promotion must remain diagnosable and replayable.

## 6. Coverage, discovery debt, and readiness

One metric must not answer both “have we seen the known target support?” and “is our current target scope complete enough?”

- **Core Observation Coverage** measures realized valid Visible Mass over `C_t`;
- **Frontier Debt** measures unresolved, potentially valuable support in `F_t`;
- whole-Target-Splat and S0/S1 diagnostic coverage may be reported in shadow evaluation but are not product truth.

Lift Readiness remains the publication authority and must eventually combine at least:

```text
Core Observation Coverage
View Diversity
Frontier Debt
remaining feasible View Utility
identity/artifact completeness
```

High Core Coverage alone cannot establish Ready while material Frontier Debt or a high-value feasible View remains.

## 7. View Utility and exploration

View Utility remains prospective and separate from realized Coverage and Lift Readiness. Its calibrated structure must be able to express:

```text
U(v) = core-coverage gain
     + frontier-discovery gain
     + uncertain-resolution gain
     + directional-diversity gain
     - duplication penalty
     - acquisition cost
```

The seed may dominate initial framing and early exploitation, but its influence must decline as Consensus, Frontier, and Uncertain state become available. A bounded exploration floor prevents the planner from selecting only Views that re-observe already-known Seed/Core support.

The exact prediction probe, normalization, weights, and decay schedule remain V2F review/calibration work.

## 8. Seed-external discovery paths

Core expansion must not require membership in the original Seed. At least these independent discovery paths remain available:

1. Evidence Working Set boundary contact;
2. Core-external positive support from a new Included Stable View;
3. coherent multi-view support that survives conflict checks;
4. User Confirmed Expert Recovery observations.

These signals first enter the reversible Frontier and only later promote to Core.

## 9. Depth-classified Negative Evidence staging

Current production Evidence retains one `negativeMass` channel.

Depth-classified Negative Evidence (`front / near / behind` or another calibrated schema) becomes a separate experimental sidecar, provisionally named **V2AX**. It:

- does not block Provisional Consensus, Observation Reliability, Weighted Aggregation, View Utility, or the acquisition loop;
- initially publishes benchmark diagnostics only;
- does not modify the production Gaussian Evidence artifact schema or Runtime Profile;
- requires a predeclared real-scene ablation and acceptable CUDA/VRAM/latency cost before promotion;
- requires a later explicit schema, policy, reference-parity, and production-identity migration if promoted.

Front/near/behind are geometric relations to a reviewed depth statistic, not automatic semantic labels such as floater, target edge, or true background.

## 10. Validation gates

The reviewed implementation plan must include:

- S0 versus S1 seed shadow comparison;
- adversarial seed-lock fixtures with thin, disconnected, rear, and newly revealed support;
- Core/Envelope/Frontier invariants and Core revision rotation tests;
- predicted versus realized Core and Frontier gain;
- early-stop tests proving high Core Coverage cannot hide material Frontier Debt;
- Expert Recovery tests that break an automatic planner bias;
- optional V2AX classified-N ablation against the unchanged single-N production baseline.

## 11. Unchanged boundaries

This amendment does not change:

- Stable Mask and Participation authority;
- same-decision authoritative RGB and raw P/N/V requirements;
- User Confirmed observation authority;
- atomic Candidate publication and stale blocking;
- explicit Native Set/Add/Remove/Intersect;
- automation-default plus Expert Recovery from Amendment 001;
- prohibition on an autonomous Companion product session.
