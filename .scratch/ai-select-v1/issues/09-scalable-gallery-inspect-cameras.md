# 09 — Scalable Gallery + Frustum sync + tracking-status inspection

Status: blocked — waits for Ticket 08A tracking contract

Blocked by: 08A

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27–28
- Final Spec v1.1 Amendment 003
- DG-18, DG-20, DG-23
- MVP Phase 3

## Inputs / preconditions

- Progressive AIView registry
- Independent render/mask/evidence states
- Assessment/Participation
- Generated frustums
- Camera Inspection
- Ticket 08 Key/Bridge sequence roles
- Ticket 08A tracking/Mask/reference status

## Outputs / handoff artifacts

- Single-row scalable Gallery
- Summary/filter/review queue
- Bidirectional frustum sync
- Inspect AI Cameras
- Key/Bridge/Anchor tracking-role presentation
- Tracking/correction-reference status presentation

## What to build

Build Gallery and frustum synchronization while preserving state boundaries. Navigation/filtering never changes Participation, Mask, tracking reference, or Evidence identity. Render, tracking/Mask, Evidence, and Lift failures remain distinguishable.

## Acceptance criteria

- [ ] Gallery uses stable order: Anchor followed by planner sequence order, then user-added creation order.
- [ ] Cards remain minimal: thumbnail, View ID, primary status, Participation, current selection, and compact tracking role where applicable.
- [ ] Anchor / Key / Bridge / none roles are visible without being conflated with Participation.
- [ ] Sequence index/order is inspectable and stable by identity, never array position alone.
- [ ] Bridge Views are de-emphasized/grouped by default but remain inspectable.
- [ ] Bridge role never automatically Includes a View; Bridge Stable Masks default Excluded.
- [ ] Render status, Tracking/Mask status, Mask quality, Evidence state, Participation, and selection are not collapsed into one flag.
- [ ] Correction-reference status is visible and does not imply Included Participation.
- [ ] Status priority is deterministic; Evidence Failed appears only when requested and never replaces RGB Ready.
- [ ] Summary exposes useful counts without pretending they are Lift Readiness.
- [ ] Filters support All / Needs Attention / Included / Excluded / Key / Bridge / User-added and never mutate Participation.
- [ ] Needs Attention includes unresolved Review, identity-drift suspicion, no Stable Mask, Mask Failed, Render Failed, and actionable Evidence Failed.
- [ ] Filtering de-emphasizes nonmatching frustums without deleting/reclassifying them.
- [ ] Card↔frustum selection sync works without moving Editor Camera.
- [ ] Inspect AI Cameras reuses Camera Inspection and never retargets Anchor.
- [ ] A selected off-screen frustum has an explicit locate/inspect path.
- [ ] Generated frustums remain read-only in v1.1.
- [ ] Stable viewId is identity; sequence index is presentation/order metadata.
- [ ] Thumbnail/resource handling supports 10–20+ Views without one full Mask Editor per card.
- [ ] Sticky add exposes Generate More / Use Current View / Adjust New View; Stop remains visible while active.
- [ ] No ordinary Delete View; Exclude is normal participation removal, record deletion is Restart/Regenerate-owned.
- [ ] Needs Attention empty state provides return to All.

## Failure / recovery criteria

- [ ] Failed thumbnails/resources keep recoverable View records.
- [ ] Tracker failure/identity drift remains distinguishable from View Render Failure.
- [ ] Filtering/navigation never changes Participation, Mask, tracking references, Evidence, or Candidate identity.
- [ ] A stale tracking run is shown as stale rather than attached to newer View/Mask state.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Manual 10–20+ View walkthrough with Anchor/Key/Bridge/User-added Views
- RGB Ready + tracking pending/failed + Evidence Failed combinations
- Frustum↔card tests
- Correction-reference and identity-drift Review walkthrough
- Browser walkthrough starting with every Generated Frustum behind the current observer

## Non-goals

- No tracker execution or correction-memory mutation
- No manual sequence reorder/search
- No Candidate provenance inspector