# V2G — Deterministic budgets, failures, termination, and continuation

Status: **review-required parent envelope — next joint review with V2I; not agent-ready**

Blocked by: V2F  
Blocks: V2H, V2I

## Goal

Define finite acquisition, probe, replacement, Scope Revision, and cost budgets; structured outcomes; and deterministic terminal rules without allowing transient wall-clock to change canonical camera decisions.

## Accepted inputs

- V2F deterministic candidate/probe/utility result;
- Core Coverage, structured Frontier Debt, View Diversity, remaining Utility, and Consensus/Scope status;
- measured operational telemetry separated from canonical cost units;
- Expert Recovery intent for Continue Acquisition.

## Q9 review gates

- which counters are per target, Scope Epoch, acquisition attempt, View iteration, probe attempt, replacement, Solver Iteration, and Scope Revision;
- successful/failed/probe-only View accounting and bounded replacement;
- deterministic cost-ceiling units versus operational timeout/OOM/cancel;
- structured terminal/outcome taxonomy;
- treatment of scope-advanced mandatory re-solves;
- whether Continue Acquisition resets, inherits, or extends budgets;
- replay semantics for partially completed attempts and recorded cost decisions;
- circuit-breaker rules and no silent fixed-four/geometry-only fallback.

## Required boundaries

Failed work never becomes Evidence. Operational timeout may fail an attempt but cannot retroactively choose a different candidate. All values remain calibration-owned until explicit promotion.

## Non-goals

No Candidate publication matrix (V2H), Browser orchestration implementation (V2I), or UI (V2J).
