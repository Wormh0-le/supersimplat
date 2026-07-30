# Current Final Spec v1.3 → Ticket Mapping — v2.12

Status: **current normative ticket mapping**

This file maps every active AI Select Ticket to `docs/specs/ai-select-final-spec-v1.3.md`.

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical. ADR 0016 supersedes conflicting route/backend/planner details in ADR 0014 and DG-24 through DG-26.

| Ticket | Final Spec v1.3 mapping | Current responsibility |
|---|---|---|
| 01 | §§1–4, 19, 22, 24 | CurrentTargetContext and lifecycle identity |
| 02 | §§1–5, 24–25 | AI Select shell and authoritative Anchor RGB |
| 02C | §§3–6, 16, 19, 24–26 | automatic readiness and Companion-ref invalidation |
| 03 | §§4–5, 16–17, 24–25 | Camera Inspection, RGB publication and Retry |
| 04 | §§4, 7, 14–15, 19–20, 24 | Editing/Stable/Evidence lifecycle |
| 05 | §§4–7, 19, 22, 24 | Anchor validation, Confirm and Restart |
| 04A | §§0, 4, 6–8, 16, 26 | historical Prompt/proposal foundation; removed Prompt families are non-current |
| 04B | §§0, 6–8, 16, 26 | historical Multiplex visual-adapter baseline |
| 04C | §§4–8, 11, 16, 19, 24–26 | SAM 3 Image adapter, authoritative RGB and opaque refinement refs |
| 06 | §§0, 5, 13–16, 24–26 | progressive Generated RGB tracer; legacy Mask/fallback isolated |
| 07 | §§7, 13–15, 18–19, 24–26 | MaskReviewPolicy and Participation |
| 07A | §§4, 6–8, 14–16, 24–26 | simplified Anchor candidate choice/refinement/confirmation |
| 07B | §8, §§17–19, 26 | Point/Box + Paint/Erase floating palette |
| 08 | §§9–10, 19, 21, 24–26 | TargetGeometryHint and bounded local Views |
| 08A | §§4–6, 9–13, 16, 19, 24–26 | compact RGB-bound image instance Mask contracts |
| 08B | §§9–19, 24–26 | 3D-guided per-View SAM 3 Image acquisition |
| 09 | §§17–19, 24–26 | Gallery/frustum/Mask inspection |
| 10 | §§14, 20–21, 24–26 | optional cross-view Evidence-conflict diagnostics |
| 11 | §§5–8, 11–19, 24–26 | user-added Views through current image path |
| 12 | §§16, 19–21, 24–26 | refresh, dirty, stale and Companion-ref lifecycle |
| 13 | §§14, 20–21, 24–26 | sole coverage, visibility and Lift Readiness authority |
| 14 | §§20–22, 24–25 | reference P/N/V and Candidate |
| 15 | §§19–22, 24 | Candidate correction and explicit Re-Lift |
| 16 | §§22, 24 | Native Set/Add/Remove/Intersect |
| 17 | §§4, 19, 22, 24 | Undo-and-Fix, Restart and target lifecycle |
| 18 | §§4, 19, 22, 24 | Suspended state and exact Undo recovery |
| 19 | §§3–5, 20–21, 24–25 | SceneSnapshot, authoritative RGB and Render Working Set |
| 20 | §§4–5, 20–22, 24–25 | production same-decision P/N/V Evidence |
| 21 | §§4–6, 14–25 | core failure, calibration and release hardening; Ticket 10 optional |
| 22 | §§0, 16, 20–25 | legacy product/Contributor contraction |

## Current implementation frontier

```text
ready now:
- 04C — critical model migration gate
- 07  — parallel MaskReview policy correction

after 04C:
- 02C may proceed independently

after 04C + 07:
- 07A

after 07A:
- 07B and 08 in parallel
```

`next_implementation_ticket = 04C` is retained as the critical-path compatibility field, but it is not the only ready Ticket.

## Supersession rules

Implementation agents MUST NOT reintroduce current requirements for:

- static SAM 3.1 Multiplex/private tracker-head inference;
- Negative Box, Prompt Brush, Mask Constraints or Text Prompt;
- binary Brush or Editing Mask as previous logits;
- raw previous-logits tensor in browser Prompt/request state;
- inference request containing only RGB digest with no resolvable image artifact/ref;
- generic near-duplicate/material-distinct cluster framework;
- adaptive/free-space Key-View planning;
- generic backend registry or Route B/C/D bundle;
- automatic Route-A fallback;
- tracker propagation or sequence interfaces;
- `propagation-uncertain` as current Mask Review;
- `weak-gaussian-support` as Mask quality or Ticket 10 output;
- Ticket 10 as a core release blocker;
- Ticket 06 as a current production fallback.

## Audit rule

The mapping passes only when:

- every Ticket resolves here;
- 04C and 07 are recognized as the current ready frontier;
- 04C remains the critical migration gate;
- no active closure criterion relies on superseded v1.2 architecture;
- provider requests carry resolvable authoritative RGB;
- previous logits remain Companion-local behind opaque refs;
- Ticket 13 remains sole visibility/readiness authority;
- Ticket 10 absence does not block Ticket 21 core release.
