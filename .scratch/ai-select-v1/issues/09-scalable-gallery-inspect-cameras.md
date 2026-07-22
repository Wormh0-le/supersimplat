# 09 — Scalable Gallery + Frustum sync + Inspect AI Cameras

Status: ready-for-agent

Blocked by: 08

## Final Spec mapping

- DG-18
- §22 Gallery↔Frustum
- §73/76 Gallery IA
- MVP Phase 3

## Inputs / preconditions

- Progressive AIView registry
- Assessment/Participation state
- Generated frustums
- Camera Inspection

## Outputs / handoff artifacts

- Single-row scalable Gallery
- Summary/filter/review queue
- Bidirectional frustum sync
- Inspect AI Cameras

## What to build

Build the scalable Gallery UI and connect it to 3D frustums/Camera Inspection. Keep View management
separate from Participation semantics: filtering/navigation never mutates evidence participation.

## Acceptance criteria

- [ ] Gallery is one horizontal row with stable base order: Anchor first, then auto-generated creation order, then user-added creation order.
- [ ] Cards are minimal: thumbnail, View ID, primary quality/status badge, participation visual state, and current-selection state.
- [ ] Quality/status badge, Included/Excluded encoding, and current-selection outline are independent visual dimensions.
- [ ] Status priority is deterministic for overlapping states (for example Failed > Review > No Mask > Rendering > Confirmed > Good).
- [ ] Header/summary exposes useful counts such as total Views, Included, Review, Failed without pretending those counts are Lift Readiness.
- [ ] Filter supports at least All / Needs Attention / Included / Excluded / User-added and never mutates Participation.
- [ ] Needs Attention aggregates unresolved Review, No Stable Mask, Mask Failed, and Render Failed cases according to the current policy.
- [ ] When a filter is active, nonmatching 3D frustums are visually de-emphasized rather than deleted or reclassified.
- [ ] Selecting a Gallery card highlights/selects its frustum without moving Editor Camera.
- [ ] Selecting a frustum selects and auto-scrolls the matching Gallery card.
- [ ] `Inspect AI Cameras` enters the existing Camera Inspection mode for spatial inspection of Anchor, Generated, Review/Failed/Excluded, and later User-added frustums.
- [ ] Inspecting a Generated View never silently retargets or changes the Anchor CameraBinding.
- [ ] Generated frustums remain read-only in v1.0.
- [ ] Gallery uses stable viewId identity, never array-index identity.
- [ ] Thumbnail/resource strategy supports lazy/virtualized handling for 10–20+ views and does not instantiate a full Mask Editor per card.
- [ ] Sticky `+` affordance exposes Generate More / Use Current View / Adjust New View when those actions exist; Stop Generation remains in header/summary while active.
- [ ] v1.0 exposes no ordinary Delete View action; Exclude is the normal evidence-removal workflow, while actual record removal is limited to Restart Target or Regenerate Auto Views.
- [ ] Needs Attention empty state offers a clear return to All rather than leaving an apparently empty workflow.

## Failure / recovery criteria

- [ ] Failed thumbnails/resources do not crash Gallery; the card remains a recoverable View record.
- [ ] Filtering/navigation never changes underlying participation or AI artifact versions.

## Affected seams

- src/ai-select/gallery*
- AI View Dock
- Viewport frustum registry
- Camera Inspection integration
- Thumbnail/resource seam

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Manual 10–20+ View Gallery walkthrough
- Frustum↔card synchronization tests

## Non-goals

- No manual reordering
- No search
- No Candidate provenance/source inspector
