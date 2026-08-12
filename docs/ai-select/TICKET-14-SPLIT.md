# Ticket 14 Split Plan — Reference P/N/V Evidence → Candidate

Status: planning decomposition

Parent ticket:
- Ticket 14 — Reference P/N/V Evidence + Gaussian Lifting → Candidate / Uncertain

## 14A — Evidence Aggregation Layer

Goal:
- Normalize multi-view evidence into a traceable evidence set.

Input:
- View artifacts
- RGB artifacts
- Mask artifacts
- Camera metadata
- TargetGeometryHint

Output:
- Unified Evidence Set

Acceptance:
- Every evidence item retains source View identity.
- Evidence lifecycle is compatible with existing Ticket 12 dirty/stale rules.

## 14B — Gaussian Projection Scoring

Goal:
- Score Gaussian support from reference evidence.

Input:
- Unified Evidence Set
- Gaussian set

Output:
- Per-Gaussian support score

Acceptance:
- Projection results are reproducible from the same evidence snapshot.
- Scoring does not introduce removed proposal/ranking abstractions.

## 14C — Candidate Artifact

Goal:
- Produce the first stable AI Select candidate object.

Output:

```text
Candidate
- gaussianIds
- confidence
- evidenceRefs
```

Acceptance:
- Candidate ownership and lifecycle are explicit.
- Ticket 13 Lift Readiness can consume Candidate output.

## 14D — Candidate Review Surface

Goal:
- Allow inspection and confirmation of generated candidates.

Acceptance:
- User can inspect candidate evidence.
- Candidate rejection does not corrupt source evidence.

## Dependency

```text
14A
 |
 v
14B
 |
 v
14C
 |
 v
14D
 |
 v
13 Lift Readiness
```

Ticket 14 remains the current implementation frontier. This split only reduces implementation scope; it does not change the Final Spec authority chain.
