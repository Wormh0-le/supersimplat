# Eight-Pass Bidirectional Traceability Audit — v2.21

The filename is retained for compatibility. Final Spec v1.3 is the sole current normative specification.

## Independent review findings corrected in v2.12

1. Ticket 04A still presented removed Prompt families as current outputs.
2. Ticket 06 still described the projected-support/Multiplex route as a production fallback.
3. `ImageInstanceMaskProvider` accepted Prompt identity without explicit resolvable authoritative RGB input.
4. previous logits were modeled as if tensor artifacts could cross browser boundaries, rather than Companion-local state behind opaque refs.
5. the graph described 04C as the only ready work even though reopened Ticket 07 is independently unblocked.
6. Ticket 10 duplicated visibility/readiness semantics and unnecessarily blocked Ticket 21.
7. Fourteen Ticket files still named Final Spec v1.1 or v1.2 in their current mapping/status text even though the central mapping had moved to v1.3.
8. The ArtisanGS influence on 2D-first interaction, visible-surface localization and multi-view Gaussian selection was implicit, leaving dense-view tracking and aggregation divergences undocumented.

All eight were corrected before v2.13.

## v2.13 follow-up closure

Ticket 08C records the accepted retained-visible-support contract from the
08B browser investigation. It separates Geometry Quality from Route B Prompt
Support, rejects old TargetGeometryHint identities, and remains independent
from tracker state and P/N/V ownership.

## v2.14 source-of-truth / frontier closure

- Tickets 04C, 07, 02C, 07A, 07B, 08, 08A, 08B and 08C are implemented and
  are no longer represented as current ready work.
- Locked-GPU browser E2E for 08B and 08C completed on 2026-08-07 with no
  blocking issue reported.
- Ticket 09 is the sole current ready frontier; Tickets 11 and 12 become
  parallel ready work after 09.
- Root `AGENTS.md`, `CONTEXT.md`, the Final Spec planning header, manifest,
  mapping and graph README are synchronized to Final Spec v1.3 / graph v2.14.
- Ticket 08's local contract now states TargetGeometryHint schema v2,
  retained first-hit `visiblePoints`, and independent `promptSupport`.

## v2.15 Ticket 09 closure

- Ticket 09 is implemented: separated Gallery card presentation (Render,
  Prompt, Mask inference, Mask Review, Participation, Evidence), read-only
  Generated View RGB/Mask inspection, per-View read-only Camera Inspection,
  presentation-only filters, and bounded digest-keyed thumbnails; the
  Anchor candidate choice remains Anchor-surface only and no backend-route,
  fallback, tracker, ProposalDecision, Prompt Brush or Negative Box surface
  appears.
- Locked-GPU large-Gallery browser walkthrough for Ticket 09 passed on
  2026-08-07.
- Tickets 11 and 12 are the parallel current ready frontier; Ticket 14
  follows after both.
- Mapping audit rule, TRACEABILITY R040, graph README, manifest and the
  Final Spec planning header are synchronized to graph v2.15.

## v2.16 Ticket 11 closure / Ticket 12 start

- Ticket 11 is implemented; its repository validation passed, while its
  locked-GPU browser walkthrough remains pending.
- Ticket 12 is the sole active implementation frontier; Ticket 14 remains
  blocked until Ticket 12 closes.
- Mapping, manifest, graph README, traceability, Ticket 12 status, and the
  Final Spec planning header are synchronized to that tracker state.

## v2.17 Ticket 12 closure / Ticket 14 ready

- Ticket 12 is implemented: Anchor/View/Mask publications now drive an
  explicit bounded dirty state, and Prompt regeneration remains separate
  from automatic Mask refresh/retry.
- Repository TypeScript and Companion tests, lint, locale lint, and the
  production build passed. This editor/domain/UI slice did not exercise the
  locked GPU renderer path.
- Ticket 14 became the sole current ready parent implementation frontier;
  Ticket 13 remains blocked until Ticket 14 closes.

## v2.18 Ticket 14 decomposition / planning-control migration

- Parent Ticket 14 remains the sole current parent implementation frontier.
- Parent Ticket 14 is partitioned into four execution stages without changing
  its Final Spec v1.3 requirement ownership:
    - 14A Evidence Contract & Working Set;
    - 14B Reference Per-View P/N/V Evidence;
    - 14C Multi-view Aggregation & Classification;
    - 14D Atomic Candidate Publication & Reference Validation.
- 14A is the sole current execution stage. `next_implementation_ticket = 14`
  remains the parent compatibility field and
  `next_implementation_subticket = 14A` records the stage frontier.
