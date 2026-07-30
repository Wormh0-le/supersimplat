# Final Spec v1.2 Walkthrough Coverage — v2.8

## Typical and architecture flows A–T

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-A | Fast single-object | `02 → 03/04/05 → 04A/04B/07A → 08 → 08A → 08B → 09 → 12/14 → 15/16` | Route-B layered acquisition reaches Candidate without tracker or Contributor dependency |
| WF-B | Adjust Anchor | `02 → 03 Retry → 04A/04B/07A → 05 Confirm` | New Anchor identity invalidates all dependent support/planning artifacts |
| WF-C | Ambiguous Anchor | `04A/04B → 07A` | Multiple material candidates remain ambiguous; no silent Top-1 |
| WF-D | Floating palette | `07A → 07B` | Drag/collapse/Space-hide leaves no stale blind region |
| WF-E | 07B and planner parallel | `07A → 07B` and `07A → 08` | UX hardening does not block support/planning artifacts |
| WF-F | Visible support extraction | `07A → 08` | Bounded replayable support artifact with no ownership semantics |
| WF-G | Sparse planner | `08 support → bootstrap → segment` | Validity precedes gain; no Bridge/tracker requirement |
| WF-H | Generate More | `08 → 09/12` | New immutable segment appends without staling prior Views |
| WF-I | Contract foundation | `08 → 08A` | Prompt/Proposal/Decision/backend bundle schemas validate without production inference |
| WF-J | Route-B per-view acquisition | `08A → 08B` | Prompt synthesis → ProposalSet → Decision → Assessment → publication are separate |
| WF-K | Ambiguous Key View | `08B → 09` | ProposalSet retained, no Stable Mask, Excluded, actionable Review |
| WF-L | Route-B technical fallback | `08B → 09/12` | Distinct route-A attempt with parent/reason; same-or-stricter quality gate |
| WF-M | Semantic Review no fallback | `08B → 09` | Contamination/clipping/Review remains Review and never auto-fallbacks |
| WF-N | RGB Ready without Mask/Evidence | `03/06/08B/11` | RGB publishes independently and remains inspectable |
| WF-O | User-added View | `07B + 09 → 11` | Same Prompt/acquisition/decision/assessment/publication chain and complete correction UX |
| WF-P | Refresh one View | `09 → 12 → 08B` | Prompt-only regeneration and SAM Retry are distinct; no automatic Re-Lift |
| WF-Q | Per-view correction | `09/11 → Confirm → 12` | Only that View Evidence/Lift becomes dirty; no tracker memory |
| WF-R | P/N/V ownership | `11/12 → 14 → 20` | Only Included Stable Masks contribute formal Evidence |
| WF-S | Native apply and Undo-and-Fix | `14/15 → 16 → 17` | Native EditHistory used; correction returns through explicit Re-Lift |
| WF-T | Future C/D readiness | `08A contracts → future experiment → ADR` | Current route B remains stable; no fake sequence/reference state |

## WF-F — Visible target support

```text
Confirmed Anchor Stable Mask
→ exact Anchor Camera/RGB/Mask binding
→ depth / first-hit visible-surface extraction
→ bounded deterministic support samples
→ VisibleTargetSupportArtifact
→ robust center/extent summary
→ TargetBootstrapArtifact references support digest
```

Assertions:

- support samples are finite and replayable;
- optional Gaussian IDs are provenance only;
- separated/background-dominated support degrades or fails closed;
- support may guide planning/Prompt synthesis but cannot classify ownership;
- absence from Anchor support cannot imply Rejected/Out of Scope.

## WF-G — Sparse planning

```text
VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
→ candidate cameras
→ camera validity / free-space / scene-content gate
→ observation and directional diversity gain
→ bounded sparse Key Views
→ immutable SparseKeyViewPlanSegment
```

Assertions:

- invalid camera cannot win by gain;
- no mandatory Bridge View, dense path, tracker ordering, or transition envelope;
- Generate More appends another segment;
- Regenerate is the explicit segment replacement operation.

## WF-I — Acquisition foundation

```text
08 artifacts
→ KeyViewPromptArtifact schema
→ KeyViewMaskProposalSet schema
→ KeyViewMaskDecision schema
→ attempt/fallback identity
→ Backend Descriptor + Bundle + Registry
→ perView contract + optional sequence schemas
```

Assertions:

- 08A runs no production model;
- bundle structure is capability truth;
- route B has perView only;
- provider result cannot contain Decision, Assessment, Stable publication, Participation, P/N/V, or Candidate;
- unsupported sequence operations fail before mutation.

## WF-J — Route-B layered acquisition

```text
Visible support + bootstrap + segment + Key-View RGB
→ KeyViewPromptSynthesizer
→ immutable KeyViewPromptArtifact
→ route-B perView provider
→ bounded KeyViewMaskProposalSet
→ exact/near-duplicate clustering
→ KeyViewMaskDecision
    ├── selected
    ├── ambiguous
    └── unavailable
→ selected only: ViewAssessmentPolicy
→ MaskPublicationCoordinator
```

Publication:

```text
selected + Good   → Auto Good Stable + Included
selected + Review → Auto Review Stable + Excluded
ambiguous          → retain ProposalSet, no new Stable, Excluded
unavailable        → Mask Failed, no Stable
```

Assertions:

