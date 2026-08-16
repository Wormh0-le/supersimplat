# Current Final Spec v1.3 → Ticket Mapping — v2.27

Status: **current normative ticket mapping — Ticket 16A implemented; Ticket 16B ready**

This file maps every active AI Select parent Ticket to `docs/specs/ai-select-final-spec-v1.3.md`.

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical. ADR 0016 supersedes conflicting route/backend/planner details in ADR 0014 and DG-24 through DG-26. ADR 0017 is current where TargetGeometryHint Geometry Quality and Prompt Support semantics are involved.

All 31 parent Ticket files carry a direct current mapping to Final Spec v1.3.
Ticket 14A–14D and post-closure Ticket 16A–16G are implementation stages
under their respective parent Tickets; they refine execution scope without
creating a competing parent graph. Ticket 16B must publish the accepted
superseding ADR and update Final Spec v1.3 before dependent stages close.

| Ticket | Final Spec v1.3 mapping    | Current responsibility                                                         |
| ------ | -------------------------- | ------------------------------------------------------------------------------ |
| 01     | §§1–4, 19, 22, 24          | CurrentTargetContext and lifecycle identity                                    |
| 02     | §§1–5, 24–25               | AI Select shell and authoritative Anchor RGB                                   |
| 02C    | §§3–6, 16, 19, 24–26       | automatic readiness and Companion-ref invalidation                             |
| 03     | §§4–5, 16–17, 24–25        | Camera Inspection, RGB publication and Retry                                   |
| 04     | §§4, 7, 14–15, 19–20, 24   | Editing/Stable/Evidence lifecycle                                              |
| 05     | §§4–7, 19, 22, 24          | Anchor validation, Confirm and Restart                                         |
| 04A    | §§0, 4, 6–8, 16, 26        | historical Prompt/proposal foundation; removed Prompt families are non-current |
| 04B    | §§0, 6–8, 16, 26           | historical Multiplex visual-adapter baseline                                   |
| 04C    | §§4–8, 11, 16, 19, 24–26   | SAM 3 Image adapter, authoritative RGB and opaque refinement refs              |
| 06     | §§0, 5, 13–16, 24–26       | progressive Generated RGB tracer; legacy Mask/fallback isolated                |
| 07     | §§7, 13–15, 18–19, 24–26   | MaskReviewPolicy and Participation                                             |
| 07A    | §§4, 6–8, 14–16, 24–26     | simplified Anchor candidate choice/refinement/confirmation                     |
| 07B    | §8, §§17–19, 26            | Point/Box + Paint/Erase floating palette                                       |
| 08     | §§9–10, 19, 21, 24–26      | TargetGeometryHint and bounded local Views                                     |
| 08A    | §§4–6, 9–13, 16, 19, 24–26 | compact RGB-bound image instance Mask contracts                                |
| 08B    | §§9–19, 24–26              | 3D-guided per-View SAM 3 Image acquisition                                     |
| 08C    | §§9–10, 17–19, 24–26       | retained TargetGeometryHint support and Route B Prompt eligibility             |
| 09     | §§17–19, 24–26             | Gallery/frustum/Mask inspection                                                |
| 10     | §§14, 20–21, 24–26         | optional cross-view Evidence-conflict diagnostics                              |
| 11     | §§5–8, 11–19, 24–26        | user-added Views through current image path                                    |
| 12     | §§16, 19–21, 24–26         | refresh, dirty, stale and Companion-ref lifecycle                              |
| 13     | §§14, 20–21, 24–26         | sole coverage, visibility and Lift Readiness authority                         |
| 14     | §§20–22, 24–25             | reference P/N/V, aggregation, Gaussian lifting and Candidate                   |
| 15     | §§19–22, 24                | Candidate correction and explicit Re-Lift                                      |
| 16     | §§22, 24                   | Native application core: gate, algebra, SelectOp/EditHistory and record        |
| 17     | §§4, 19, 22, 24            | Undo-and-Fix, Restart and target lifecycle after 16G                           |
| 18     | §§4, 19, 22, 24            | Suspended state and exact Undo recovery                                        |
| 19     | §§3–5, 20–21, 24–25        | SceneSnapshot, authoritative RGB and Render Working Set                        |
| 20     | §§4–5, 20–22, 24–25        | production same-decision P/N/V Evidence                                        |
| 21     | §§4–6, 14–25               | core failure, calibration and release hardening; Ticket 10 optional            |
| 22     | §§0, 16, 20–25             | legacy product/Contributor/SAM/Prompt contraction                              |

## Ticket 14 implementation decomposition

| Stage | Parent mapping             | Responsibility                                                 |
| ----- | -------------------------- | -------------------------------------------------------------- |
| 14A   | Ticket 14 / §§20–22, 24–25 | Evidence contract, admission, identities and Working Sets      |
| 14B   | Ticket 14 / §§20–22, 24–25 | Trusted reference per-view P/N/V computation                   |
| 14C   | Ticket 14 / §§20–22, 24–25 | Multi-view aggregation and four-state classification           |
| 14D   | Ticket 14 / §§20–22, 24–25 | Atomic Candidate publication and parent reference quality gate |

Dependency:

```text
14A → 14B → 14C → 14D → 13 → 15
```

