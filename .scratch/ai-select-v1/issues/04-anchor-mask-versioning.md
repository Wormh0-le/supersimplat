# 04 — Anchor AIView + independent Editing / Stable Mask / Evidence lifecycle

Status: implemented — 2026-07-24

Blocked by: 02

## Final Spec mapping

- Final Spec v1.1 §§7, 10, 11, 18, 24
- DG-08, DG-09, DG-20
- MVP Phase 2

## Inputs / preconditions

- Anchor AIView/RGB identity
- Single-frame SAM runtime
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
- [x] SAM output creates/replaces Editing Mask and never silently overwrites Stable Mask.
- [x] Prompt changes trigger single-frame SAM feedback without an extra apply action.
- [x] Brush strokes update Editing Mask locally.
- [x] Confirm Mask atomically publishes the current Editing Mask as a new Stable Mask revision.
- [x] Until Confirm succeeds, downstream users continue seeing the previous Stable Mask and Evidence/Candidate remain current.
- [x] Publishing a new Stable Mask invalidates only dependent per-view Evidence by exact RGB/Mask/policy identity; if Included, Candidate becomes stale. (Candidate does not exist in 04 — explicit non-goal. The exact-identity Evidence invalidation seam that drives future `liftDirty` is in place and tested; Candidate staleness wiring lands with Ticket 14.)
- [x] Automatic and fully manual masks use the same publication contract.
- [x] Mask artifacts bind to AIView/RGB identity so stale output cannot attach to changed RGB/CameraBinding.
- [x] Render, Mask, Evidence, and Candidate statuses remain distinct. (Candidate status: no Candidate in 04 — non-goal. Render/Mask/Evidence statuses are independent and separately exposed.)

## Failure / recovery criteria

- [x] Mask generation failure keeps View/RGB available and permits retry/manual recovery.
- [x] Partial/stale SAM output is not published as Stable Mask.
- [x] Evidence failure never mutates Stable Mask or View render status.

## Affected seams

- src/ai-select/ai-view*
- src/ai-select/mask*
- src/ai-select/evidence-state*
- AI View Dock selected-view/mask surface
- Companion SAM adapter/runtime

## Validation

- npm test
- npm run lint
- npm run test:companion
- Atomic Stable publication tests
- Editing-no-stale versus Confirm-invalidates-Evidence tests
- Stale RGB/mask binding rejection tests

## Non-goals

- No multi-view propagation
- No production Evidence kernel
- No Candidate/lifting
- No full mask-history UX

## What was built — 2026-07-24

Editor (TypeScript, `src/ai-select/`):

- `mask-annotation.ts` — versioned `MaskAnnotation`/`MaskArtifact` (`bitset-lsb-v1` + `sha256:` digest of decoded bytes), `MaskPrompt`, trust-boundary validators, bitset decode/encode, and local disc brush strokes.
- `mask-registry.ts` — pure per-view Mask domain: SAM results create/replace only the Editing Mask; brush edits create `manual`/`hybrid` local revisions (an out-of-RGB brush starts a fresh manual chain); Confirm Mask atomically publishes the Editing Mask as a new `user-confirmed` Stable revision (synchronous pointer swap; previous Stable version retained). Currency derives from `createdFromRgbDigest`, so stale masks never attach to changed RGB.
- `evidence-state.ts` — per-view Evidence dependency identity (`viewId`, `rgbDigest`, `stableMaskDigest`, `evidencePolicyDigest`) and derived status (`not-requested/pending/ready/stale/failed`). Ready/pending records whose exact identity no longer matches derive `stale`; failures bound to superseded inputs read as not-requested. `aiSelectEvidencePolicyVersion = 'evidence-policy/pnv-v0'` is an identity seam only — no calibrated policy exists yet (Ticket 20).
- `ai-view.ts` — the Final Spec §7 `AIView` record and `composeAnchorAIView`, exposing independent `renderStatus`, `editingMaskId`/`stableMaskId`, and `evidenceStatus`. Anchor `participation` is fixed `included` until Ticket 07.
- `mask-service.ts` — the single-frame SAM transport contract: request binds full async identity + exact RGB artifact + prompt set + `maskAttemptId`; response matching fails closed on any stale identity, dimension, or digest-of-bytes mismatch.
- `mask-controller.ts` — `AISelectMaskController`: prompt changes auto-submit the full prompt set (latest-only; no extra apply action), local brush supersedes in-flight SAM, Confirm publishes atomically and derives Evidence invalidation, Retry mints a new `maskAttemptId`, Restart/RGB-change disposes target-local Mask state by identity.
- `anchor-controller.ts` — narrow seam only: `createAnchorMaskRequest` (null unless exact full-resolution RGB Ready) and `acceptsMaskResponse` (context/rgb-digest freshness gate).
- `anchor-dock-presentation.ts` — Mask surface (`none/pending/draft/confirmed/failed` + prompt count + evidenceStatus + confirm/retry affordances), kept distinct from render status.
- `ui/ai-select-anchor-dock.ts` — Dock renders the Mask surface, a tinted Mask overlay aligned to the `object-fit: contain` image, click = include prompt, Shift+click = exclude prompt, drag = brush add, Shift+drag = brush erase (only when the formal RGB is `ready`), plus Confirm Mask / Retry Mask actions.
- `selection-service-fetch-adapter.ts` + `selection-service-readiness.ts` — `produceMask` transport (POST `/ai-select/masks`, manifest assertion, fail-closed validation) behind the readiness gate; `main.ts` wiring; `ai-select.mask.*` locale keys in all 9 locales.

