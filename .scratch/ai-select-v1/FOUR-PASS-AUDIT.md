# Eight-Pass Bidirectional Traceability Audit — v2.11

The filename is retained for compatibility. Final Spec v1.3 is the sole current normative specification.

## Pass 1 — Ticket graph

- Ticket count: 30 total — 22 numbered + 02C + 04A + 04B + 04C + 07A + 07B + 08A + 08B
- Missing blocker references: 0
- Ticket cycle: false
- Topological order length: 30/30
- Next implementation gate: 04C
- Result: **PASS**

One valid order:

```text
01 → 02 → 03 → 04 → 05 → 04A → 04B → 04C → 02C
→ 06 → 07 → 07A → 07B → 08 → 08A → 08B → 09
→ 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18
→ 19 → 20 → 21 → 22
```

## Pass 2 — Specification authority

Checks:

- Final Spec v1.3 exists and is indexed as current.
- Final Spec v1.2 is marked Historical.
- ADR 0016 is accepted and indexed.
- CURRENT-TICKET-SPEC-MAPPING maps all 30 Tickets to v1.3.
- ADR 0014 / DG-24–26 are historical where conflicting.

Result: **PASS**

## Pass 3 — SAM model and Prompt contract

Checks:

- static production model is SAM 3 Image instance interactivity;
- static Multiplex/private tracker heads are explicitly non-current;
- Positive Point, Negative Point and Positive Instance Box are the only v1 Prompt families;
- Negative Box, Prompt Brush, Mask Constraints and Text are removed;
- Paint/Erase remain editing only;
- previous logits are internal same-image refinement state;
- single-point multimask and Box/multi-point/refinement single-mask rules are consistent across 04C, 07A, 08A, 08B, 11 and 21.

Result: **PASS**

## Pass 4 — Geometry and multi-view scope

Checks:

- Ticket 08 produces one `TargetGeometryHintArtifact`;
- no Gaussian ownership fields are required;
- default plan is 2–4 bounded local Views;
- adaptive marginal-gain/free-space/room-scale planning is deferred;
- 08 runs no SAM;
- 07B and 08 remain parallel after 07A.

Result: **PASS**

## Pass 5 — Per-View Mask architecture

Checks:

- 08A defines compact image Prompt/result contracts only;
- no backend registry, Route B/C/D bundle, sequence extension or automatic fallback is current;
- 08B generates one Box, 1–3 positive Points and optional negative Points;
- Generated inference uses SAM 3 Image single-mask mode;
- provider cannot publish Review, Stable Mask, Participation, Evidence or Candidate;
- semantic unavailable differs from technical failure.

Result: **PASS**

## Pass 6 — Mask Review and Lift Readiness

Checks:

- Ticket 07 owns Prompt consistency, clipping, severe fragmentation and gross spill;
- `propagation-uncertain` is removed;
- `weak-gaussian-support` is owned by Ticket 13;
- Participation defaults remain independent from View role;
- only Included Stable Masks contribute to P/N/V.

Result: **PASS**

## Pass 7 — Legacy migration

Current migration targets:

```text
SAM 3.1 Multiplex static shim
private tracker-head image prediction
old Multiplex Model Manifest/runtime digest
generated-view-mask/v1
maskSource: propagated
provider-returned Assessment
Negative Box / Mask Constraint artifacts
binary Brush-to-mask_input mapping
backend registry / sequence / automatic fallback state
```

Every target is owned by 04C, 08B, 12 or 21. User Confirmed Stable Masks are preserved.

Result: **PASS**

## Pass 8 — Traceability and walkthrough coverage

- Requirements: 48
- Unmapped requirements: 0
- Orphan active Tickets: 0
- Walkthroughs: 14
- Error walkthroughs: 14
- Invalid ADR refs: 0
- Invalid current mapping refs: 0
- Critical phrase failures: 0

Result: **PASS**

## Critical phrase scan

Active planning MUST NOT require:

- static Multiplex for Anchor/Key Views;
- Negative Box or Prompt Brush;
- binary Brush as previous logits;
- generic near-duplicate/material-distinct cluster framework;
- adaptive/free-space planner;
- backend registry or Route C/D seam;
- automatic Route-A fallback;
- propagation uncertainty in ordinary Mask Review;
- weak Gaussian support as Mask quality.

Current active planning contains no such requirement.

## Final audit result

```text
Ticket graph                         PASS
Specification authority             PASS
SAM model / Prompt contract          PASS
Geometry / local multi-view scope    PASS
Per-View Mask architecture           PASS
Mask Review / Lift Readiness split   PASS
Legacy migration                     PASS
Traceability / walkthroughs          PASS
```
