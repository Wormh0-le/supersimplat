# Eight-Pass Bidirectional Traceability Audit — v2.12

The filename is retained for compatibility. Final Spec v1.3 is the sole current normative specification.

## Independent review findings corrected in v2.12

1. Ticket 04A still presented removed Prompt families as current outputs.
2. Ticket 06 still described the projected-support/Multiplex route as a production fallback.
3. `ImageInstanceMaskProvider` accepted Prompt identity without explicit resolvable authoritative RGB input.
4. previous logits were modeled as if tensor artifacts could cross browser boundaries, rather than Companion-local state behind opaque refs.
5. the graph described 04C as the only ready work even though reopened Ticket 07 is independently unblocked.
6. Ticket 10 duplicated visibility/readiness semantics and unnecessarily blocked Ticket 21.
7. Fourteen Ticket files still named Final Spec v1.1 or v1.2 in their current mapping/status text even though the central mapping had moved to v1.3.

All seven are corrected below.

## Pass 1 — Ticket graph and current frontier

- Ticket count: 30 total.
- Missing blocker references: 0.
- Ticket cycle: false.
- Topological order length: 30/30.
- Current ready frontier: `[04C, 07]`.
- Critical migration gate: `04C`.
- Ticket 02C may proceed after 04C.
- Ticket 07A requires both 04C and 07.
- Ticket 07B and 08 remain parallel after 07A.
- Ticket 10 is optional and does not block Ticket 13 or Ticket 21.

Result: **PASS**

One valid order:

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B → 08 → 08A → 08B → 09
→ 11 → 12 → 14 → 13 → 15 → 16 → 17 → 18
→ 19 → 20 → 21 → 22 → 10
```

Ticket 10 may execute at any point after 14 + 09 + 07.

## Pass 2 — Specification authority and Ticket-local migration

Checks:

- Final Spec v1.3 exists and is indexed as current.
- Final Spec v1.2 is historical.
- ADR 0016 is accepted and indexed.
- CURRENT-TICKET-SPEC-MAPPING maps all 30 Tickets to v1.3.
- every one of the 30 Ticket files contains a direct current mapping to Final Spec v1.3;
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

## Pass 4 — Geometry and multi-view scope

Checks:

- Ticket 08 produces one `TargetGeometryHintArtifact`;
- no Gaussian ownership fields are required;
- default plan is 2–4 bounded local Views;
- adaptive marginal-gain/free-space/room-scale planning is deferred;
- 08 runs no SAM;
- Generate More appends only a bounded local batch;
- 07B and 08 remain parallel after 07A.

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
- semantic unavailable differs from technical failure.

Result: **PASS**

## Pass 6 — Mask Review, Lift Readiness and optional cross-view diagnostics

Checks:

- Ticket 07 owns Prompt consistency, clipping, severe fragmentation and gross spill;
- `propagation-uncertain` is removed;
- Ticket 13 solely owns weak/low Gaussian visibility support, coverage, diversity and readiness;
- Ticket 10 owns optional Evidence-conflict diagnostics only;
- Ticket 10 output is not required for Ticket 13 or core release;
- Participation defaults remain independent from View role;
- only Included Stable Masks contribute to P/N/V.

Result: **PASS**

## Pass 7 — Legacy migration

Current migration targets:

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

Every target is owned by 04C, 06, 08B, 12, 14, 20, 22 or 21. User Confirmed Stable Masks are preserved.

Result: **PASS**

## Pass 8 — Traceability and walkthrough coverage

- Requirements: 52.
- Unmapped requirements: 0.
- Orphan active Tickets: 0.
- Ticket-local direct v1.3 mappings: 30/30.
- Ticket-local legacy current mappings: 0.
- Typical walkthroughs: 16.
- Error walkthroughs: 16.
- Invalid ADR refs: 0.
- Invalid current mapping refs: 0.
- Critical phrase failures: 0.

Result: **PASS**

## Critical phrase scan

Active planning MUST NOT require:

- Final Spec v1.1, an Amendment, or Final Spec v1.2 as a Ticket-local current closure source;
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
Ticket graph / current frontier               PASS
Specification authority / all-ticket mapping PASS
SAM model / Prompt / RGB / refinement         PASS
Geometry / local multi-view scope             PASS
Per-View Mask architecture                    PASS
Mask Review / Lift Readiness / optional P1    PASS
Legacy migration                              PASS
Traceability / walkthroughs                   PASS
```