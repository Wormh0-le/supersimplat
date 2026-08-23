# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendment 001
→ Final Spec v2.0
→ ADR 0022 / 0021 / 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

No V2 ticket is agent-ready. Runtime remains the implemented v1.3 baseline.

## Product orientation

```text
default:
Anchor → automatic acquisition → terminal Candidate/readiness

secondary Expert Recovery:
Add Observation / Use Current View
or Continue Acquisition
```

User-added View is retained as recovery and is not exposed as camera management during a running loop.

## Current documents

- `CURRENT-TICKET-SPEC-MAPPING.md` — current authority and ticket lifecycle;
- `V2-REVIEW-STATUS.md` — human-readable implementation gate;
- `TRACEABILITY.md` — amended v2 target coverage;
- `manifest.json` — machine-readable control plane;
- `TICKET-GRAPH-V2.md` — provisional parent capability graph;
- `CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md` — current recovery vocabulary override;
- `tickets/v2/` — review-required V2 capability envelopes.

## Historical documents

Implemented v1 control-plane snapshots live under:

```text
docs/ai-select/history/v1/
```

Root v1 graph/audit/walkthrough files are compatibility pointers only. Closed v1 ticket files remain implementation provenance, not current planning.

## Documentation lifecycle

- Current amendments supersede conflicting clauses without rewriting accepted history.
- Deprecated terms and paths are named explicitly.
- Obsolete deletion-oriented V2J documentation has been removed.
- Research remains under `docs/research/`.
- Executable disposable probes remain under `.scratch/experiments/`.
- Calibration and production promotion must gain explicit ticket ownership before v2 closure.

## Next review

```text
V2A — depth data path, expected-depth traversal, classified-N schema and identity
```
