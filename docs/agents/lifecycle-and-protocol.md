# Lifecycle and Protocol Invariants

Read for target, View, Mask, Evidence, Target Scope, consensus, Candidate, acquisition, recovery, identity, replay, cancellation, suspension, or Native Selection.

## Baseline and gate

Amended v2.0 is target; runtime remains v1.3 until explicit reviewed cutover. Exact stage must be agent-ready in both current mapping and review status.

## Authority

Stable Mask, Participation, raw Evidence, TargetScopeState, q/s Consensus, Candidate, and Native Selection are distinct. User Confirmed/manual masks cannot be silently replaced or automatically downweighted. Candidate changes Native Selection only through explicit native operations/EditHistory.

## Target Scope lifecycle

- One Scope Epoch permits Core growth but not shrinkage.
- New observations do not rotate the epoch; authoritative correction/removal of existing evidence may rotate it.
- Each canonical solve binds one immutable Scope Revision.
- Envelope ledger is bounded/provenance-recorded; active Frontier is reversible.
- Rejected Frontier remains ledger state, not Context, and reopens only from new provenance.
- Promotion/rejection is component-level and requires converged evidence plus hysteresis.
- Scope remains frozen during solve.
- Material Scope Delta advances Scope Revision and requires a new canonical solve.
- Pre-delta/scope-advanced consensus cannot feed Readiness or Candidate.
- Scope churn has a finite counter distinct from Solver and View iterations.

## Consensus lifecycle

Each iteration reaggregates immutable Evidence from fixed finite priors; prior q/s is used only for lagged readout. Reliability weights are independent/floored and affect P/N only. Partial iterations never publish. Convergence requires mean/tail/weight stability and oscillation detection. Non-converged/oscillating output is Limited/fail-closed.

## Working Sets

Render Working Set continues to preserve full occlusion/transmittance. EvidenceWorkingSet v1 remains current runtime. V2 migration must bind exact Scope Epoch/Revision and preserve distinct Core/active-Frontier/Context roles; Frontier cannot be hidden in Context.

## Acquisition and recovery

Anchor starts bounded automation. Users do not manage cameras while it runs. Cancel immediately prevents later publication; kernel interruption is best effort. After termination, active targets may Add Observation or Continue Acquisition. New stable observations stale prior Candidate but never patch Candidate or Native Selection.

## Replay

Loop, acquisition iteration, Scope Revision, Consensus Revision, Solver Iteration, and endpoint-attempt hierarchy remains a V2I review gate. Do not claim deterministic wall-clock replay before that review.
