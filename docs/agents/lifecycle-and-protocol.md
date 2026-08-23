# Lifecycle and Protocol Invariants

Read for target, View, Mask, Evidence, Seed/Core/Frontier, consensus, Candidate, acquisition, recovery, identity, replay, cancellation, suspension, or Native Selection.

## Baseline and gate

Amended v2.0 is target; runtime remains v1.3 until explicit reviewed cutover. Exact stage must be agent-ready in both current mapping and review status.

## Authority

Stable Mask, Participation, raw Evidence, Seed/Core/Frontier, q/s Consensus, Candidate, and Native Selection are distinct. User Confirmed/manual masks cannot be silently replaced or automatically downweighted. Candidate changes Native Selection only via explicit native operations/EditHistory.

## Consensus lifecycle

- Canonical input is the exact current Included Stable observation set.
- Each iteration reaggregates immutable Evidence from fixed finite priors.
- Previous q/s is used only for lagged readout, never re-added as Evidence.
- Reliability iteration `r` consumes only q/s from `r-1`.
- User Confirmed/manual, warm-up, insufficient-support, and unscorable cases keep neutral weight `1.0`.
- Eligible automatic View weights are independent, floored, and not sum-normalized.
- The absolute residual guard is unavailable before consensus maturity.
- Scope is frozen during solve; Scope Delta commits after a complete revision.
- Partial iterations never become current.
- Convergence requires mean/tail/weight stability for consecutive iterations; period-two oscillation is explicit.
- Non-converged/oscillating output is Limited/fail-closed and cannot publish Candidate.
- Warm/cache optimizations must equal a cold canonical solve.

## Evidence

Reliability weights semantic P/N only. Source raw V remains immutable and solver visibility is not multiplied by Reliability. Current production keeps one Negative Mass. CWED and consensus maps remain Companion-internal.

## Acquisition and recovery

Anchor starts bounded automation. Users do not manage cameras while it runs. Cancel immediately prevents later product publication; kernel interruption is best effort. After termination, active targets may Add Observation or Continue Acquisition. New stable observations stale prior Candidate but never patch Candidate or Native Selection.

## Replay

Loop, iteration, Consensus Revision, scope revision, and endpoint-attempt hierarchy remains a V2I review gate. Do not claim deterministic wall-clock replay before that review.