- The former 14D Candidate-review wording was corrected: 14D does not add a
  Candidate provenance/source browser, Gaussian Evidence inspector or direct
  Candidate editing system.
- Durable AI Select planning, active Tickets, manifest, mapping, traceability,
  audits and acceptance records now live under `docs/ai-select/`.
- Executable/disposable investigation tooling lives under
  `.scratch/experiments/ai-select-v1/`.
- Historical `.scratch/ai-select-v1/` planning paths are compatibility-only.
- Root `AGENTS.md`, Final Spec planning header, mapping, graph, manifest and
  traceability are synchronized to v2.18 and the 14A execution frontier.
- This migration changes planning structure and execution granularity only;
  it does not change Final Spec v1.3 product semantics, ADR authority,
  renderer/runtime locks, Evidence policy, or calibration.

## v2.19 Ticket 14A implementation closure

- 14A is implemented as a fail-closed browser/Companion contract for formal
  Evidence admission, Render/Evidence Working Set separation, artifact
  identity, boundary expansion and reference-only backend identity.
- A shared Unicode and IEEE-754 golden vector verifies matching browser and
  Companion Working-Set and artifact digests.
- 14A performs no P/N/V calculation, aggregation, Candidate publication or
  same-decision GPU work; those remain 14B–14D and Ticket 20 responsibilities.
- Parent Ticket 14 remains the sole current parent frontier. 14B is the sole
  current execution stage, with `next_implementation_ticket = 14` and
  `next_implementation_subticket = 14B`.
- The focused contract tests passed in both runtimes. Production GPU validation
  was not applicable to this contract-only stage.

## v2.20 Ticket 14B implementation closure

- 14B implements the trusted complete-Contributor reference path from an
  Included Stable Mask and full Render Working Set to raw per-view P/N/V plus
  separate Boundary Mass in the 14A `GaussianEvidenceArtifact`.
- The versioned pixel policy explicitly separates strong positive interior,
  boundary/ignore, local negative context and far-neutral regions; P/N/V
  weights remain independent.
- The discrepancy report measures absolute and relative max/p95/p99 errors,
  support differences and threshold-near differences across every available
  trusted backend pair without retuning policy thresholds.
- CPU fixtures and the locked-CUDA complete-Contributor integration fixture
  passed. This is reference/debug backend work, not Ticket 20 production
  same-decision Evidence.
- Parent Ticket 14 remains the current parent frontier. 14C is the current
  execution stage, with `next_implementation_ticket = 14` and
  `next_implementation_subticket = 14C`.

## v2.21 Ticket 14C implementation closure

- 14C implements deterministic reference multi-view aggregation over exact
  current Included per-view Evidence artifacts while preserving their raw
  P/N/V and source identities.
- Its versioned policy exposes raw-mass summation for comparison and defaults
  to a declared per-view Visible Mass cap so a close/high-resolution View
  cannot dominate silently.
- Four-state classification keeps Selected, Rejected, Uncertain and Out of
  Scope distinct; Candidate input contains Selected only, while unobserved,
  insufficient, mixed and conflicting support remains Uncertain.
- Exclusion omits the View from aggregation without turning it negative;
  reinclusion is deterministic, and Stable Mask/dependency mismatch rejects
  stale Evidence before aggregation.
- CPU reference fixtures passed. This stage performs no Candidate publication,
  Native Selection mutation, Ticket 13 readiness claim or production GPU work.
- Parent Ticket 14 remains the current parent frontier. 14D is the current
  execution stage, with `next_implementation_ticket = 14` and
  `next_implementation_subticket = 14D`.

## Pass 1 — Ticket graph and current frontier

- Parent Ticket count: 31 total.
- Ticket 14 execution-stage count: 4.
- Missing blocker references: 0.
- Parent Ticket cycle: false.
- Parent topological order length: 31/31.
- Implemented prerequisite chain is closed through 12 and 14C.
- Current parent implementation frontier: `[14]`.
- Current execution-stage frontier: `[14D]`.
- Next implementation Ticket / current parent critical gate: `14`.
- Next implementation subticket: `14D`.
- Ticket 13 requires parent Ticket 14 to close after 14D.
- Ticket 10 is optional and does not block Ticket 13 or Ticket 21.

Result: **PASS**

