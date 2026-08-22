# AI Select Specification Index

## Current normative specification

1. [`ai-select-final-spec-v2.0.md`](./ai-select-final-spec-v2.0.md)
2. [`../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md`](../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md)
3. [`../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md`](../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md)
4. [`../adr/0019-promote-direct-evidence-candidate-and-bind-production-identity.md`](../adr/0019-promote-direct-evidence-candidate-and-bind-production-identity.md) — carried over, extended
5. [`../ai-select/TICKET-GRAPH-V2.md`](../ai-select/TICKET-GRAPH-V2.md) — active implementation planning surface
6. current Ticket acceptance criteria and tests

Final Spec v2.0 (accepted 2026-08-22) supersedes Final Spec v1.3 as a whole
version with an explicit carry-over list (draft §0.2): SAM 3 Image
single-result Mask authoring, Anchor/hint semantics, Stable Mask /
Participation lifecycle, authoritative RGB and same-decision invariants,
exact-key identity, atomic Candidate replacement and Native operation
boundaries carry over unchanged. Superseded: the fixed initial View plan
(fixed-four / ADR 0018's `4–8` range → dual budget), manual-only Candidate
publication at the normal terminal (→ auto-publish per ADR 0020), User-added
View capability (removed; runtime removal lands with V2J), single-channel
Negative Mass (→ depth-classified per ADR 0021).

Runtime behavior transitions to v2.0 as the V2x tickets land; until then
shipped behavior remains v1.3.

## Historical specifications and rationale

The following are retained for history only:

- Final Spec v1.3 (superseded 2026-08-22; provenance record for the
  implemented Tickets through 22 via
  [`../ai-select/CURRENT-TICKET-SPEC-MAPPING.md`](../ai-select/CURRENT-TICKET-SPEC-MAPPING.md));
- Final Spec v1.1 and Amendments 001–005;
- Final Spec v1.2;
- ADR 0014;
- DG-20 through DG-26 where superseded by ADR 0016 / later specs;
- Ticket 04A generic Prompt surface;
- Ticket 06 projected-support/Multiplex Mask and production-fallback handoff.

They must not be reconstructed as current requirements.

## Durable control plane

- [`CONTEXT.md`](../../CONTEXT.md) — stable domain vocabulary;
- [`../ai-select/TICKET-GRAPH-V2.md`](../ai-select/TICKET-GRAPH-V2.md) — active v2 ticket graph;
- [`../ai-select/tickets/v2/`](../ai-select/tickets/v2/) — V2A–V2J ticket contracts;
- [`../ai-select/TICKET-GRAPH.md`](../ai-select/TICKET-GRAPH.md),
  [`../ai-select/manifest.json`](../ai-select/manifest.json) — implemented v1
  closure record (historical).
