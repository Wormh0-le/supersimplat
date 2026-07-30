# Final Spec v1.1 → Ticket Traceability Overlay — v2.7

This file is the v2.7 overlay on top of [`TRACEABILITY.md`](./TRACEABILITY.md), which remains the complete v2.6 mapping for R001–R164.

Authoritative interpretation:

```text
TRACEABILITY.md v2.6
+ this v2.7 overlay
= current 166-requirement mapping
```

Amendment 005 / DG-25 govern conflicts.

## Superseded requirement mapping

The v2.6 definition of R154 is superseded.

| ID | Current v2.7 requirement | Ticket(s) |
|---|---|---|
| R154 | Ticket 08A proceeds directly with route-B enhanced 3D-guided independent SAM; A/B/C/D comparison and an acquisition-route ADR are not route-B closure gates | 08A, 21 |

The following v2.6 mappings remain valid without semantic change:

- R153: route B is the default production path;
- R155: tracker/hybrid production requires a later experiment-backed ADR;
- R156–R164: optional Bridge/reference/propagation semantics, per-view correction, artifact identity, Working Set expansion, and final P/N/V ownership remain capability-gated and unchanged.

## New v2.7 requirements

| ID | Requirement | Ticket(s) |
|---|---|---|
| R165 | Multi-view Mask acquisition exposes a versioned backend-neutral capability contract and mandatory per-view `acquireView` provider; route B truthfully advertises no sequence/reference/propagation capability | 08A, 09, 12, 21 |
| R166 | Optional sequence/reference methods (`openSequence`, `acquireSequenceRange`, `updateReferences`, `closeSequence`) are defined and validated for future C/D experiments; unsupported calls fail closed with no state mutation | 08A, 12, 21 |

## Amendment 005 / DG-25 mapping

| Normative rule | Ticket coverage |
|---|---|
| Route B is selected and implemented directly | 08A |
| Route A remains regression baseline/fallback | 06, 08A, 21 |
| No A/B/C/D comparison gate for route B | 08A, 21 |
| No acquisition-route ADR required before route-B closure | 08A |
| Backend capabilities are versioned and digest-bound | 08A, 21 |
| Route B implements independent per-view acquisition | 08A |
| Sequence/reference extension schemas exist for future C/D | 08A, 12 |
| Route B rejects unsupported sequence/reference operations before mutation | 08A, 12, 21 |
| Gallery and Mask registry consume generic acquisition provenance | 08A, 09 |
| Future C/D production requires a separate experiment-backed ADR | 08A, 12, 21 |
| Final ownership remains Included Stable Masks → P/N/V | 14, 20 |

## Reverse mapping result

All current v2.7 requirements map to explicit ticket acceptance, failure, or validation criteria.

No current ticket requires a tracker implementation, Bridge View, dense trajectory, reference memory, or propagation session. The extension schemas preserve those future options without creating a current artifact dependency.
