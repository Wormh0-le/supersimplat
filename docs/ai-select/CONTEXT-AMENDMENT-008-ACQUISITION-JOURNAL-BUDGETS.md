# AI Select Context Amendment 008 — Acquisition identity, Journal, and budgets

Status: current vocabulary overlay  
Authority: Final Spec Amendment 008 / ADR 0029

## Acquisition Series

The target-local lineage containing the initial automatic Acquisition Attempt and later Continue Acquisition Attempts. It owns cumulative safety caps. Restart, a new target, or incompatible dependency identity ends or invalidates the Series.

## Acquisition Attempt

One bounded automatic run. The initial run and each Continue Acquisition action are separate Attempts. Replay, endpoint retry, exact resume, and continuation are not synonyms.

## Acquisition Iteration

One canonical planning decision followed by acquisition of one selected candidate and the resulting Consensus/Scope/Readiness work. Multiple Scope or Consensus revisions inside it do not count as additional observations.

## Decision Journal

The Browser-owned append-only, digest-chained record of committed acquisition decisions, exact identities, budget transitions, endpoint outcomes, and terminal state for one Attempt.

## Successful Observation Budget

The allowance consumed only by a current Included Stable observation with current Direct Evidence. Failed or Excluded work does not consume it.

## Selected Candidate Attempt Budget

The allowance consumed when a selected candidate begins formal acquisition, whether or not it later becomes a usable observation.

## Deterministic Cost Budget

A versioned canonical resource ledger based on declared work units. Measured wall-clock and cache state do not redefine ranking or replay semantics.

## Same-attempt Replay

Reuse of an already committed decision or exact endpoint result under the same Attempt, journal state, and endpoint attempt identity. It does not rerank or debit budget again.

## Fresh Retry

New work under a new endpoint attempt identity. It consumes the applicable cost and failure/retry allowances.

## Continue Acquisition

A fresh Acquisition Attempt in the current Series. It receives new per-Attempt allowances while preserving Series cumulative caps and current stable artifacts/scope state.

## Deprecated meanings

- “whole loop = one attempt” is superseded;
- “failed View consumes no budget” is narrowed to Successful Observation Budget only;
- Continue Acquisition is not replay, resume, or persistent Generate More.
