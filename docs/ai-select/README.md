# AI Select Documentation

Stable, long-lived AI Select planning and validation documentation lives here.

## Control plane

```text
docs/ai-select/
├── README.md
├── manifest.json
├── CURRENT-TICKET-SPEC-MAPPING.md
├── TICKET-GRAPH.md
├── TICKET-14-SPLIT.md
├── tickets/
│   ├── 01-...md
│   ├── ...
│   ├── 14-gaussian-lifting-candidate.md
│   ├── 14A-evidence-contract-working-set.md
│   ├── 14B-reference-per-view-pnv-evidence.md
│   ├── 14C-multiview-aggregation-classification.md
│   ├── 14D-atomic-candidate-publication-validation.md
│   ├── 16A-candidate-viewport-presentation.md
│   ├── 16B-single-result-product-contract.md
│   ├── 16C-mask-inspector-state-truth.md
│   ├── 16D-canvas-first-navigator-shell.md
│   ├── 16E-2d-work-area-floating-palette.md
│   ├── 16F-viewport-toolbar-anchor-adjustment.md
│   └── 16G-obsolete-controls-integration-closure.md
├── TRACEABILITY.md
├── WALKTHROUGHS.md
├── FOUR-PASS-AUDIT.md
├── MIGRATION-STATUS.md
├── contracts/
├── benchmarks/
└── walkthroughs/
```

Repository-wide specifications and ADRs remain canonical under `docs/specs/` and `docs/adr/`.

## Accepted designs

- [AI View Dock layout](ai-view-dock-layout.md) — implemented Ticket 16A
  baseline; conflicting presentation details are superseded by 16B–16G.
- [AI View Dock visual](show-me-ai-view-dock-layout.html) — visual companion for the accepted layout.
- [AI Select Toolbar layout](ai-select-toolbar-layout.md) — implemented Ticket
  16A baseline; the Candidate Overlay remains valid while 16F/16G refine the
  toolbar surface.
- [Ticket 16A](tickets/16A-candidate-viewport-presentation.md) — implemented
  presentation baseline and completed operator visual-review record.
- [Ticket 16B](tickets/16B-single-result-product-contract.md) — implemented
  single-result product-contract stage; Ticket 16C is current and 16D–16G
  carry the remaining follow-up.

## Scratch policy

Executable and disposable investigation material lives under:

```text
.scratch/experiments/ai-select-v1/
```

This includes repro probes, cross-check scripts, benchmark harnesses and browser/GPU validation harnesses.

`.scratch/ai-select-v1/` is compatibility-only after the migration. It must not become a second source of truth.

## Current frontier

Parent Ticket 14 is decomposed into:

- 14A — Evidence Contract & Working Set;
- 14B — Reference Per-View P/N/V Evidence;
- 14C — Multi-view Aggregation & Classification;
- 14D — Atomic Candidate Publication & Reference Validation.

Execution order is:

```text
14A → 14B → 14C → 14D → 13 → 15 → 16 → 16A → 16B
                                                       ├→ 16C ─┐
                                                       ├→ 16D ─┴→ 16E ─┐
                                                       └→ 16F ─────────┴→ 16G → 17
```

14A through 14D, parent Ticket 14, Tickets 13 through 15, Ticket 16's native
application core and Tickets 16A–16B are implemented. The completed 16A
operator visual walkthrough created follow-up stages 16B–16G. Ticket 16C is
current (`next_implementation_ticket = 16`, `next_implementation_subticket = 16C`);
Ticket 17 follows 16G.