Stage contracts live under `docs/ai-select/tickets/14A-*` through `14D-*`. `docs/ai-select/TICKET-14-SPLIT.md` is the decomposition overview.

## Ticket 16 post-closure presentation and visual-review stages

| Stage | Parent mapping                   | Responsibility                                                                 |
| ----- | -------------------------------- | ------------------------------------------------------------------------------ |
| 16A   | Ticket 16 / §§4, 17–19, 22, 24   | Implemented AI View Dock, Candidate Overlay, Toolbar and presentation baseline |
| 16B   | Ticket 16 / §§4, 6–8, 16–26      | Single-result product contract, capability truth and normative supersession    |
| 16C   | Ticket 16 / §§4, 7–8, 17–19, 24  | Mask state truth and compact current-View Inspector                            |
| 16D   | Ticket 16 / §§4, 9–10, 17–19, 24 | Canvas-first three-pane shell and stable Navigator                             |
| 16E   | Ticket 16 / §§4–8, 17–22, 24–26  | 2D Work Area, floating-palette actions and explicit Re-Lift                    |
| 16F   | Ticket 16 / §§4–5, 9–10, 17–24   | Compact 3D toolbar and non-destructive Anchor adjustment                       |
| 16G   | Ticket 16 / §§3–8, 16–26         | Obsolete-control removal, integration and final operator visual closure        |

Ticket 16 remains implemented for native application semantics and adapters.
Ticket 16A remains the implemented functional presentation baseline. Its
completed operator visual walkthrough found the release-presentation issues
owned by 16B–16G. Those stages do not reopen Ticket 16's application algebra;
Ticket 15 remains the owner of Correction/Re-Lift semantics. Ticket 17 follows
16G and must not reintroduce the 3D Toolbar More/Restart surface removed by the
follow-up contract.

## Current implementation frontier

```text
implemented prerequisites:
- 04C, 07, 02C, 07A, 07B
- 08, 08A, 08B, 08C
- 09, 11, 12
- 14A — Evidence Contract & Working Set
- 14B — Reference Per-View P/N/V Evidence
- 14C — Multi-view Aggregation & Classification
- 14D — Atomic Candidate Publication & Reference Validation
- 13 — Visible Evidence Coverage + View Diversity + Lift Readiness
- 15 — Candidate correction + explicit Evidence-aware Re-Lift
- 16 — Native application core
- 16A — AI View Dock + Candidate viewport presentation baseline

current execution stage:
- 16B — Single-result Mask product contract + execution-frontier correction

following post-visual-review stages:
- 16C — Mask state truth + compact Inspector
- 16D — canvas-first shell + stable Navigator
- 16E — 2D Work Area + floating palette + Re-Lift
- 16F — compact 3D Toolbar + non-destructive Anchor adjustment
- 16G — obsolete-control removal + integration closure

follows 16G:
- 17 — Applied Undo-and-Fix + Restart + multi-target lifecycle
```

Compatibility fields:

```text
next_implementation_ticket = 16
next_implementation_subticket = 16B
```

Ticket 16 is the current parent compatibility frontier with 16B as its active
post-visual-review execution stage. Tickets 16C, 16D and 16F follow 16B; 16E
joins the 16C/16D surfaces; 16G closes the integrated slice. Ticket 17 follows
16G. Ticket 10 remains optional and may execute after parent Ticket 14 + 09 +
07 without blocking the core release path.

Locked-GPU browser E2E for Tickets 08B and 08C completed on 2026-08-07 with no blocking issue reported. The locked-GPU large-Gallery browser walkthrough for Ticket 09 passed on 2026-08-07. Ticket 11 shipped with repository test/lint/locales/build green; its locked-GPU browser walkthrough is still pending.

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
- Ticket 06 as a current production fallback;
- `VisibleTargetSupportArtifact` / `TargetBootstrapArtifact` as current v1 geometry contracts;
- ProposalSet/Decision/fallback identities as current Generated-View ownership or Evidence inputs;
- Candidate provenance browser / Gaussian Evidence inspector as part of Ticket 14D.

## Audit rule

The mapping passes only when:

- every parent Ticket resolves here;
- every Ticket-local current mapping block points directly to Final Spec v1.3;
- Ticket 14A–14D point to parent Ticket 14 and Final Spec v1.3 rather than creating a separate authority;
- Ticket 16A–16G point to parent Ticket 16 and Final Spec v1.3 rather than reopening Ticket 16's implemented application core;
- no Ticket-local current mapping block names Final Spec v1.1, an Amendment, or Final Spec v1.2 as authority;
- older spec names appear only under explicit historical/superseded/migration labels;
- implemented prerequisites through 12 are not reported as current ready work;
- parent Ticket 14 and stages 14A through 14D are recognized as implemented;
- Tickets 13 through 15, Ticket 16's application core and Ticket 16A are recognized as implemented, with 16B as the current execution stage and Ticket 17 following 16G;
- `next_implementation_ticket = 16` and `next_implementation_subticket = 16B` are current;
- Ticket 16B is required to publish the superseding ADR and update the current
  Final Spec before dependent stages close;
- no active closure criterion relies on superseded v1.2 architecture;
- provider requests carry resolvable authoritative RGB;
- previous logits remain Companion-local behind opaque refs;
- Ticket 13 remains sole visibility/readiness authority;
- Ticket 10 absence does not block Ticket 21 core release.
