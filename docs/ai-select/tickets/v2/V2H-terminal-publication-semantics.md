# V2H — Terminal publication semantics

Status: **review-required parent envelope; not agent-ready**

Blocked by: V2E, V2G  
Blocks: V2J

## Goal

Define Candidate publication and explicit Limited consent across Readiness and terminal stop reasons while preserving atomicity and Native Selection authority.

## Accepted prerequisites

Candidate publication requires:

- converged current Consensus;
- exact current Scope Epoch/Revision;
- no pending material Scope Delta;
- result not `scope-advanced`, stale, non-converged, or oscillating;
- exact production Evidence/policy identity;
- Lift Readiness authority.

`ready-and-low-marginal-gain` may auto-publish Candidate atomically. Scope-revision-budget exhaustion, Limited debt, or other non-happy terminals never auto-publish. Whether explicit user consent can publish a Limited Candidate is a remaining terminal-matrix decision.

## Review gates

Complete Readiness × StopReason matrix; distinction between Re-Lift and “Use Limited Candidate”; prior Candidate preservation; scope/consensus identity binding; cancellation/OOM/failure atomicity.

## Validation families

Happy-path auto-publication; every terminal branch; scope-advanced/stale/non-converged rejection; explicit Limited consent; prior Candidate preservation; no automatic Native operation.

## Non-goals

No UI surface, threshold calibration, or Native operation automation.
