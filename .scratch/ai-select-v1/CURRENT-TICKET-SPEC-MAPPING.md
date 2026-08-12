# Current Final Spec v1.3 → Ticket Mapping — v2.18

Status: **current normative ticket mapping — Ticket 12 implemented; Ticket 14 split planning complete**

Ticket 14 remains the current implementation frontier.

## Ticket 14 decomposition

| Ticket | Responsibility |
| --- | --- |
| 14A | Evidence Aggregation Layer |
| 14B | Gaussian Projection Scoring |
| 14C | Candidate Artifact |
| 14D | Candidate Review Surface |

Dependency:

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

## Current implementation frontier

```text
implemented prerequisites:
- 04C, 07, 02C, 07A, 07B
- 08, 08A, 08B, 08C
- 09, 11, 12

ready now:
- 14A → 14D

after 14:
- 13
```

## Documentation layout

Stable AI Select documentation is moving toward:

```text
docs/ai-select/
```

Scratch remains for:

- experiments
- repro scripts
- temporary validation artifacts

Normative specification and release evidence should not accumulate only in scratch.
