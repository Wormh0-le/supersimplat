# 09 — Scalable Gallery + Frustum sync + Mask-acquisition inspection

Status: blocked — waits for Ticket 08A acquisition contract

Blocked by: 08A

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27–28
- Final Spec v1.1 Amendments 003 and 004
- DG-18, DG-20, DG-24
- MVP Phase 3

## Inputs / preconditions

- Progressive AIView registry
- Independent render/mask/evidence states
- Assessment/Participation
- Generated frustums
- Camera Inspection
- Ticket 08 sparse Key-View plan segments
- Ticket 08A acquisition backend/status
- Optional tracker/reference state only when advertised

## Outputs / handoff artifacts

- Single-row scalable Gallery
- Summary/filter/review queue
- Bidirectional frustum sync
- Inspect AI Cameras
- Anchor/Key/User-added role presentation
- Mask acquisition backend/status presentation
- Optional auxiliary/tracker/reference presentation when capability exists

## What to build

Build Gallery and frustum synchronization while preserving state boundaries. Navigation/filtering never changes Participation, Mask, optional tracking reference, Evidence, or Candidate identity. Render, Mask acquisition, Evidence, and Lift failures remain distinguishable.

## Acceptance criteria

- [ ] Gallery uses stable order: Anchor, immutable planner segments in creation order, then user-added creation order.
- [ ] Cards remain minimal: thumbnail, View ID, primary status, Participation, selection, and compact role/backend where applicable.
- [ ] Anchor / Key / User-added roles are visible without being conflated with Participation.
- [ ] Optional Auxiliary / Bridge / tracker roles appear only when the selected backend advertises them.
- [ ] Plan segment and local index are inspectable metadata; stable `viewId` remains identity.
- [ ] Render status, Mask acquisition status, Mask quality, Evidence state, Participation, and selection are not collapsed into one flag.
- [ ] Acquisition backend/fallback identity is inspectable and does not imply trust or Included Participation.
- [ ] Optional correction-reference status is visible only when that capability exists and does not imply Included Participation.
- [ ] Status priority is deterministic; Evidence Failed appears only when requested and never replaces RGB Ready.
- [ ] Summary exposes useful counts without pretending they are Lift Readiness.
- [ ] Filters support All / Needs Attention / Included / Excluded / Key / User-added and never mutate Participation.
- [ ] Optional Auxiliary/Bridge filters appear only when such Views exist.
- [ ] Needs Attention includes unresolved Review, no Stable Mask, Mask Failed, Render Failed, and actionable Evidence Failed.
- [ ] Optional tracker identity-drift suspicion enters Needs Attention without replacing the Mask/Render status taxonomy.
- [ ] Filtering de-emphasizes nonmatching frustums without deleting/reclassifying them.
- [ ] Card↔frustum selection sync works without moving Editor Camera.
- [ ] Inspect AI Cameras reuses Camera Inspection and never retargets Anchor.
- [ ] A selected off-screen frustum has an explicit locate/inspect path.
- [ ] Generated frustums remain read-only in v1.1.
- [ ] Thumbnail/resource handling supports 10–20+ Views without one full Mask Editor per card.
- [ ] Sticky add exposes Generate More / Use Current View / Adjust New View; Stop remains visible while active.
- [ ] Generate More appends a planner segment and does not visually stale prior completed Views.
- [ ] No ordinary Delete View; Exclude is normal participation removal, record deletion is Restart/Regenerate-owned.
- [ ] Needs Attention empty state provides return to All.

## Failure / recovery criteria

- [ ] Failed thumbnails/resources keep recoverable View records.
- [ ] Mask backend failure remains distinguishable from View Render Failure.
- [ ] Optional tracker failure/drift remains capability-gated and distinguishable from ordinary per-view SAM failure.
- [ ] Filtering/navigation never changes Participation, Mask, optional references, Evidence, or Candidate identity.
- [ ] A stale acquisition result is shown as stale rather than attached to newer View/Mask state.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Manual 10–20+ View walkthrough with Anchor/Key/User-added Views
- Optional Auxiliary/Bridge walkthrough only when selected route supports it
- RGB Ready + Mask pending/failed + Evidence Failed combinations
- Frustum↔card tests
- Backend/fallback identity walkthrough
- Browser walkthrough starting with every Generated Frustum behind the current observer

## Non-goals

- No acquisition backend execution
- No tracker/reference mutation
- No manual sequence reorder/search
- No Candidate provenance inspector
