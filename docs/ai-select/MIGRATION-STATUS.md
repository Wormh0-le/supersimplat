# AI Select Documentation Migration Status

Status: **substantive migration complete; historical scratch paths are compatibility-only**

## Completed

- Stable AI Select planning root established at `docs/ai-select/`.
- Full 31-parent-ticket Final Spec v1.3 mapping restored and promoted.
- Ticket graph and control plane promoted through v2.34 with ADR 0018, the
  implemented single-result / `4–8` initial automatic-View contract. The
  complete Ticket 16A–16G presentation and obsolete-control closure is
  recorded, followed by Ticket 17 target-lifecycle closure and Ticket 18
  semantic suspension/exact-Undo closure. The v2.34
  eight-pass control-plane audit passes; v2.27 remains
  historical evidence.
- Parent Ticket 14 decomposed into executable 14A–14D stage contracts without changing normative product scope.
- Active Ticket control plane promoted to `docs/ai-select/tickets/`.
- Planning manifest promoted to `docs/ai-select/manifest.json` and updated with parent/stage frontier fields.
- Durable traceability, walkthrough, audit, protocol-contract, benchmark-result and browser-walkthrough evidence promoted to `docs/ai-select/`.
- Executable cross-check/repro, benchmark and browser/GPU harnesses moved to `.scratch/experiments/ai-select-v1/`.
- `AGENTS.md` source routing updated to stable docs/Ticket locations.
- Historical `.scratch/ai-select-v1` planning paths reduced to compatibility pointers/readmes rather than duplicate normative content.
- CI is configured for `ai-select-v1` pushes with integrated `npm test`, build, lint and locale-lint jobs; locked-GPU validation remains a separate environment-specific gate.

## Directory ownership

```text
docs/ai-select/
  durable planning, Tickets, mappings, manifest, traceability and acceptance evidence

.scratch/experiments/ai-select-v1/
  executable/disposable experiments, repros and validation harnesses

.scratch/ai-select-v1/
  compatibility redirects only; no new normative content
```

## Remaining compatibility cleanup

Old scratch compatibility pointers may be removed in a future cleanup only after any external tooling or local agent configuration that still hardcodes those paths has migrated. They are not authoritative.

## Current execution frontier

```text
next_implementation_ticket = 19
next_implementation_subticket = none

14A Evidence Contract & Working Set (implemented)
→ 14B Reference Per-View P/N/V Evidence (implemented)
→ 14C Multi-view Aggregation & Classification (implemented)
→ 14D Atomic Candidate Publication & Reference Validation (implemented)
→ 13 Lift Readiness (implemented)
→ 15 Candidate correction / Re-Lift (implemented)
→ 16 Native Candidate operations core (implemented)
→ 16A AI View Dock + Candidate viewport presentation (implemented; operator visual review complete)
→ 16B single-result product contract (implemented)
→ 16C Mask state truth + compact Inspector (implemented)
→ 16D canvas-first shell + stable Navigator (implemented)
→ 16F compact 3D Toolbar surface (implemented)
→ 16E 2D Work Area integration (implemented)
→ 16G obsolete-control removal and visual closure (implemented)
→ 17 Applied Undo-and-Fix / Restart / multi-target lifecycle (implemented)
→ 18 Scene mutation suspension / exact Undo recovery (implemented)
→ 19 Large SceneSnapshot / authoritative render path hardening (current)
```
