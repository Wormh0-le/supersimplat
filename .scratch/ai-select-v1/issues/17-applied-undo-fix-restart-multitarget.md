# 17 — Applied Undo-and-Fix + complete Restart + multi-object/tool-switch lifecycle

Status: ready-for-agent

Blocked by: 16, 05, 03

## Final Spec mapping

- DG-11
- DG-15 applied correction
- DG-16
- §69–71 Context lifecycle
- Typical Flows F/H

## Inputs / preconditions

- Candidate Applied/Ready
- CandidateApplicationRecord
- Early Restart primitive
- Native EditHistory

## Outputs / handoff artifacts

- Undo and Fix
- Restart at all stages
- Continuous multi-object flow
- Tool-switch disposal

## What to build

Complete target lifecycle after application and extend Early Restart to all late stages. Preserve Native
Selection/EditHistory as durable cross-target truth; never introduce a previous-AI-target session stack.

## Acceptance criteria

- [ ] `Undo and Fix` is available only when the associated AI Select native history command is safely undoable/top-of-stack.
- [ ] `Undo and Fix` performs Native Undo of that associated SelectOp, keeps AI context alive, and enters the Candidate correction flow.
- [ ] If later native edits exist after the AI operation, `Undo and Fix` is unavailable; no hidden history traversal occurs.
- [ ] Restart Current Target is available in Generated Views, Mask Review, Propagation Stale, Candidate Stale, Candidate Ready, and Candidate Applied in addition to early stages.
- [ ] Restart clears target-local Anchor/Views/Masks/Review/Coverage/Readiness/Lift/Candidate/Uncertain/Gallery state while preserving Native Selection/EditHistory, AI Select active state, Scene View, planner/tool policy, and shared runtime caches.
- [ ] Candidate Applied requires no confirmation solely to protect the already-committed Native Selection result.
- [ ] Restart always rotates targetContextId; old async work cannot publish into the new target.
- [ ] Consecutive target flow supports A Candidate → Add → Restart → B → Add → Restart → C without hidden Add mode.
- [ ] Durable cross-target result is Native Selection/EditHistory only; old AI target contexts are not resurrected by Native Undo/Redo.
- [ ] User-added Views are target-local and disappear on Restart; shared render/model caches may be reused only by valid dependency identity.
- [ ] Dock/Gallery/Mask-tool target-local visual state resets to safe defaults on Restart.
- [ ] Switching to a different native selection/tool exits/disposes active AI target context according to v1.0; no persistent AI session tabs/history are created.

## Failure / recovery criteria

- [ ] Late async work after Restart is discarded by targetContextId/dependency mismatch.
- [ ] Unsafe Undo-and-Fix is disabled rather than traversing history.

## Affected seams

- src/ai-select/current-target-context*
- src/ai-select/application-record*
- Native EditHistory integration
- Tool manager integration
- Contextual toolbar/overflow

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- A/B/C multi-target workflow
- Safe/unsafe Undo-and-Fix tests

## Non-goals

- No previous-target AI history browser
- No Candidate clipboard