Companion (Python):

- `POST /ai-select/masks` → `CompanionState.produce_ai_select_mask`: full request validation (dependency binding, `sha256` RGB digest against decoded PNG bytes, in-bounds prompts), `_require_mask_adapter`, single-operation admission with idempotent same-attempt replay and new-attempt re-execution (`maskAttemptId`), a synthetic single-view `RegisteredFrameSet` so `Sam3PointMaskAdapter` performs exactly one SAM pass with no propagation, complete-tracks validation, and a bitset digest bound to the decoded bytes. `MaskSessionError` → 409 `maskError`; validation `ValueError` → 400 `invalidRequest` (the route matches `MaskSessionError` first because it subclasses `ValueError`).

Decisions recorded:

- Editing Masks are `draft`; SAM quality labels (`auto-good`/`auto-review`) are not fabricated before evidence-backed View Assessment (Ticket 07). Confirm publishes `user-confirmed`.
- Brush while a SAM request is in flight supersedes that request; the late response is discarded rather than clobbering the local edit.
- Evidence registry is exposed (`evidenceRegistry`) for Ticket 20 to drive; nothing produces Evidence in 04.

## Validation recorded — 2026-07-24

- `npm test` — 170 editor tests pass, including atomic Stable publication (`ai-select-mask-registry.test.js`), Editing-no-stale versus Confirm-invalidates-Evidence (`ai-select-mask-controller.test.js` "Confirm Mask invalidates dependent Evidence only at publication"), stale RGB/mask binding rejection (`ai-select-mask-service.test.js`, mask-controller stale-response cases, fetch-adapter produceMask cases).
- `npm run test:companion` — 197 tests pass (16 new in `tests/test_ai_select_masks.py`: route validation, digest/prompt rejection, no-candidate, idempotent replay vs new-attempt, capacity, invalid-artifact failure).
- `npm run lint` — clean (172 TS files); `npm run lint:locales` — 356 keys in sync; `npm run build` — success.
- SAM ran against the fake predictor only. Real SAM 3.1 weights/GPU were not exercised in this environment; the single-frame path is contract-tested, not production-model validated.

Known gaps / handoff notes:

- `_render_ai_select_anchor` in `server.py` listed `except ValueError` before `except MaskSessionError`, making its 409 `anchorRenderError` branch unreachable (pre-existing, discovered during 04). **Fixed 2026-07-26 in `aa74484`** with HTTP regression tests (renderer failure and `capacityFull` now map to 409).
- Manual browser walkthrough of the Dock prompt/brush/Confirm flow (with a live Companion) has not run in this environment.

## Walkthrough fixes recorded — 2026-07-26

Manual walkthrough against a live Companion surfaced two defects, both fixed:

- **Dock layout overflow** (image bottom unclickable + buttons clipped): the vertical dock stack (~360px of content) exceeded its 260px max-height; the flex-shrunk `imageWrap` let the fixed-height `img` overflow beneath the transparent status/button rows, so the photo's lower strip swallowed no clicks and showed no crosshair cursor, and the Validate/Confirm row was clipped at the panel edge. The dock is now a horizontal main row (image left with `height: 100%` + `overflow: hidden`, a 340px scrollable controls column right), and panel/dock max-height is `min(280px, 50vh)`.
- **Mask 409 on rapid prompting**: every prompt click submitted a new concurrent SAM attempt, which the Companion's single operation slot rejects with `409 capacityFull`. `AISelectMaskController` now serializes per-view SAM attempts: a prompt arriving mid-flight supersedes the in-flight attempt locally and resubmits the latest full prompt set as a fresh `maskAttemptId` when it settles. The test that encoded concurrent submission was replaced with serialized semantics; regression tests cover failure-then-resubmit and no-spurious-resubmit.

Follow-up note: if a mask request still returns 409 with `code` other than `capacityFull` (e.g. `anchorMaskUnavailable` — SAM rejected the prompt candidate), that is a genuine model-level failure surfaced by design; check the response body / Companion log for the `code` before treating it as a transport bug.
