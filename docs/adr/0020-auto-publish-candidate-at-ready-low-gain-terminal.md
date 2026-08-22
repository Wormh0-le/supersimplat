# ADR 0020: Auto-publish the Candidate at the ready-and-low-marginal-gain terminal

Status: accepted (companion to Final Spec v2.0; accepted 2026-08-22)

Date: 2026-08-22

## Context

In Final Spec v1.3 an AI Candidate never appears without an explicit user
action: Re-Lift evaluates exact current Evidence and atomically publishes.
The next architecture replaces the fixed acquisition path with a bounded
utility-driven loop whose normal terminal is `ready-and-low-marginal-gain`.
Leaving publication to a manual click at that terminal would negate the main
value of the automated loop (one fewer round trip) while keeping all safety
properties that actually matter: a Candidate is inspectable, replaceable, and
never self-executing — Native operations remain user-only under ADR 0019's
production identity.

This is a deliberate consent-structure change and must be recorded as such:
v1.3 users implicitly consented to Limited-quality publication by clicking;
automation must not silently inherit that consent for lower-quality outcomes.

## Decision

1. At the `ready-and-low-marginal-gain` terminal the loop publishes the
   Candidate automatically and atomically. Replacement stays atomic; the prior
   Candidate remains inspectable; failure isolation preserves all artifacts.
2. Reaching Ready does not stop acquisition. The marginal-gain threshold
   tightens once Ready and the loop stops only when predicted gain falls below
   it, so quality headroom above the readiness threshold is not abandoned,
   while post-Ready budget burn is bounded by the tightened threshold.
3. `Limited` plus budget exhaustion publishes readiness with structured
   reasons but NO Candidate. Accepting Limited quality requires an explicit
   user Re-Lift (Limited remains publishable under that explicit consent).
4. Explicit Re-Lift keeps its v1.3 semantics: a user-triggered re-evaluation
   and gated atomic publication attempt against exact current Evidence. It
   never restarts acquisition. Stale identity publishes staleness, not a
   Candidate.
5. The planner may consume readiness reasons but never takes over Candidate
   publication authority; readiness alone gates publication exactly as in
   ADR 0019.

## Consequences

- Users will see Candidates appear without asking for them; the UI status
  surface must present terminal state and stop reasons so this is legible.
- Mis-publication cost stays low because application is manual and replacement
  is atomic with the old Candidate preserved.
- Auto-publication only fires on the calibrated terminal; every other outcome
  (`marginal-gain-exhausted`, budgets, failures, cancel) publishes nothing or
  readiness-only.
- This decision is hard to reverse quietly once users build workflows around
  auto-published Candidates; reverting requires a spec change and identity
  rotation, which is why it warrants an ADR.
