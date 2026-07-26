# 06 — First progressive Generated AIView + Initial Auto Mask

Status: implemented — 2026-07-25

Blocked by: 05

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27, 28
- DG-08, DG-13, DG-20
- MVP Phase 3

## Inputs / preconditions

- Confirmed coherent Anchor revision
- Compatible Generated View planner primitives
- Authoritative gsplat RGB renderer
- SAM propagation/single-frame fallback

## Outputs / handoff artifacts

- First planner-owned Generated AIView
- Authoritative RGB identity
- Initial Auto Mask state
- Evidence=`not-requested`/later-derived state
- Generated frustum

## What to build

Prove progressive multi-view publication end to end. Publish a Generated AIView as soon as authoritative RGB is ready. Produce its Mask independently. Evidence is mask-conditioned and is not part of initial View rendering/publication.

## Acceptance criteria

- [x] Confirm Anchor can start automatic planning without fixed user View count.
- [x] At least one planner-owned Generated AIView publishes when authoritative gsplat RGB is ready.
- [x] Generated AIView has stable viewId, source, CameraBinding, RGB identity, independent render/mask/evidence states, and Participation.
- [x] RGB comes from authoritative gsplat and frustum derives from the exact CameraBinding.
- [x] View publication does not move Editor Camera.
- [x] Gallery may show RGB Ready while Mask is Generating and Evidence is Not Requested.
- [x] Complete Contributor is not required for Generated View Render Ready.
- [x] Once RGB is ready, automatic Mask production starts without blocking the View.
- [x] Successful Mask production atomically publishes an auto Stable Mask bound to AIView/RGB.
- [x] Publishing Stable Mask marks corresponding Evidence missing/dirty; it does not automatically perform formal Lift.
- [x] Mask failure keeps AIView/RGB/frustum and produces RGB Ready + Mask Failed, not View Failed.
- [x] Evidence failure, when later attempted, keeps View Render Ready.
- [x] Render failure remains distinct and preserves a failed View record.
- [x] Completed Views survive later planner failure.
- [x] Late render/mask results with obsolete bindings are discarded.
- [x] Generated frustum is selectable and read-only.

## Failure / recovery criteria

- [x] Mask failure exposes retry/manual/exclude as later controls become available.
- [x] View Render Failure exposes true Retry; replacement and Exclude complete in later tickets.
- [x] No partial Mask or Evidence is published stable.

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Locked GPU: RGB Ready → Mask Generating → Auto Stable/Failed
- RGB Ready without Contributor/Evidence fixture

## Non-goals

- No full adaptive stop policy
- No scalable Gallery
- No formal Evidence production or cross-view assessment

## Implementation recorded — 2026-07-25

Editor (TypeScript):

- `src/ai-select/generated-view-service.ts` — versioned protocol contracts `generated-view-planner/v1` and `generated-view-mask/v1`: plan / view-render / propagated-mask request+response types with fail-closed structural validators and request-echo matchers (PNG envelope + dimensions verified against the bound CameraBinding; mask artifact digest verified against decoded bytes; `anchor-view` reserved for the Anchor route).
- `src/ai-select/generated-view-controller.ts` — `AISelectGeneratedViewController`: Confirm Anchor starts automatic planning bound to the exact confirmed-Anchor identity (context/revision, RGB digest, Stable Mask digest, Scene identity). Each planned View publishes the moment authoritative gsplat RGB is Ready (RGB Ready + Mask Generating + Evidence `not-requested` is a legal Gallery state); automatic Mask production follows per View without blocking publication; a successful Mask atomically publishes an auto Stable Mask (`auto-review`, Participation `excluded` — the §13 fail-closed default until Ticket 07 assessment); Evidence stays derived-missing and no Lift runs. Render and Mask failures are contained per View; completed Views survive; a true render Retry mints a new `renderAttemptId` for the exact same planned CameraBinding; planning Retry mints a new `planAttemptId`. Adjust/Restart rotates the run identity and disposes all target-local Views/Masks; late plan/render/mask results are discarded by run ordinal + the shared target kernel gate (`anchor.acceptsTargetBinding`).
- `src/ai-select/mask-registry.ts` — `publishAutoStable`: atomic automatic Stable Mask publication (no Editing chain), chained from the previous Stable revision, digest-bound artifact re-verified.
- `src/ai-select/anchor-controller.ts` — `acceptsTargetBinding` (shared kernel stale-result gate) and `getAnchorSnapshot` (active Scene Snapshot seam).
- `src/ai-select/mask-controller.ts` — the single per-context Mask registry is now shared as `maskRegistry` so Mask identities never fork across views.
- `src/ai-select/generated-frustum-picking.ts` — renderer-free frustum line derivation from the exact CameraBinding plus nearest-segment picking with behind-camera culling.
- `src/ai-select-generated-frustums.ts` — read-only debug element drawing every Generated Frustum with selection highlight; never observes or moves the Editor Camera.
- UI — `src/ui/ai-select-anchor-dock.ts` AI View Gallery strip: Anchor card + per-View cards (thumbnail, localized Render/Mask/Evidence status lines, Retry Render on failed Views, selection highlight) and the planner status line with Retry Planning; `src/ui/scss/ai-select.scss`; 9 locales.
- `src/main.ts` — controller composition, Generated Frustum visibility, and click-vs-drag (≤4px) frustum picking for Gallery ↔ Frustum selection sync. The Editor Camera is never moved.
- Transport — `POST /ai-select/generated-view-plans`, `/ai-select/view-renders`, `/ai-select/generated-view-masks` through `selection-service-fetch-adapter.ts` (packed + spatial scene cache/chunk-miss recovery identical to the Anchor render/support-probe paths; authoritative RGB digest verified browser-side) and `selection-service-readiness.ts` (readiness gate). Older Companions without the additive `aiSelectGeneratedViewPlanning` capability keep the Anchor flow; planning fails closed with an actionable diagnostic.

