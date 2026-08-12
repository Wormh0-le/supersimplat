# 14C — Multi-view Aggregation & Classification

Status: ready-for-agent — execution stage of parent Ticket 14

Blocked by: none (14B implemented)

Blocks: 14D

## Current Final Spec mapping

- Parent Ticket 14
- Final Spec v1.3 §§20–22, 24–25
- ADR 0013

Final Spec v1.3 and parent Ticket 14 remain authoritative.

## Goal

Aggregate valid per-view reference Evidence without destroying per-view provenance and classify Gaussian support into Selected, Rejected, Uncertain and Out of Scope.

## Inputs / preconditions

- current valid per-view P/N/V artifacts from 14B;
- versioned aggregation/classification policy;
- exact current target/dependency identity;
- current Participation state.

## Outputs / handoff

- versioned aggregate Evidence result;
- four-state Gaussian classification;
- Selected Stable Gaussian IDs for Candidate publication;
- Uncertain Stable Gaussian IDs for diagnostics;
- aggregation/classification identity and diagnostics for 14D.

## Acceptance criteria

- [ ] Aggregation consumes only current valid per-view Evidence artifacts from Included Views.
- [ ] Per-view raw P/N/V remains available after aggregation; aggregation does not collapse source identity irreversibly.
- [ ] Aggregation policy is versioned and binds effective Evidence, Visible Mass, supporting/conflicting Views and declared normalization/capping behavior.
- [ ] Benchmark raw-mass summation against per-view cap/normalization so a close/high-resolution View cannot dominate silently.
- [ ] Selected, Rejected, Uncertain and Out of Scope remain distinct internal classes.
- [ ] Candidate input set contains Selected only.
- [ ] Unobserved or insufficient Visible Mass is Uncertain, never default Rejected.
- [ ] Material positive+negative or materially conflicting support is Uncertain.
- [ ] Absence from Anchor-visible TargetGeometryHint alone cannot classify a Gaussian as Rejected or Out of Scope.
- [ ] Excluding/reincluding a View deterministically changes only aggregation inputs and makes downstream Candidate stale.
- [ ] Stable Mask replacement invalidates dependent per-view Evidence before aggregation can consume it.
- [ ] Aggregation/classification result binds policy, Evidence artifact set, target/dependency identity and reference backend identities.

## Failure / recovery

- Missing/stale/incompatible per-view Evidence fails closed.
- Aggregation failure publishes no partial classification and preserves the previous Candidate.
- An unusable View is omitted through upstream Participation/Evidence admission; it is never converted into negative Evidence.

## Validation

- single-vs-multi-view fixture;
- high-resolution/close-view dominance fixture;
- mixed positive/negative fixture;
- unobserved/insufficient-V fixture;
- exclude/reinclude fixture;
- Stable Mask replacement fixture;
- TargetGeometryHint non-ownership fixture;
- deterministic policy/identity invalidation tests.

## Non-goals

- No Candidate publication; 14D owns it.
- No Native Selection mutation.
- No Ticket 13 readiness/coverage claim.
- No optional Ticket 10 cross-view diagnostic requirement.
- No generic candidate clustering/ranker.
