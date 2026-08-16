# 17 — Applied Undo-and-Fix + complete Restart + multi-object/tool-switch lifecycle

Status: current — ready after implemented Ticket 16G

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

- [ ] Undo and Fix is available only when the associated native command is safely top-of-stack/undoable.
- [ ] Undo and Fix occupies the accepted slot after Intersect in the fixed AI
      Select Toolbar; it is not rendered before its native history behavior
      exists.
- [ ] It performs Native Undo, keeps AI context alive, and enters Candidate correction.
- [ ] Later native edits disable Undo and Fix; no hidden history traversal.
- [ ] Restart is available across Generated Views, Review, Mask/Evidence/Lift dirty, Candidate Stale/Ready/Applied.
- [ ] Restart is not reintroduced through the removed 3D Toolbar More menu or
      as a persistent AI Select viewport control.
- [ ] The internal `Restart Current Target` semantic is presented to users as
      `选择另一个对象` in the global AI Select tool's lifecycle menu, alongside
      tool exit rather than inside the contextual 3D sub-toolbar.
- [ ] The lifecycle-menu trigger follows the reusable button rule: compact
      icon-only presentation, project tooltip, accessible name, visible focus
      and at least `40×40px` hit area. Menu entries may retain icon plus text
      where scanability and destructive consequence require it.
- [ ] `选择另一个对象` explains that it clears the current AI target context but
      preserves Native Selection/EditHistory, and requests confirmation when
      needed by the existing destructive-action policy.
- [ ] Restart clears target-local Anchor/Views/Masks/Evidence artifacts/status/Review/Coverage/Readiness/Lift/Candidate/Uncertain/Gallery.
- [ ] Restart preserves Native Selection/EditHistory, AI Select activation, Scene View, policies, and valid shared runtime caches.
- [ ] Candidate Applied needs no confirmation solely to protect already committed Native Selection.
- [ ] Restart rotates targetContextId; old async work cannot publish.
- [ ] A→Add→Restart→B→Add→Restart→C works without implicit Add mode.
- [ ] Native Selection/EditHistory are the only durable cross-target result; old AI contexts are not resurrected.
- [ ] User-added Views and per-target Evidence disappear on Restart; shared caches require exact identity.
- [ ] Dock/Gallery/Mask/Evidence UI resets safely.
- [ ] Tool switch disposes active AI target context; no persistent session tabs/history.

## Failure / recovery criteria

- [ ] Late render/Mask/Evidence/Lift work after Restart is discarded by identity mismatch.
- [ ] Unsafe Undo and Fix is disabled.

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