Companion (Python):

- `selection-service-companion/src/selection_service_companion/generated_view_planning.py` — pure-CPU `generated-view-planner/v1` + `generated-view-mask/v1` policies: mask-conditioned Gaussian support collection (support-probe gating parity), robust Seed Region (median center, separated-support rejection), deterministic anchor-relative orbit (first ±45° ring neighbours, `GENERATED_VIEW_PLAN_COUNT = 2`), CameraBinding-convention camera construction, and deterministic cross-view prompt synthesis. No torch/numpy/gsplat imports; no renderer involvement; no Stable ID or ownership output.
- `state.py` / `server.py` — three routes with the established request parsing (digest-verified mask, camera orthonormality), packed + spatial scene resolution shared via `_resolve_ai_select_scene_planes` with `sceneCacheMiss`/`sceneChunkMiss` fail-closed, same-attempt idempotent replay vs new-attempt re-execution, the single global operation slot extended to plans and propagated masks, `aiSelectGeneratedViewPlanning` capability, 409 `plannerError` / `viewRenderError` / `maskError` and 400 `invalidRequest` mapping (the new view-render route matches MaskSessionError before ValueError so renderer failures stay 409). The propagated Mask path projects Anchor support into the Generated View camera, synthesizes include prompts, and runs exactly one single-frame SAM pass; `maskPropagation` diagnostics (projected support count, prompt count) are retained for Ticket 07 assessment. `anchor-view` is rejected on both Generated View routes.

## Validation recorded — 2026-07-25

- `npm test` — 268 editor tests pass, including: registry auto-Stable publication/atomic replacement/digest closure; protocol validators for all three contracts; the full controller lifecycle (automatic planning on Confirm, progressive RGB-Ready-before-Mask publication, auto Stable Mask binding, Mask/Render failure isolation, true render/planning Retry, Adjust/Restart disposal, stale-binding discard, selection); frustum line/picking math; fetch-adapter routes (packed + spatial miss recovery, stale binding rejection).
- `npm run test:companion` — 232 tests pass (17 new in `tests/test_ai_select_generated_views.py`: seed derivation gating/robust framing, orbit geometry/determinism, prompt synthesis, plan/view-render/generated-mask route behavior, cache miss, replay without a second SAM pass, propagation-unavailable 409, reserved-view-id and digest rejection).
- `npm run lint` — clean (180 TS files); `npm run lint:locales` — 399 keys in sync across 9 locales; `npm run build` — success.
- Two-axis `/code-review` (Standards + Spec) ran against the working tree; findings fixed: dead `rgb` parameter in the mask step, undiscriminating pointerdown picking (now click-vs-drag), latent dynamic evidence locale key, misleading admission replay comments.

Known gaps / handoff notes:

- Mask Failed exposes Retry Auto Mask / Manual Draw / Exclude only as later tickets add the controls (Ticket 07/12); the failure state itself is preserved with the View.
- A dependency-token suspension mid-run discards in-flight steps via the kernel gate but leaves their transient states wedged (same behavior as the Ticket 05 Anchor path); Ticket 18 owns suspension/restoration UX.
- The planner publishes a fixed first ring-neighbour pair (`GENERATED_VIEW_PLAN_COUNT = 2`); Ticket 08 owns the adaptive coverage-driven stop policy and larger budgets.
- The fetch-adapter scene-miss recovery loops now exist in five near-identical copies (Anchor render/probe + these three); extraction deferred as cross-ticket churn.
- The legacy Anchor render route maps renderer failures to 400 (ValueError before MaskSessionError — its 409 branch is unreachable); left untouched here, the new view-render route maps them to 409 correctly.
- No GPU validation ran in this environment: planning/propagation policies are pure CPU and the render path reuses the locked-renderer seam with a fixture renderer, but production GPU behavior (RGB Ready → Mask Generating → Auto Stable/Failed on the locked runtime) is unverified. No manual browser walkthrough of the Gallery/frustum picking in this environment.
