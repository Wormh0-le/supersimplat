# AI Select v1 — Implementation Ticket Graph v2.8

Status: **ready-for-agent planning graph — Ticket 04B remains the next implementation gate**

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.2.md`
2. ADR 0013 where not superseded by v1.2
3. `CONTEXT.md` where not superseded
4. DG-20 through DG-26 as decision rationale
5. `AGENTS.md`
6. Current implementation and tests

Final Spec v1.1 and Amendments 001–005 are historical only. Agents must not reconstruct the old supersession chain.

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

v2.8 has 22 numbered tickets and six retrofit tickets: **04A**, **04B**, **07A**, **07B**, **08A**, and **08B**.

## v2.8 architecture corrections

- Ticket 08 now produces a bounded replayable `VisibleTargetSupportArtifact`.
- `TargetBootstrapArtifact` is a lightweight summary that references visible support by digest.
- 07B Floating Palette and 08 support/planner execute in parallel after 07A.
- 08A is contracts/registry only; it does not run production SAM.
- 08B implements route-B Prompt synthesis, per-view SAM, ProposalSet, conservative Decision, Assessment integration, publication, and B2 route-A fallback.
- Prompt synthesis, inference, proposal decision, assessment, publication, Participation, and P/N/V are separate layers.
- Route-B provider returns a ProposalSet, never a hidden Top-1 Stable Mask or ViewAssessmentResult.
- Materially distinct plausible proposals remain `ambiguous`; no arbitrary Stable Mask is published.
- Backend capabilities derive from the actual `MaskAcquisitionBackend` bundle structure.
- Route B is `perView` only; C/D remain future sequence extension experiments.
- Route-A fallback is automatic only for declared technical/capability failures and may Auto Good only under the same or stricter gates.
- Final ownership remains Included Stable Masks → P/N/V in Tickets 14/20.

## Dependency graph

```text
01 CurrentTargetContext kernel
 │
 ▼
02 AI Select shell + authoritative gsplat Anchor
 ├───────────────────┐
 ▼                   ▼
03 Camera            04 Anchor AIView + Mask/Evidence lifecycle
   Inspection +       │
   RGB Retry           │
 └──────────┬──────────┘
            ▼
05 Anchor editing + support validation + Confirm + Early Restart
 ├──────────────────────────────┐
 ▼                              ▼
04A Prompt Authoring            06 First Generated AIView + route-A baseline
 + Proposal Foundation           │
 │                               ▼
 ▼                              07 Local Assessment + Participation
04B Visual Prompt Adapter        │
 Enablement                      │
 └──────────────────┬────────────┘
                    ▼
07A Object-level Anchor Acquisition / Conservative ProposalDecision
 ├──────────────────────────────┐
 ▼                              ▼
07B Floating Prompt/Edit        08 Visible Support + Bootstrap
 Palette UX                         + Sparse Key-View Planner
 │                                  │
 │                                  ▼
 │                              08A Acquisition Contracts
 │                                  + Backend Registry
 │                                  │
 │                                  ▼
 │                              08B Route-B Production Acquisition
 │                                  │
 └───────────────┬──────────────────┘
                 ▼
09 Scalable Gallery + Frustum / Acquisition Inspection
 ├──────────────────┐
 ▼                  ▼
11 User-added View  12 Prompt/Mask Refresh + Dirty/Stale
 └──────────┬───────┘
            ▼
14 Reference P/N/V Evidence + Gaussian Lifting/Candidate
 ├──────────────────┐
 ▼                  ▼
10 Cross-view P1    13 Visible Evidence Coverage + Readiness
 Assessment          │
 └──────────────────┘
            ▼
15 Candidate correction + Evidence-aware explicit Re-Lift
            │
            ▼
16 Native Set/Add/Remove/Intersect
            │
            ▼
17 Applied Undo-and-Fix + Restart + multi-object/tool-switch
            │
            ▼
18 Scene Mutation Suspended + Exact Undo Recovery
            │
            ▼
19 Large SceneSnapshot + authoritative RGB / Render Working Set
            │
            ▼
20 Same-decision GPU Evidence + artifact/working-set hardening
            │
            ▼
21 Retry/OOM/atomic publication + calibration/release hardening
            │
            ▼
22 Contract legacy product and Contributor paths
```

## Dependency notes

- Ticket 04A and Ticket 06 may proceed after Ticket 05.
- Ticket 04B follows 04A.
- Ticket 04B and completed Ticket 07 converge at 07A.
- After 07A, Ticket 07B and Ticket 08 may proceed in parallel.
- Ticket 08 produces support/bootstrap/planner artifacts.
- Ticket 08A defines acquisition contracts and registry.
- Ticket 08B implements route-B production acquisition.
- Ticket 09 consumes real generic acquisition/proposal/decision states from 08B.
- Ticket 11 depends on 07B for complete correction UX.
- Ticket 21 depends on 07B and 08B for final interaction/acquisition release hardening.

## One valid topological order

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 08B → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

The order lists 07B before 08 for readability; they are structurally parallel after 07A.

## Artifact chain

```text
07A Anchor Stable Mask
→ 08 VisibleTargetSupportArtifact
→ 08 TargetBootstrapArtifact
→ 08 SparseKeyViewPlanSegment
→ 08B KeyViewPromptArtifact
→ 08B KeyViewMaskProposalSet
→ 08B KeyViewMaskDecision
→ 07/08B ViewAssessmentResult
→ 08B MaskPublication result / Stable Mask
→ 09/12 Review, Participation, dirty lifecycle
→ 14 per-view P/N/V
→ 15 current Candidate
```

Contract foundation:

```text
08A Backend Descriptor
→ Backend Bundle
→ Backend Registry
→ perView Provider contract
→ optional Sequence extension contract
```

No artifact edge flows from future C/D back into current Ticket 08 planning.

## Audit artifacts

- `TRACEABILITY.md`: single Final Spec v1.2 mapping; no overlay.
- `FOUR-PASS-AUDIT.md`: six-pass v2.8 graph, artifact, reverse-scope, workflow, and failure audit.
- `WALKTHROUGHS.md`: route-B layered pipeline, B2 fallback, ambiguity, and C/D extension readiness.
- `manifest.json`: machine-readable v2.8 graph and audit metadata.

## Implementation rules

- Ticket 04B remains the next executable implementation ticket.
- Ticket 07A fails conservatively on material Anchor ambiguity.
- Ticket 07B changes interaction/pointer routing only and runs parallel with Ticket 08.
- Ticket 08 uses early geometry for support/planning/Prompt context, never ownership or Masks.
- Ticket 08A defines stable types, validators, digests, backend bundle/registry and sequence schemas only.
- Ticket 08B implements route B directly and is not blocked by route comparison.
- The provider returns ProposalSet only; Decision, Assessment, Publication and Participation are separate.
- Ambiguous never publishes an arbitrary Stable Mask.
- Route-A fallback is technical-only and fully provenance-bound.
- Route B has no sequence/reference implementation.
- A later ADR is mandatory before tracker/hybrid production adoption.
- Confirmed correction does not automatically create reference memory.
- Key-View role and backend never imply Lift Participation.
- Support/bootstrap are not hard Evidence Working Set bounds.
- Ticket 14 is the reference correctness gate; Ticket 20 owns production same-decision Evidence.
- Complete Contributor remains reference/debug only.
