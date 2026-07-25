# 05 — Anchor editing + support validation + atomic Confirm Anchor + early Restart

Status: implemented — 2026-07-25

Blocked by: 03, 04

## Final Spec mapping

- Final Spec v1.1 §§10–12, 24
- DG-09, DG-11, DG-12, DG-20
- MVP Phase 2

## Inputs / preconditions

- RGB-ready Anchor AIView
- Editing/Stable Mask
- Camera Inspection
- CurrentTargetContext
- Stable Gaussian ID / Render Working Set support-probe seam

## Outputs / handoff artifacts

- Complete Anchor authoring flow
- Validated/confirmed Anchor revision
- Versioned mask-conditioned Gaussian support result
- Early Restart flow

## What to build

Complete Anchor authoring and recovery. Anchor validation proves computability and coherent Camera/RGB/Mask/support identity. Confirm Anchor no longer requires complete Contributor publication or formal multi-view Evidence.

The support probe is a cheap computability gate, not a hidden lifting implementation. It must not reintroduce complete Contributor production into Anchor confirmation.

## Acceptance criteria

- [x] Prompt refine and Brush Add/Erase modify only Editing Mask until Confirm Mask.
- [x] Clear creates an empty Editing Mask; Restore Auto restores the latest valid auto mask and is disabled when none exists.
- [x] Fully manual Clear → Brush → Confirm produces User Confirmed Stable Mask.
- [x] Mask Editor has independent Undo/Redo with explicit focus routing.
- [x] Anchor Validation evaluates computational suitability, not semantic target confidence.
- [x] Hard validation blocks unavailable authoritative RGB, empty/nearly-empty Mask, no computable Gaussian support, pending latest Mask/SAM revision, invalid Stable ID/Render Working Set, or mismatched Camera/RGB/Mask identity.
- [x] Gaussian support is obtained from a versioned low-cost support/visibility probe with explicit input identity; it is not complete Contributor publication and is not formal P/N/V Evidence.
- [x] The support probe may answer only whether useful Gaussian support is computable/observable under the declared policy; it must not classify Selected/Rejected ownership or become a Candidate source.
- [x] The normal Confirm Anchor path does not invoke the complete Contributor backend. Any reference operation used for diagnostics is explicit, bounded, and outside the product hard gate.
- [x] Soft warnings such as image-boundary contact, extreme size, fragmentation, or weak visible support remain user-overridable.
- [x] Validation refreshes against the latest exact revisions and never confirms stale output.
- [x] Changing Anchor after target intent warns before discarding unconfirmed Prompt/Editing state.
- [x] Confirm Anchor atomically publishes CameraBinding, RGB digest, Stable Mask+digest, Mask Evidence Policy version, TargetDependencyToken, and Scene/Splat identity.
- [x] Complete Contributor identity is not part of the formal Anchor binding.
- [x] Formal per-view/multi-view Evidence and Candidate are not prerequisites for Confirm Anchor.
- [x] Confirmed Anchor remains locked until an explicit allowed adjustment/restart flow.
- [x] Restart is available during Anchor Draft, Camera Inspection, Mask Editing, validation, and confirmed-Anchor early stages.
- [x] Early Restart disposes target-local Anchor/View/Mask/Evidence-status/review/readiness state, rotates targetContextId, and preserves Native Selection/EditHistory/policy/runtime caches.
- [x] Restart during Camera Inspection restores saved Scene View before constructing the new Anchor.
- [x] Restart confirmation states clearly that Native Selection does not change.

## Failure / recovery criteria

- [x] Mask/SAM failure preserves View/RGB and supports Retry Auto Mask / Manual Draw / later Exclude.
- [x] Support-probe/validation failure offers Fix Mask / Adjust Anchor / Restart and does not relabel RGB as Render Failed.
- [x] Unavailable debug/reference Contributor data does not make an otherwise computable Anchor invalid.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion for support-probe/SAM changes
- Binding mismatch and no-complete-Contributor Confirm tests
- Test that support probe cannot publish Candidate/Evidence or call the production reference-Contributor path implicitly
- Manual focus/restart walkthrough

## Non-goals

- No Generated Views beyond Confirm transition
- No formal P/N/V artifact
- No Candidate
- No complete Contributor production or tolerance tuning

## Implementation recorded — 2026-07-25

Editor (TypeScript):

