# 17 — Applied Undo-and-Fix + complete Restart + multi-object/tool-switch lifecycle

Status: implemented — 2026-08-17

Prerequisites: 16G, 16, 05, 03 (implemented)

## Current Final Spec mapping

- Final Spec v1.3 §§4, 19, 22, 24
- DG-11, DG-15, DG-16 and DG-20 as historical lifecycle rationale where not superseded
- Historical Typical Flows F/H as implementation provenance

Final Spec v1.3 is the only current closure source.

## Inputs / preconditions

- Candidate Applied/Ready
- CandidateApplicationRecord
- Early Restart primitive
- Native EditHistory
- Per-view Evidence/Candidate target-local state
- Ticket 16G final Candidate Overlay, compact Toolbar and shared presentation
  seam after the post-16A visual-review corrections

## Outputs / handoff artifacts

- Undo and Fix
- Restart at all stages
- Global AI Select target-lifecycle menu
- Continuous multi-object flow
- Tool-switch disposal

## What to build

Complete lifecycle after application. Native Selection/EditHistory are durable cross-target truth; Anchor/View/Mask/Evidence/Candidate state remains target-local.

## Acceptance criteria

- [x] Undo and Fix is available only when the associated native command is safely top-of-stack/undoable.
- [x] Undo and Fix occupies the accepted slot after Intersect in the fixed AI
      Select Toolbar; it is not rendered before its native history behavior
      exists.
- [x] It performs Native Undo, keeps AI context alive, and enters Candidate correction.
- [x] Later native edits disable Undo and Fix; no hidden history traversal.
- [x] Restart is available across Generated Views, Review, Mask/Evidence/Lift dirty, Candidate Stale/Ready/Applied.
- [x] Restart is not reintroduced through the removed 3D Toolbar More menu or
      as a persistent AI Select viewport control.
- [x] The internal `Restart Current Target` semantic is presented to users as
      `选择另一个对象` in the global AI Select tool's lifecycle menu, alongside
      tool exit rather than inside the contextual 3D sub-toolbar.
- [x] The lifecycle-menu trigger follows the reusable button rule: compact
      icon-only presentation, project tooltip, accessible name, visible focus
      and at least `40×40px` hit area. Menu entries may retain icon plus text
      where scanability and destructive consequence require it.
- [x] `选择另一个对象` explains that it clears the current AI target context but
      preserves Native Selection/EditHistory, and requests confirmation when
      needed by the existing destructive-action policy.
- [x] Restart clears target-local Anchor/Views/Masks/Evidence artifacts/status/Review/Coverage/Readiness/Lift/Candidate/Uncertain/Gallery.
- [x] Restart preserves Native Selection/EditHistory, AI Select activation, Scene View, policies, and valid shared runtime caches.
- [x] Candidate Applied needs no confirmation solely to protect already committed Native Selection.
- [x] Restart rotates targetContextId; old async work cannot publish.
- [x] A→Add→Restart→B→Add→Restart→C works without implicit Add mode.
- [x] Native Selection/EditHistory are the only durable cross-target result; old AI contexts are not resurrected.
- [x] User-added Views and per-target Evidence disappear on Restart; shared caches require exact identity.
- [x] Dock/Gallery/Mask/Evidence UI resets safely.
- [x] Tool switch disposes active AI target context; no persistent session tabs/history.

## Failure / recovery criteria

- [x] Late render/Mask/Evidence/Lift work after Restart is discarded by identity mismatch.
- [x] Unsafe Undo and Fix is disabled.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- `rtk npm run build`
- A/B/C multi-target workflow
- Restart with pending Evidence/Lift
- Safe/unsafe Undo and Fix tests
- Global lifecycle-menu ownership, tooltip, focus restoration and accessible-
  name tests

## Non-goals

- No previous-target AI history browser
- No Candidate clipboard
- No reimplementation of Ticket 16 application algebra or Ticket 16G Candidate
  Overlay/Toolbar/presentation ownership

## Implementation record

- Added an exact-command EditHistory seam that reports whether a command is
  top-of-stack, applied below later native work, or unapplied. `Undo and Fix`
  rechecks the exact command inside the shared history queue, performs one
  Native Undo, and enters Candidate Correction without traversing unrelated
  history or disposing the current AI context.
- Added the fixed Toolbar slot after Intersect with a real Undo SVG,
  tooltip/ARIA labels and history-specific disabled reasons. Ordinary Native
  Undo/Redo now refreshes the shared Candidate presentation.
- Added the global AI Select lifecycle menu. Its trigger remains the icon for
  the AI Select tool itself; `选择另一个对象` and tool exit remain scanable
  icon-plus-text menu commands rather than becoming a new global icon mode.
- Restart confirmation follows the existing destructive-state policy:
  unconfirmed drafts and confirmed AI context are protected, while Candidate
  Applied alone needs no confirmation because Native Selection/EditHistory are
  preserved.
- Restart reuses the established CurrentTargetContext restart primitive, so
  target identity rotates and existing Anchor/View/Mask/Evidence/Lift/
  Candidate subscriptions dispose target-local state and reject late work.
  Tool exit additionally closes only the AI Select panel.
- This Ticket changes browser editor state/UI and documentation only. It adds
  no Companion, renderer, CUDA, Evidence algorithm or production GPU claim.

## Validation record

- `rtk npm test` passed: 618 editor tests and 446 Companion tests, with one
  existing Companion skip.
- `rtk npm run lint`, `rtk npm run lint:locales` (8 translated locales aligned
  with 561 English keys), `rtk npm run build` and `rtk git diff --check` passed.
- Focused tests passed for safe/unsafe Undo-and-Fix, native Undo/Redo
  presentation refresh, exact queued history validation, pending Lift reset,
  restart confirmation policy, A/B/C explicit Add continuity, target-context
  rotation, lifecycle-menu ownership/accessibility/focus and tool-switch
  disposal.
- Existing restart suites continue to cover Anchor late-response rejection,
  in-flight Mask cancellation, Generated View/Mask disposal and target-local
  Evidence/Candidate reset. Touched-document link checks and the v2.33
  manifest/frontier closure check passed.
- No locked-GPU validation ran or was required: Ticket 17 changes the browser
  editor lifecycle/UI around existing identity-bound renderer and Evidence
  behavior, not that behavior itself.
