# 04 — Anchor AIView + independent Editing / Stable Mask / Evidence lifecycle

Status: implemented — 2026-07-24

Blocked by: 02

## Current Final Spec mapping

- Final Spec v1.3 §§4, 7, 14–15, 19–20, 24
- DG-08, DG-09 and DG-20 as historical lifecycle/ownership rationale where not superseded
- MVP Phase 2 as historical implementation provenance

Final Spec v1.3 is the only current closure source. Model-specific implementation details below are historical where superseded by Ticket 04C and Ticket 07A.

## Inputs / preconditions

- Anchor AIView/RGB identity
- Current static image Mask runtime
- CurrentTargetContext

## Outputs / handoff artifacts

- AIView render/mask/evidence state separation
- MaskAnnotation versions
- editingMaskId / stableMaskId
- Atomic Confirm Mask publication
- Per-view Evidence invalidation identity

## What to build

Introduce the current per-view Mask domain. AIView, Mask, and Evidence are independently versioned: RGB Ready does not require a Mask or Evidence; Stable Mask is the formal annotation input; Evidence is a later derived artifact.

## Acceptance criteria

- [x] AIView may be RGB Ready with no Mask and Evidence=`not-requested`.
- [x] AIView may remain RGB Ready when Evidence is stale or failed.
- [x] Mask identity/lifecycle is independent from View identity/lifecycle.
- [x] Anchor exposes independent editingMaskId and stableMaskId.
- [x] Model output creates/replaces Editing Mask and never silently overwrites Stable Mask.
- [x] Prompt changes trigger current static-image Mask feedback without an extra apply action.
- [x] Paint/Erase strokes update Editing Mask locally.
- [x] Confirm Mask atomically publishes the current Editing Mask as a new Stable Mask revision.
- [x] Until Confirm succeeds, downstream users continue seeing the previous Stable Mask and Evidence/Candidate remain current.
- [x] Publishing a new Stable Mask invalidates only dependent per-view Evidence by exact RGB/Mask/policy identity; if Included, Candidate becomes stale. (Candidate does not exist in 04 — explicit non-goal. The exact-identity Evidence invalidation seam that drives future `liftDirty` is in place and tested; Candidate staleness wiring lands with Ticket 14.)
- [x] Automatic and fully manual masks use the same publication contract.
- [x] Mask artifacts bind to AIView/RGB identity so stale output cannot attach to changed RGB/CameraBinding.
- [x] Render, Mask, Evidence, and Candidate statuses remain distinct. (Candidate status: no Candidate in 04 — non-goal. Render/Mask/Evidence statuses are independent and separately exposed.)

## Failure / recovery criteria

- [x] Mask generation failure keeps View/RGB available and permits retry/manual recovery.
- [x] Partial/stale model output is not published as Stable Mask.
- [x] Evidence failure never mutates Stable Mask or View render status.

## Affected seams

- src/ai-select/ai-view*
- src/ai-select/mask*
- src/ai-select/evidence-state*
- AI View Dock selected-view/mask surface
- Companion image-instance adapter/runtime

## Validation

- npm test
- npm run lint
- npm run test:companion
- Atomic Stable publication tests
- Editing-no-stale versus Confirm-invalidates-Evidence tests
- Stale RGB/mask binding rejection tests

## Non-goals

- No multi-view tracking/propagation
- No production Evidence kernel
- No Candidate/lifting
- No full mask-history UX

## Historical implementation record — 2026-07-24

Editor (TypeScript, `src/ai-select/`):

