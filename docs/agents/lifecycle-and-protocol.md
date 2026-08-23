# Lifecycle and Protocol Invariants

Read for target, View, Mask, Evidence, Scope, Consensus, probe, Candidate, acquisition, recovery, identity, replay, cancellation, suspension, or Native Selection.

## Baseline and gate

Amended v2.0 is target; runtime remains v1.3 until explicit reviewed cutover. An exact stage must be agent-ready in both current mapping and review status.

## Authority

Stable Mask, Participation, raw Evidence, TargetScopeState, q/s Consensus, View Utility/probe, Candidate, and Native Selection are distinct. User Confirmed/manual masks cannot be silently replaced or automatically downweighted. Candidate changes Native Selection only through explicit native operations/EditHistory.

## View acquisition

- Candidate cameras come from a finite deterministic layered pool.
- Geometry pruning may reject obvious infeasibility but is not occlusion truth.
- Only a deterministic shortlist receives the low-resolution complete-occlusion ViewUtilityProbe.
- Probe output is prospective and cannot publish View, Mask, Evidence, Coverage, Readiness, Scope, or Candidate.
- Only the winning candidate receives full authoritative RGB/SAM/Evidence processing.
- Canonical ranking uses deterministic cost units; wall-clock, GPU load, and cache state do not alter order.
- Probe failure cannot silently restore fixed-four or a geometry-only winner.

## Consensus/scope lifecycle

Canonical consensus reaggregates immutable Evidence, uses lagged Reliability, freezes scope during solve, and forces another solve after material Scope Delta. Non-converged, oscillating, stale, or scope-advanced results cannot publish Candidate.

## Acquisition and recovery

Anchor starts bounded automation. Users do not manage cameras while it runs. Cancel immediately prevents later product publication; kernel/process interruption is best effort. After termination, active targets may Add Observation or Continue Acquisition. Continue Acquisition is a fresh bounded attempt, not replay.

## Replay

Loop, acquisition attempt, View iteration, probe, render, mask, Evidence, Consensus Revision, Scope Revision, and endpoint-attempt identity hierarchy remains the Q9/V2I review gate. Do not claim deterministic replay from current wall-clock or cache state.
