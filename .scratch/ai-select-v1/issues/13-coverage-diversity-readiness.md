# 13 — Observation Coverage + View Diversity + Lift Readiness

Status: ready-for-agent

Blocked by: 10, 11, 12, 08

## Final Spec mapping

- DG-04
- §44–50 Coverage/Readiness
- MVP Phase 5

## Inputs / preconditions

- Current Included Stable View Annotations
- Contributor/visibility evidence
- Planner completion/stop state

## Outputs / handoff artifacts

- Core Target Set / Context Set seam
- Observation Coverage
- View Diversity
- Not Ready/Limited/Ready

## What to build

Implement target-scoped cheap derived readiness state. Replace old whole-scene/count-oriented semantics
with contributor observation over the current target/core set and separate directional diversity.

## Acceptance criteria

- [ ] Define/version the Core Target Set / Context Set construction seam used by observation/readiness/lifting.
- [ ] Observation Coverage is computed from actual gsplat contributor observation over the target/core set, not whole-scene Gaussian count.
- [ ] View Diversity is a separate directional/observation metric and is not interchangeable with raw View count.
- [ ] Lift Readiness is one of Not Ready / Limited / Ready and derives from current Included Stable View inputs.
- [ ] Auto Review remaining Excluded never secretly contributes to Coverage/Readiness.
- [ ] User Confirmed/Included Views contribute normally regardless of historical machine Review reason.
- [ ] Changes to Stable Mask/Participation refresh these cheap derived states automatically.
- [ ] Existence of Review does not globally block Lift when remaining Included evidence legitimately satisfies Limited/Ready.
- [ ] Planner early-stop and readiness consumers share target-scoped observation semantics rather than reintroducing whole-scene denominator.
- [ ] After Stop Generation, planner completion, or max-budget stop, Lift Readiness refreshes immediately from currently completed Included Stable Views.
- [ ] Generate More can use current observation/directional gaps without erasing current readiness state.

## Failure / recovery criteria

- [ ] Unavailable contributor/visibility evidence fails readiness conservatively rather than manufacturing coverage.
- [ ] Coverage/readiness failure never changes Native Selection.

## Affected seams

- src/ai-select/readiness*
- src/ai-select/participation*
- Companion Core/Context set + contributor aggregation policy
- Planner integration

## Validation

- npm test
- npm run test:companion
- npm run lint
- Locked GPU contributor aggregation check
- Not Ready/Limited/Ready calibration fixtures

## Non-goals

- No Candidate publication
