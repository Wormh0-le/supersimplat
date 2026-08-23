# AI Select Context Amendment 006 — Target Scope and Frontier Debt

Status: **current vocabulary overlay**  
Authority: Final Spec Amendment 006 / ADR 0027

This file temporarily overrides conflicting scope terminology in root `CONTEXT.md`. Consolidate it only during the planned full glossary cleanup, then delete the superseded definitions and this overlay.

## Scope Epoch

A target-local interval in which Core Target may grow but not shrink. Authoritative correction/removal of existing observations or incompatible target identity rotates or invalidates the epoch. Adding a new observation alone does not rotate it.

## Scope Revision

One immutable Core/Envelope/Frontier/Context snapshot inside a Scope Epoch. A canonical Consensus solve binds exactly one Scope Revision.

## Target Scope State

Companion-local derived state containing scope identity, Core, bounded Discovery Envelope ledger, active and rejected/reopened Frontier components, required Context, provenance, and policy identity. It is not ownership or Candidate state.

## Frontier Component

A deterministic spatial component or reviewed subcomponent representing unresolved potential target support. It is the primary unit for promotion, retention, rejection, reopening, and Debt.

## Discovery Envelope Ledger

The bounded, seed-independent, provenance-recorded set of support the system has had a valid reason to investigate during a Scope Epoch. Ledger membership is not ownership and does not imply active Frontier.

## Scope Delta

An atomic post-solve proposal to promote Core, retain/reject/reopen Frontier, or expand the Envelope. A material delta advances Scope Revision and requires a new canonical solve before Readiness or Candidate publication.

## Scope-advanced Consensus

A complete Consensus Revision whose post-solve material Scope Delta has advanced the scope. It is diagnostically valid but publication-ineligible because it was solved under the previous Scope Revision.

## Frontier Debt

Structured component-level unresolved target-scope state. It distinguishes Unobserved Debt, Conflict Debt, and Promotion-pending Debt and retains component diagnostics. It is not raw Gaussian count or a substitute for Core Observation Coverage.

## Rejected Frontier

A component currently judged not plausible enough to investigate. It remains in the ledger, is not Context, and may reopen only from new authoritative evidence or discovery provenance.
