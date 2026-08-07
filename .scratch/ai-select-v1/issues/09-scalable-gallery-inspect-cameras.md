# 09 — Scalable Gallery + Frustum Sync + Mask Inspection

Status: implemented — separated card presentation, read-only View/Mask
inspection, per-View Camera Inspection, presentation-only filters, and bounded
thumbnails implemented with repository test/lint/locales/build green;
large-Gallery browser walkthrough remains operator validation. Point/Box/Paint
correction for Generated Views remains on the Anchor surface and card
Retry/Confirm/Participation actions; per-View Mask editing arrives with the
user-added View and refresh Tickets (11/12).

Blocked by: 08B (satisfied)

Blocks: 11, 12

## Final Spec mapping

- Final Spec v1.3 §§17–19, 24–26
- ADR 0016

## Purpose

Present progressive AI Views and camera frustums without exposing obsolete backend-route, tracker or generic proposal-decision machinery.

## Card state model

Cards distinguish:

```text
Render status
Prompt synthesis status
Mask inference status
Mask Review / Stable Mask status
Participation
Evidence status
Candidate stale/current where applicable
```

Required examples:

```text
Render Ready
Prompt Ready
Mask unavailable
Stable Mask none
Participation Excluded
```

is distinct from:

```text
Render Ready
Mask inference technical failure
prior Stable Mask retained or none
Participation unchanged/current policy
```

Anchor one-point candidate choice remains on the Anchor authoring surface. Generated and User-added Views normally produce one model Mask and do not expose a generic ProposalSet/Decision panel.

## Required behavior

- stable order: Anchor, generated local Views in creation order, then user-added Views;
- View role is visible but does not imply trust;
- card/frustum selection is bidirectional and never moves Editor Camera automatically;
- Camera Inspection reuses existing inspection behavior;
- filters do not mutate Prompt, Mask, Participation, Evidence or Candidate;
- RGB remains inspectable while Prompt/Mask inference is pending or failed;
- semantic unavailable is not shown as service/transport/OOM failure;
- Mask Review reasons map to corrective actions;
- Lift Readiness is presented separately when Ticket 13 exists.

## Removed presentation

Current v1 Gallery does not show:

- Route B/C/D backend kind;
- automatic Route-A fallback provenance;
- sequence/tracker/reference state;
- generic selected/ambiguous/unavailable Decision for ordinary Generated Views;
- Prompt Brush or Negative Box correction actions.

## Corrective actions

Depending on state:

- inspect Mask;
- add Positive/Negative Point;
- adjust Positive Box;
- Retry Mask;
- regenerate 3D-guided Prompt;
- Paint/Erase or Manual Draw;
- Confirm as-is where allowed;
- Include/Exclude;
- adjust/add View.

## Acceptance criteria

- [x] Render, Prompt, Mask inference, Mask Review, Participation and Evidence remain separate.
- [x] semantic unavailable differs from technical inference failure.
- [x] no obsolete backend/fallback/tracker state appears.
- [x] no Prompt Brush/Negative Box action appears.
- [x] Anchor candidate choice is not duplicated into every card.
- [x] role and Participation remain independent.
- [x] 10–20+ Views remain resource-bounded.
- [x] card↔frustum selection and Camera Inspection are deterministic.
- [x] Generate More appends local Views without visually staling prior completed Views.
- [x] filtering/navigation never mutates formal state.

## Validation

- large Gallery walkthrough;
- semantic-unavailable versus technical-failure fixture;
- Prompt/Mask Review action fixtures;
- removed backend/tool presentation assertions;
- card/frustum sync tests;
- RGB Ready plus Mask pending/failed combinations;
- repository test/lint/locales/build.

## Non-goals

- No model execution or Prompt synthesis.
- No tracker/reference UI.
- No Candidate provenance inspector.