- model score is not sole selector;
- provider, Decision, Assessment, publication and Participation remain distinct;
- User Confirmed Stable cannot be overwritten;
- RGB does not wait for acquisition.

## WF-L — B2 fallback

```text
route-B technical/capability failure
→ retain route-B failure
→ new route-A attempt
   fallbackOfAttemptId = route-B attempt
   fallbackReason = declared technical reason
→ route-A ProposalSet
→ same Decision
→ same Assessment
→ same Publication Coordinator
```

Assertions:

- fallback is allowed only for backend/capability/technical/OOM classes;
- ambiguous, contamination, Prompt inconsistency, clipping, fragmentation and Review do not trigger fallback;
- route-A Auto Good requires same or stricter thresholds;
- fallback provenance is visible and never represented as route B.

## WF-R — Evidence ownership

```text
Included + Render Ready + Stable Mask Views
→ per-view P/N/V
→ Working Set expansion where required
→ multi-view aggregation
→ Selected / Rejected / Uncertain / Out of Scope
→ Candidate contains Selected only
```

Assertions:

- support, bootstrap, Prompt, ProposalSet, Decision, backend/fallback and tracker state are not P/N/V;
- ambiguous Views without Stable Mask contribute nothing;
- unobserved/mixed support is Uncertain;
- Re-Lift is explicit.

## Reverse outcome-to-prerequisite validation

```text
Native operation (16)
← current Candidate (15/14)
← version-bound P/N/V (14/20)
← Included Stable View Annotations (09/11/12)
← layered route-B acquisition (08B)
← acquisition contracts and registry (08A)
← valid support/bootstrap/sparse Key Views (08)
← confirmed object-level Anchor (04B/07A/05)
← Prompt/proposal foundation (04A)
← authoritative RGB + CameraBinding (02/03/06/11)
← Current Target Context + Stable IDs (01/19)
```

07B is a parallel interaction prerequisite for complete correction UX and release hardening, not an artifact prerequisite for Ticket 08.

No final outcome depends on route comparison, tracker presence, or complete Contributor publication.

## Error / degradation flows ERR-1–ERR-20

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion offline/incompatible | 02/21 | Native editor unaffected; readiness/reconnect recovery |
| ERR-2 | RGB/Preview failure | 03/21 | Last valid preview stale/not-current; true Retry |
| ERR-3 | Anchor model failure | 04A/04B/07A/21 | Keep RGB/Prompt/prior Stable/edit state; Retry/manual |
| ERR-4 | Anchor ambiguity | 07A | Preserve candidates; choose/refine/Paint; no Top-1 |
| ERR-5 | Palette stuck/stale hit region | 07B/21 | Clear transient state on cancel/blur/disposal; old pixels editable |
| ERR-6 | Visible support invalid/background-dominated | 08/21 | Preserve Anchor; Limited/local/user-added fallback |
| ERR-7 | Invalid indoor camera | 08 | Reject before gain; bounded replacement/local fallback |
| ERR-8 | Generate More failure | 08/12 | Preserve every prior segment/View/artifact |
| ERR-9 | Backend descriptor/bundle contradiction | 08A/21 | Backend Not Ready; no dispatch or mutation |
| ERR-10 | Unsupported sequence/reference call | 08A/12/21 | Structured capability failure; no session/dirty state |
| ERR-11 | Prompt synthesis insufficient | 08B/21 | Review/Failed; adjusted View/manual Prompt/Exclude |
| ERR-12 | Route-B technical failure/OOM | 08B/21 | No partial result; eligible B2 fallback or manual recovery |
| ERR-13 | Key-View ambiguous | 08B/09/12 | Retain ProposalSet; no Stable; no auto-fallback |
| ERR-14 | Neighbour contamination/quality Review | 08B/09/21 | Review+Excluded; no route-A semantic downgrade |
| ERR-15 | Publication conflicts with User Confirmed Stable | 08B/12/21 | Retain user authority; automatic result not current Stable |
| ERR-16 | Stale support/bootstrap/segment/Prompt/backend result | 08/08A/08B/12/21 | Discard; never rebind to newer state |
| ERR-17 | View Render Failure | 06/08/11/21 | Keep View record; retry/replacement/exclude |
| ERR-18 | Evidence/Lift failure | 14/20/21 | Preserve RGB/View/Stable/Gallery/proposals/prior Candidate |
| ERR-19 | Scene dependency mutation | 18 | Suspended/read-only; exact Undo or Restart |
| ERR-20 | Cached replay vs true Retry | 03/08B/12/21 | Same attempt idempotent; Retry creates new identity |

## Closure assertions

- Final Spec v1.2 is the only current implementation specification.
- Ticket 07B and Ticket 08 are parallel after 07A.
- Ticket 08 owns visible support, bootstrap, and sparse planning only.
- Ticket 08A owns contracts/registry only.
- Ticket 08B owns production route-B execution and B2 fallback.
- Prompt synthesis, provider, Decision, Assessment, publication and Participation remain separate.
- Ambiguous never publishes an arbitrary Stable Mask or auto-fallbacks.
- Support/bootstrap/acquisition artifacts never become P/N/V.
- Confirmed correction is per-view by default.
- Routes C/D remain future ADR-gated experiments.
- Every destructive/recompute action states retained artifacts and recovery.
