# 09 — Scalable Gallery + Frustum sync + Inspect AI Cameras

Status: ready-for-agent — v2.2 re-audited

Blocked by: 08

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27–28
- DG-18, DG-20
- MVP Phase 3

## Inputs / preconditions

- Progressive AIView registry
- Independent render/mask/evidence states
- Assessment/Participation
- Generated frustums
- Camera Inspection

## Outputs / handoff artifacts

- Single-row scalable Gallery
- Summary/filter/review queue
- Bidirectional frustum sync
- Inspect AI Cameras

## What to build

Build Gallery and frustum synchronization while preserving state boundaries. Navigation/filtering never changes Participation or Evidence identity. Render, Mask, and Evidence failures remain distinguishable.

## Acceptance criteria

- [ ] Gallery uses one horizontal row with stable order: Anchor, auto-generated creation order, user-added creation order.
- [ ] Cards remain minimal: thumbnail, View ID, primary status, Participation, current selection.
- [ ] Render status, Mask quality, Evidence state, Participation, and selection are not collapsed into one ambiguous flag.
- [ ] Status priority is deterministic; Evidence Failed is shown only when Evidence was requested and does not replace RGB Ready.
- [ ] Summary exposes useful counts without pretending they are Lift Readiness.
- [ ] Filters support All / Needs Attention / Included / Excluded / User-added and never mutate Participation.
- [ ] Needs Attention includes unresolved Review, no Stable Mask, Mask Failed, Render Failed, and actionable Evidence Failed where applicable.
- [ ] Filtering de-emphasizes nonmatching frustums without deleting/reclassifying them.
- [ ] Card↔frustum selection sync works without moving Editor Camera.
- [ ] Inspect AI Cameras reuses Camera Inspection and never retargets Anchor.
- [ ] Generated frustums remain read-only in v1.1.
- [ ] Stable viewId, never array index, is identity.
- [ ] Thumbnail/resource handling supports 10–20+ Views without one full Mask Editor per card.
- [ ] Sticky add exposes Generate More / Use Current View / Adjust New View; Stop remains visible while active.
- [ ] No ordinary Delete View; Exclude is normal participation removal, record deletion is Restart/Regenerate-owned.
- [ ] Needs Attention empty state provides return to All.

## Failure / recovery criteria

- [ ] Failed thumbnails/resources keep recoverable View records.
- [ ] Filtering/navigation never changes Participation, Mask, Evidence, or Candidate identity.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Manual 10–20+ View walkthrough including RGB Ready + Evidence Failed
- Frustum↔card tests

## Non-goals

- No manual reorder/search
- No Candidate provenance inspector