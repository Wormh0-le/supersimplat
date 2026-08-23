# Lifecycle and Protocol Invariants

Read this file for target, View, Mask, Evidence, Seed, Core/Frontier, consensus, Reliability, Candidate, acquisition-loop, Expert Recovery, identity, replay, cancellation, suspension, or native-selection behavior.

## Baseline and implementation gate

- Final Spec v2.0 with Amendments 001–004 is the target.
- Runtime remains v1.3 until an explicit reviewed cutover.
- Both mapping and review status must mark an exact stage agent-ready.

## Stable authority

- The editor owns Stable Gaussian IDs and one Current Target Context.
- Stable Mask, Participation, raw Evidence, Seed/Core/Frontier, Consensus, Candidate, and Native Selection remain distinct.
- User Confirmed/manual Stable Masks cannot be silently replaced or automatically downweighted.
- Candidate changes Native Selection only through explicit Set/Add/Remove/Intersect backed by Native EditHistory.

## Seed, Core, and discovery

- Seed is precision-first, incomplete, and non-executable.
- Seed never hard-bounds Evidence or discovery.
- Core is monotonic only inside one stable input revision.
- Discovery Envelope has Seed-independent sources.
- Frontier is reversible and never directly Candidate membership.
- Core Coverage and Frontier Debt are distinct.

## Consensus recurrence and readout

- Consensus stores q+s under an exact frozen scope revision.
- Canonical output uses the exact Included Stable observation set, not arrival order.
- Reliability iteration `r` consumes only q/s from iteration `r-1`.
- One public Consensus Revision may contain bounded private iterations.
- Scope is frozen during the solve; Scope Delta commits afterward.
- Support-aware membership contracts low-support q toward neutral.
- Same-decision readout maps remain Companion-local and do not replace raw V.
- Partial iterations/readouts never become current state.
- Non-convergence is Limited/fail-closed and cannot publish Candidate.

## Reliability

- Reliability applies to semantic P/N only; raw V remains realized observation truth.
- Stable Mask regions are compared locally: positive interior, negative ring, low-weight/diagnostic boundary; Far Neutral is excluded.
- Positive Frontier protection is bounded and asymmetric.
- Insufficient comparison support yields neutral weight and a reason.
- User Confirmed/manual observations retain semantic weight `1.0`.
- leave-one-out Reliability is offline/reference-only.
- Reliability never mutates Mask, Participation, Candidate, or Native Selection.

## Automatic acquisition

- Anchor confirmation starts automation by default.
- The running loop owns bounded planner-selected Generated Views.
- View Utility preserves exploitation and bounded discovery exploration.
- Users do not manage cameras or invoke persistent Generate More while running.
- Cancel changes product authority immediately; kernel/process interruption is best effort.

## Expert Recovery

- Available only after the loop stops and while target is active.
- Add Observation uses authoritative RGB and Stable Mask/Participation rules.
- Continue Acquisition starts a fresh bounded attempt from exact stable artifacts.
- New Stable observation stales previous Candidate; it never patches Candidate or Native Selection.

## Replay and identity

Loop, iteration, Consensus Revision, scope revision, and endpoint-attempt hierarchy remains a V2I review gate. Do not claim deterministic wall-clock replay prematurely.
