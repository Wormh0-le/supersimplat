# AI Select Context Amendment 003 — Consensus recurrence vocabulary

Status: **current vocabulary overlay**  
Authority: Final Spec v2.0 Amendment 003 / ADR 0024

This file temporarily overrides conflicting or underspecified consensus terms in root `CONTEXT.md`. Fold these terms into the root glossary during the later controlled glossary consolidation, then delete this overlay and the superseded definitions.

## Consensus Membership Tendency (`q`)

A continuous `[0,1]` Companion-local value expressing the current foreground-membership tendency for one Stable Gaussian ID. It is not a calibrated probability, Candidate membership, or Native Selection.

## Consensus Support / Knownness (`s`)

A continuous `[0,1]` Companion-local value expressing how much current observation support makes `q` meaningful. Low `s` distinguishes unknown support from high-support semantic conflict near `q≈0.5`.

## Solver Iteration

One private recurrence step that renders the lagged consensus readout, computes reliability, performs weighted aggregation, and updates q/s. Solver Iterations are not product-visible revisions.

## Consensus Revision

One atomic Companion-local result bound to an exact canonical input snapshot. A revision may contain multiple bounded Solver Iterations.

## Canonical Full Solve

The deterministic, arrival-order-independent batch solve over the exact current Included Stable observation set. Warm starts and incremental caches must remain equivalent to it within the declared tolerance.

## Frozen Scope Revision

The exact Core / Discovery Envelope / Frontier binding held constant throughout one canonical solve.

## Scope Delta

A proposed Core promotion, Frontier retention/rejection, or Discovery Envelope expansion derived after a solve. It commits atomically after the Consensus Revision and affects only a subsequent solve.

## Non-converged Consensus

A bounded solve that reaches its iteration limit without satisfying the convergence contract. It may produce diagnostics but cannot establish Ready or publish Candidate.