- `mask-annotation.ts` — versioned `MaskAnnotation`/`MaskArtifact` (`bitset-lsb-v1` + `sha256:` digest of decoded bytes), `MaskPrompt`, trust-boundary validators, bitset decode/encode, and local disc brush strokes.
- `mask-registry.ts` — pure per-view Mask domain: SAM results create/replace only the Editing Mask; brush edits create `manual`/`hybrid` local revisions (an out-of-RGB brush starts a fresh manual chain); Confirm Mask atomically publishes the Editing Mask as a new `user-confirmed` Stable revision (synchronous pointer swap; previous Stable version retained). Currency derives from `createdFromRgbDigest`, so stale masks never attach to changed RGB.
- `evidence-state.ts` — per-view Evidence dependency identity (`viewId`, `rgbDigest`, `stableMaskDigest`, `evidencePolicyDigest`) and derived status (`not-requested/pending/ready/stale/failed`). Ready/pending records whose exact identity no longer matches derive `stale`; failures bound to superseded inputs read as not-requested. `aiSelectEvidencePolicyVersion = 'evidence-policy/pnv-v0'` is an identity seam only — no calibrated policy exists yet (Ticket 20).
- `ai-view.ts` — the historical per-view record and `composeAnchorAIView`, exposing independent `renderStatus`, `editingMaskId`/`stableMaskId`, and `evidenceStatus`. Anchor `participation` is fixed `included` until Ticket 07.
- `mask-service.ts` — the historical single-frame transport contract: request binds full async identity + exact RGB artifact + prompt set + `maskAttemptId`; response matching fails closed on any stale identity, dimension, or digest-of-bytes mismatch.
- `mask-controller.ts` — `AISelectMaskController`: prompt changes auto-submit the full prompt set (latest-only; no extra apply action), local brush supersedes in-flight model work, Confirm publishes atomically and derives Evidence invalidation, Retry mints a new `maskAttemptId`, Restart/RGB-change disposes target-local Mask state by identity.
- `anchor-controller.ts` — narrow seam only: `createAnchorMaskRequest` (null unless exact full-resolution RGB Ready) and `acceptsMaskResponse` (context/rgb-digest freshness gate).
- `anchor-dock-presentation.ts` — Mask surface (`none/pending/draft/confirmed/failed` + prompt count + evidenceStatus + confirm/retry affordances), kept distinct from render status.
- `ui/ai-select-anchor-dock.ts` — Dock renders the Mask surface, a tinted Mask overlay aligned to the `object-fit: contain` image, click = include prompt, Shift+click = exclude prompt, drag = brush add, Shift+drag = brush erase (only when the formal RGB is `ready`), plus Confirm Mask / Retry Mask actions. The current Prompt/Edit surface is migrated by Tickets 04C/07B; this interaction description is historical provenance.
- `selection-service-fetch-adapter.ts` + `selection-service-readiness.ts` — historical `produceMask` transport (POST `/ai-select/masks`, manifest assertion, fail-closed validation) behind the readiness gate; `main.ts` wiring; `ai-select.mask.*` locale keys in all 9 locales.

Companion (Python):

- `POST /ai-select/masks` → `CompanionState.produce_ai_select_mask`: historical request validation and one-pass adapter route. Multiplex/private-head specifics are superseded by Ticket 04C and cannot advertise Ready for current static image segmentation.

Decisions retained from the implementation:

- Editing Masks are `draft`; model quality labels are not fabricated before Ticket 07 review. Confirm publishes `user-confirmed`.
- Paint/Erase while a model request is in flight supersedes that request; the late response is discarded rather than clobbering the local edit.
- Evidence registry is exposed (`evidenceRegistry`) for Ticket 20 to drive; nothing produces Evidence in 04.

## Validation recorded — 2026-07-24

- `npm test` — 170 editor tests pass, including atomic Stable publication, Editing-no-stale versus Confirm-invalidates-Evidence, stale RGB/mask binding rejection and fetch-adapter cases.
- `npm run test:companion` — 197 tests pass for the historical contract.
- `npm run lint` — clean; locale lint and build passed.
- Real current SAM 3 Image GPU validation is owned by Ticket 04C, not this historical implementation record.

Known gaps / handoff notes:

- Manual browser walkthrough of the Dock Prompt/Edit/Confirm flow with the current 04C adapter remains a later validation responsibility.

## Walkthrough fixes recorded — 2026-07-26

Manual walkthrough against a live Companion surfaced two defects, both fixed:

- **Dock layout overflow:** the Dock layout was revised to keep the image and controls reachable.
- **Mask 409 on rapid prompting:** `AISelectMaskController` serializes per-view attempts and resubmits the latest full PromptState after the current attempt settles.

Follow-up note: a non-capacity 409 remains a genuine model-level or validation failure and must be inspected by structured code. Current model/runtime interpretation is governed by Ticket 04C.