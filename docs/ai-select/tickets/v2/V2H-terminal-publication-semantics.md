# V2H — Terminal Candidate publication and explicit consent

Status: **review-required parent envelope — current review frontier; not agent-ready**

Blocked by: V2E, V2G  
Blocks: V2J

## Authority

Final Spec v2.0, Amendments 003–008, ADR 0020, and carried-over atomic production Candidate publication.

## Goal

Define a complete, fail-closed mapping from current Readiness plus terminal outcome to Candidate publication, prior-Candidate preservation, explicit Limited consent, and available recovery actions.

## Inputs

- current converged, scope-stable Consensus/aggregate and exact identity;
- Lift Readiness and Frontier Debt;
- terminal outcome from V2G;
- Attempt/Series/Journal terminal state from V2I;
- prior Candidate current/stale state.

## Q10 review gates

- behavior for Ready/Limited/Not Ready across low-gain, budget exhaustion, no-feasible, failure, cancel, suspend, stale, and non-convergence outcomes;
- whether Ready at a non-low-gain forced terminal auto-publishes or requires consent;
- explicit `Use Limited Candidate` versus Re-Lift semantics;
- prior Candidate preservation and application eligibility while a fresh continuation runs;
- no Candidate from scope-advanced, non-converged, oscillating, cancelled, suspended, or stale results;
- recovery recommendations and atomic publication identity.

## Invariants already accepted

Candidate never self-applies Native Selection. Partial/non-current publication is forbidden. Ready-low-gain may auto-publish under ADR 0020. Limited never auto-publishes without an explicit consent decision. Re-Lift re-evaluates exact current stable inputs and does not restart acquisition.

## Validation families

Complete Readiness × terminal-outcome table; atomicity; stale/cancel/suspend; prior Candidate; explicit Limited consent; Re-Lift regression; Continue interaction.