- `src/ai-select/mask-registry.ts` — `clearEditing`, `restoreEditing`, `latestAutoMask`: Clear publishes an empty manual draft; Restore Auto / mask-local Undo/Redo navigate retained Editing-chain versions only (never Stable versions, never across RGB identity).
- `src/ai-select/mask-controller.ts` — Clear / Restore Auto / `undoMaskEdit` / `redoMaskEdit` with mask-local Undo/Redo stacks reset on RGB/context identity change; `canUndo`/`canRedo`/`canRestoreAuto`/`hasUnconfirmedChanges` surface; `isAnchorLocked` gate rejects every Mask mutation while the Anchor is confirmed.
- `src/ai-select/mask-analysis.ts` — union-find 4-connected component/area/boundary analysis (near-linear; review fix replaced the first O(n^2) labelling pass).
- `src/ai-select/anchor-validation.ts` — versioned `anchor-validation/v1` policy: 11 hard blocks, 5 soft warnings, thresholds as exported constants.
- `src/ai-select/support-probe.ts` — versioned `anchor-support-probe/v1` contract. The response `support` payload validates to exactly `{computable, observedGaussianCount}`; any Stable-ID/ownership/Evidence-shaped field fails closed at the boundary.
- `src/ai-select/anchor-confirmation.ts` — `AISelectAnchorConfirmationController`: local hard/soft evaluation → support probe (only when all local prerequisites hold) → fresh re-validation on every Confirm → atomic `ConfirmedAnchor` publication (CameraBinding, RGB digest, Stable Mask+digest, Mask Evidence Policy version, TargetDependencyToken, Scene/Splat identity; no Contributor identity). Locked until `adjustAnchor()` or Restart; stale probe verdicts discarded by identity.
- `src/ai-select/anchor-controller.ts` — `createAnchorSupportProbeRequest` / `acceptsSupportProbeResponse` / `getAnchorSceneIdentity` seams; CameraBinding changes rejected while locked.
- Transport — `POST /ai-select/anchor-support-probes` through `selection-service-fetch-adapter.ts` (packed + spatial scene cache/chunk-miss recovery identical to the Anchor render path) and `selection-service-readiness.ts` (readiness gate).
- UI — Dock: Clear / Restore Auto / Undo / Redo / Validate / Confirm Anchor / Adjust Anchor controls, validation block+warning surface, Mask-Editor keyboard focus routing (Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y while the Dock holds focus); Toolbar Restart behind a yes/no popup stating Native Selection does not change; Adjust/Reset Anchor behind a discard warning when unconfirmed Prompt/Editing state exists; 9 locales updated.

Companion (Python):

- `selection-service-companion/src/selection_service_companion/support_probe.py` — pure-CPU `anchor-support-probe/v1` policy: OpenCV world→camera transform, near/far gate, rounded pinhole pixel, `logitOpacity >= 0` opacity gate, LSB-first mask-bit test. No torch/numpy/gsplat imports; no renderer involvement; no P/N/V or Contributor computation.
- `state.py` / `server.py` — request parsing (mask structure + digest verified), packed and spatial scene resolution with `sceneCacheMiss`/`sceneChunkMiss` fail-closed, same-attempt idempotent replay vs new-attempt re-execution, single global operation slot extended to probes (`_operation_slot_in_use_locked`), `aiSelectAnchorSupportProbe` capability, 409 `supportProbeError` / 400 `invalidRequest` mapping.

## Validation recorded — 2026-07-25

- `npm test` — 224 editor tests pass, including: registry Clear/restore/latest-auto; controller Clear supersedes in-flight SAM, Restore Auto disabled-state, mask-local Undo/Redo chains, locked-Anchor rejection of every Mask mutation; validation hard/soft policy table; support-probe fail-closed protocol (identity drift, ownership payload rejection); Confirm Anchor binding/lock/stale-probe/re-validation cases; fetch-adapter probe route (packed + spatial miss recovery, stale/ownership responses rejected before publication).
- `npm run test:companion` — 215 tests pass (18 new in `tests/test_ai_select_support_probe.py`: pure-policy projection/opacity/mask semantics, route validation, idempotent replay vs new attempt, packed + spatial paths, chunk miss, exact two-field support payload).
- `npm run lint` — clean (176 TS files); `npm run lint:locales` — 384 keys in sync across 9 locales; `npm run build` — success.
- Two-axis `/code-review` (Standards + Spec) ran against the working tree; findings fixed: O(n^2) mask component labelling → union-find, duplicated `copyDependencyToken`/digest-validation/operation-slot predicate extracted, misleading probe-admission comment corrected, missing Adjust Anchor control added to the Dock.

Known gaps / handoff notes:

- The support probe is a CPU center-projection visibility probe, as §12.2 permits; it is not the same-decision production Evidence path and must not grow ownership semantics. Ticket 20 owns the formal P/N/V path.
- `camera-binding-stale` currently fires only through dependency-token suspension; in-context CameraBinding drift is already excluded because RGB re-renders bind the exact current binding.
- No GPU validation ran (the probe is pure CPU; the locked renderer runtime is not on its path). No manual browser walkthrough of the Dock/Confirm/Restart flows in this environment.
