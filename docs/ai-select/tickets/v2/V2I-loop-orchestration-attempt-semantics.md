# V2I — Browser loop orchestration, identity hierarchy, journal, and replay

Status: **review-required parent envelope — next joint review with V2G; not agent-ready**

Blocked by: V2F, V2G  
Blocks: V2J

## Goal

Generalize the implemented serial Generated View controller into a Browser-driven bounded acquisition loop over existing validated request/response boundaries, with an explicit hierarchy for loop, acquisition attempt, iteration, probe, render, mask, Evidence, Consensus Revision, Scope Revision, and endpoint attempt identities.

## Required boundaries

- no autonomous Companion product session or new transport;
- every request independently validates exact identities;
- only complete independent Views/Masks/Evidence publish progressively;
- Candidate publication authority remains V2H/Lift Readiness;
- Cancel immediately prevents later product publication, while GPU/process interruption is best effort;
- Scope-advanced results must re-solve before Readiness;
- wall-clock telemetry cannot alter replayable candidate ranking;
- Continue Acquisition is a fresh bounded attempt, not same-attempt replay.

## Q9 review gates

- canonical identity hierarchy and which IDs rotate for retry, replacement, Scope Revision, correction, Continue Acquisition, and Restart;
- append-only decision journal versus recomputation on replay;
- exact replay of previously decided candidates and outcomes without consulting new wall-clock/cache state;
- partial completion, late-result, cancel, suspend/resume, stale dependency, and OOM semantics;
- budget state binding and Continue Acquisition inheritance/reset;
- Browser/Companion ownership of loop state and disposable caches;
- deterministic journal compaction/lifetime and recovery after process restart.

## Non-goals

No UI surface, utility math, numeric budgets, or terminal Candidate matrix.