One valid execution order:

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B → 08 → 08A → 08B → 08C / 09
→ 11 → 12 → 14A → 14B → 14C → 14D → 13 → 15 → 16 → 17 → 18
→ 19 → 20 → 21 → 22 → 10
```

Ticket 10 may execute at any point after parent Ticket 14 + 09 + 07.

## Pass 2 — specification authority and Ticket-local migration

Checks:

- Final Spec v1.3 exists and is indexed as current.
- Final Spec v1.2 and Final Spec v1.1 + Amendments are historical.
- root `AGENTS.md` identifies Final Spec v1.3 and `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md` as the source-of-truth chain;
- root `AGENTS.md` routes active Ticket work to `docs/ai-select/tickets/`;
- `CONTEXT.md` identifies Final Spec v1.3 as the current domain vocabulary;
- ADR 0016 is accepted and indexed;
- ADR 0017 is accepted for Geometry Quality / Prompt Support semantics;
- ADR 0016 records ArtisanGS as non-normative design provenance and explicitly states that Final Spec v1.3 remains the requirement authority;
- CURRENT-TICKET-SPEC-MAPPING maps all 31 parent Tickets to v1.3;
- every one of the 31 parent Ticket files contains a direct current mapping to Final Spec v1.3;
- 14A–14D explicitly inherit parent Ticket 14 + Final Spec v1.3 authority;
- zero Ticket-local current mapping/status blocks name Final Spec v1.1, an Amendment, or Final Spec v1.2 as current authority;
- older spec names appear only inside explicitly historical-provenance, historical-implementation, superseded-surface or migration-input sections;
- ADR 0014 / DG-24–26 are historical where conflicting;
- Ticket 04A explicitly marks its generic Prompt surface historical;
- Ticket 06 explicitly marks Multiplex/projected-support/fallback behavior historical;
- Tickets 14 and 20 use `TargetGeometryHintArtifact`, not v1.2 support/bootstrap route artifacts, as the current optional Working Set seed;
- Ticket 22 contracts the Final Spec v1.3 replacement path rather than waiting for a v1.1/v1.2 release;
- no current agent is instructed to reconstruct old Prompt, route, planner or Evidence semantics.

Result: **PASS**

## Pass 3 — SAM model, Prompt, RGB and refinement contract

Checks:

- static production model is SAM 3 Image instance interactivity;
- static Multiplex/private tracker heads are explicitly non-current;
- Positive Point, Negative Point and Positive Instance Box are the only v1 Prompt families;
- Negative Box, Prompt Brush, Mask Constraints and Text are removed;
- Paint/Erase remain Editing only;
- every inference request contains authoritative RGB bytes or a current Companion-resolvable RGB ref;
- RGB digest alone is insufficient;
- actual previous logits remain Companion-local;
- browser/protocol state carries only an opaque ref bound to Companion Instance, source attempt and candidate;
- stale/expired ref falls back to fresh no-logits inference;
- candidate refinement occurs before Accept in Prompt mode;
- single-Point multimask and Box/multi-Point/refinement single-mask rules are consistent.

Result: **PASS**

## Pass 4 — Geometry, multi-view scope and design provenance

Checks:

- Ticket 08 produces one TargetGeometryHint schema-v2 artifact;
- formal `visiblePoints` are retained distinct first-hit support after robust separated-support filtering;
- Geometry Quality and Prompt Support are independent;
- globally usable Prompt Support requires at least four distinct retained samples and no disqualifying reason; `separatedSupportFiltered` is the sole promotable Limited reason;
- each Generated View still requires at least two distinct in-frame retained support projections;
- no Gaussian ownership fields are required;
- default plan is 2–4 bounded local Views;
- adaptive marginal-gain/free-space/room-scale planning is deferred;
- 08 runs no SAM;
- Generate More appends only a bounded local batch;
- retained ArtisanGS principles are limited to 2D-first user intent, human correction, visible-surface localization, geometry-guided views, renderer-mediated Gaussian selection and explicit 2D/3D operation boundaries;
- dense full-circle turnaround views, Cutie/VOT memory, and optimized one-channel per-Gaussian Mask features are documented as deliberate divergences, not current requirements;
- no current `VideoObjectTracker`, `SequenceMaskProvider`, tracker-memory schema or reserved sequence extension is introduced by the provenance record;
- future `SequenceInstanceTracker` adoption still requires a separate measured ADR.

Result: **PASS**

## Pass 5 — Per-View Mask architecture

Checks:

- 08A defines compact RGB-bound Prompt/request/result contracts only;
- no backend registry, Route B/C/D bundle, sequence extension or automatic fallback is current;
- 08B generates one Box, 1–3 Positive Points and optional Negative Points;
- Generated inference uses SAM 3 Image single-mask mode;
- provider resolves authoritative RGB before inference;
- provider cannot publish Review, Stable Mask, Participation, Evidence or Candidate;
- raw logits tensors do not cross browser boundaries;
- semantic unavailable differs from technical failure;
- locked-GPU browser E2E for 08B and 08C completed 2026-08-07 with no blocking issue reported.

Result: **PASS**

## Pass 6 — Mask Review, Lift Readiness and optional cross-view diagnostics

Checks:

- Ticket 07 owns Prompt consistency, clipping, severe fragmentation and gross spill;
- `propagation-uncertain` is removed;
- Ticket 13 solely owns weak/low Gaussian visibility support, coverage, diversity and readiness;
- Ticket 10 owns optional Evidence-conflict diagnostics only;
- Ticket 10 output is not required for Ticket 13 or core release;
- Participation defaults remain independent from View role;
- only Included Stable Masks contribute to P/N/V;
- 14D owns only atomic publication/reference validation and does not absorb Ticket 13 readiness or Ticket 10 diagnostics.

Result: **PASS**

## Pass 7 — Legacy and planning migration

Current product migration targets:

```text
SAM 3.1 Multiplex static shim
private tracker-head image prediction
old Multiplex Model Manifest/runtime digest
Ticket 04A removed Prompt families
Ticket 06 production fallback claim
generated-view-mask/v1
maskSource: propagated
provider-returned Assessment
Negative Box / Mask Constraint artifacts
binary Brush-to-mask_input mapping
raw logits tensor in browser state
digest-only unresolved RGB requests
backend registry / sequence / automatic fallback state
Ticket-local Final Spec v1.1/v1.2 current mapping text
VisibleTargetSupport/TargetBootstrap current Evidence-seed wording
```

Every product target is owned by 04C, 06, 08B, 08C, 12, 14, 20, 22 or 21. User Confirmed Stable Masks are preserved.

Planning/document ownership now follows:

```text
docs/ai-select/                       durable planning and acceptance knowledge
.scratch/experiments/ai-select-v1/   executable/disposable investigation tooling
.scratch/ai-select-v1/               compatibility redirects only
```

Result: **PASS**

## Pass 8 — Traceability and walkthrough coverage

- Requirements: 56.
- Unmapped requirements: 0.
- Orphan active parent Tickets: 0.
- Parent Ticket-local direct v1.3 mappings: 31/31.
- Ticket 14 execution-stage mappings: 4/4.
- Ticket-local legacy current mappings: 0.
- Typical walkthroughs: 16.
- Error walkthroughs: 16.
- Invalid ADR refs: 0.
- Invalid current mapping refs: 0.
- Critical phrase failures: 0.
- Parent frontier mismatch: 0.
- Stage frontier mismatch: 0.

Result: **PASS**

## Critical phrase scan

Active planning MUST NOT require:

- Final Spec v1.1, an Amendment, or Final Spec v1.2 as a current closure source;
- implemented Tickets 04C, 07, 08C or 09 as current ready work;
- a `next_implementation_ticket` other than 14 while parent Ticket 14 remains current;
- a `next_implementation_subticket` other than 14D while 14D is current;
- Candidate provenance/source inspection, Gaussian Evidence inspection or direct Candidate editing as a 14D requirement;
- ArtisanGS dense turnaround views, Cutie tracking, tracker reference frames or one-channel Gaussian Mask-feature optimization as current v1 requirements;
- a current video-tracker/sequence interface merely because ArtisanGS is cited as inspiration;
- static Multiplex for Anchor/Key Views;
- Negative Box or Prompt Brush;
- binary Brush/Editing Mask as previous logits;
- raw previous-logits tensor in browser state;
- digest-only unresolved RGB inference;
- generic near-duplicate/material-distinct cluster framework;
- adaptive/free-space planner;
- backend registry or Route C/D seam;
- automatic Route-A fallback;
- Ticket 06 as production fallback;
- `VisibleTargetSupportArtifact` / `TargetBootstrapArtifact` as current v1 geometry contracts;
- ProposalSet/Decision/fallback state as current Generated-View ownership or Evidence input;
- propagation uncertainty in ordinary Mask Review;
- weak/low Gaussian support outside Ticket 13;
- Ticket 10 as release blocker.

Current active planning contains no such requirement.

## Final audit result

```text
Ticket graph / parent + stage frontier       PASS
Specification authority / all-ticket mapping PASS
SAM model / Prompt / RGB / refinement         PASS
Geometry / local multi-view / provenance      PASS
Per-View Mask architecture / GPU E2E          PASS
Mask Review / Lift Readiness / optional P1    PASS
Legacy + planning migration                   PASS
Traceability / walkthroughs                   PASS
```
