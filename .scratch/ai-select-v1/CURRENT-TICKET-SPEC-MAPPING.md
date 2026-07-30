# Current Final Spec v1.3 → Ticket Mapping — v2.11

Status: **current normative ticket mapping**

This file maps every active AI Select Ticket to `docs/specs/ai-select-final-spec-v1.3.md`.

Final Spec v1.1, Amendments 001–005, and Final Spec v1.2 are historical. Ticket-local references to those documents are non-normative provenance only. ADR 0016 supersedes conflicting route/backend/planner details in ADR 0014 and DG-24 through DG-26.

| Ticket | Final Spec v1.3 mapping | Current responsibility |
|---|---|---|
| 01 | §§1–4, 19, 22, 24 | CurrentTargetContext and lifecycle identity |
| 02 | §§1–5, 24–25 | AI Select shell and authoritative Anchor RGB |
| 02C | §§3–6, 16, 24–26 | automatic readiness for current SAM 3 Image manifest |
| 03 | §§4–5, 16–17, 24–25 | Camera Inspection, RGB publication and Retry |
| 04 | §§4, 7, 14–15, 19–20, 24 | Editing/Stable/Evidence lifecycle |
| 05 | §§4–7, 19, 22, 24 | Anchor validation, Confirm and Restart |
| 04A | §§4, 6–8, 16, 24–26 | historical Prompt/proposal foundation consumed by migration |
| 04B | §§0, 6–8, 16, 26 | historical Multiplex visual-adapter baseline |
| 04C | §§4, 6–8, 11, 16, 24–26 | SAM 3 Image adapter and Prompt contract migration |
| 06 | §§5, 13–16, 24 | progressive Generated RGB and legacy baseline isolation |
| 07 | §§7, 13–15, 18–19, 24–26 | MaskReviewPolicy and Participation |
| 07A | §§4, 6–8, 14–16, 24–26 | simplified Anchor candidate choice and confirmation |
| 07B | §8, §§17–19, 26 | Point/Box + Paint/Erase floating palette |
| 08 | §§9–10, 19, 21, 24–26 | TargetGeometryHint and bounded local Views |
| 08A | §§4, 6, 9–13, 16, 19, 24–26 | compact image instance Mask contracts |
| 08B | §§9–19, 24–26 | 3D-guided per-View SAM 3 Image acquisition |
| 09 | §§17–19, 24–26 | Gallery/frustum/Mask inspection |
| 10 | §§14, 20–21, 24–25 | optional cross-view Review diagnostics |
| 11 | §§5–8, 11–19, 24–26 | user-added Views through current image path |
| 12 | §§16, 19–21, 24–26 | refresh, dirty and stale lifecycle |
| 13 | §§14, 20–21, 24–26 | coverage, diversity and Lift Readiness |
| 14 | §§20–22, 24–25 | reference P/N/V and Candidate |
| 15 | §§19–22, 24 | Candidate correction and explicit Re-Lift |
| 16 | §§22, 24 | Native Set/Add/Remove/Intersect |
| 17 | §§4, 19, 22, 24 | Undo-and-Fix, Restart and target lifecycle |
| 18 | §§4, 19, 22, 24 | Suspended state and exact Undo recovery |
| 19 | §§3–5, 20–21, 24–25 | SceneSnapshot, authoritative RGB and Render Working Set |
| 20 | §§4–5, 20–22, 24–25 | production same-decision P/N/V Evidence |
| 21 | §§4–6, 14–25 | failure, calibration and release hardening |
| 22 | §§0, 16, 20–25 | legacy product/Contributor contraction |

## Current execution path

```text
04C → Final Spec v1.3 §§4, 6–8, 11, 16, 24–26
02C → Final Spec v1.3 §§3–6, 16, 24–26
07  → Final Spec v1.3 §§7, 13–15, 18–19, 24–26
07A → Final Spec v1.3 §§4, 6–8, 14–16, 24–26
07B → Final Spec v1.3 §8, §§17–19, 26
08  → Final Spec v1.3 §§9–10, 19, 21, 24–26
08A → Final Spec v1.3 §§4, 6, 9–13, 16, 19, 24–26
08B → Final Spec v1.3 §§9–19, 24–26
09  → Final Spec v1.3 §§17–19, 24–26
12  → Final Spec v1.3 §§16, 19–21, 24–26
13  → Final Spec v1.3 §§14, 20–21, 24–26
```

## Supersession rules

Implementation agents MUST NOT reintroduce current requirements for:

- static SAM 3.1 Multiplex/private tracker-head inference;
- Negative Box, Prompt Brush, Mask Constraints or Text Prompt;
- binary Brush mapping to previous logits;
- general candidate clustering/ranking for v1 Anchor acquisition;
- adaptive/free-space Key-View planning;
- generic backend registry or Route B/C/D bundle;
- automatic Route-A fallback;
- tracker propagation or sequence interfaces;
- `propagation-uncertain` as current Mask Review;
- `weak-gaussian-support` as Mask quality rather than Lift Readiness.

## Audit rule

The mapping passes only when every Ticket resolves here, 04C is the next gate, and no active closure criterion relies on a superseded v1.2 architecture.
