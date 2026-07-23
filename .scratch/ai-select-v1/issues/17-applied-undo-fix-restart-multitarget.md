# 17 — Applied Undo-and-Fix + complete Restart + multi-object/tool-switch lifecycle

Status: ready-for-agent — v2.2 re-audited

Blocked by: 16, 05, 03

## Final Spec mapping

- Final Spec v1.1 §25 and inherited v1.0 lifecycle rules
- DG-11, DG-15, DG-16, DG-20
- Typical Flows F/H

## Inputs / preconditions

- Candidate Applied/Ready
- CandidateApplicationRecord
- Early Restart primitive
- Native EditHistory
- Per-view Evidence/Candidate target-local state

## Outputs / handoff artifacts

- Undo and Fix
- Restart at all stages
- Continuous multi-object flow
- Tool-switch disposal

## What to build

Complete lifecycle after application. Native Selection/EditHistory are durable cross-target truth; Anchor/View/Mask/Evidence/Candidate state remains target-local.

## Acceptance criteria

- [ ] Undo and Fix is available only when the associated native command is safely top-of-stack/undoable.
- [ ] It performs Native Undo, keeps AI context alive, and enters Candidate correction.
- [ ] Later native edits disable Undo and Fix; no hidden history traversal.
- [ ] Restart is available across Generated Views, Review, Propagation/Evidence/Lift dirty, Candidate Stale/Ready/Applied.
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

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- A/B/C multi-target workflow
- Restart with pending Evidence/Lift
- Safe/unsafe Undo and Fix tests

## Non-goals

- No previous-target AI history browser
- No Candidate clipboard