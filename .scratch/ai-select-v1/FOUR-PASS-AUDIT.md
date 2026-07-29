# Five-Pass Bidirectional Traceability Audit — v2.4

The filename is retained for compatibility. v2.4 adds DG-22, retrofit Tickets 04B/07B, reopens Ticket 07A after algorithm review, and moves Ticket 08 behind the floating-palette closure gate.

## Pass 1 — Graph / dependency audit

- Ticket count: 26 total — 22 numbered + 04A + 04B + 07A + 07B
- Missing blocker references: 0
- Cycle detected: False
- Structural initial frontier: [01]
- Topological order length: 26/26
- Result: **PASS**

One valid topological order:

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

v2.4 dependency corrections:

- Ticket 04A consumes the existing Ticket 05 Mask editor/Undo/Confirm seams.
- Ticket 04B follows 04A and owns real Box/Mask visual-prompt adapter enablement.
- Ticket 07A is reopened and depends on 04B plus completed Ticket 07 assessment semantics.
- Ticket 07B follows 07A and owns DG-22 floating-palette interaction.
- Ticket 08 follows 07B and owns Generated View camera validity plus adaptive information gain.
- Ticket 14 still defines/reference-validates P/N/V before Tickets 10 and 13 consume formal Evidence.
- Ticket 20 still productionizes same-decision Direct Evidence only after Tickets 14 and 19.

## Pass 2 — Final Spec / Amendments / DGs → tickets

A curated catalog of **147** inherited and new requirements is mapped in `TRACEABILITY.md`.

Checks:

- Invalid ticket references: 0
- Unmapped DG-20 requirements: 0
- Unmapped DG-21 requirements: 0
- Unmapped DG-22 requirements: 0
- Unmapped Amendment 001 requirements: 0
- Unmapped Amendment 002 requirements: 0
- Result: **PASS**

New v2.4 requirement groups include:

- truthful locked-runtime positive/negative Box capability;
- truthful locked-runtime positive/negative Mask Constraint capability;
- deterministic visual-prompt compilation with fail-closed unsupported combinations;
- Text remaining optional and capability-gated;
- fitted-image-contained draggable palette;
- deterministic edge snapping and collapse;
- Space temporary hide;
- no stale pointer-interception region after move/collapse/hide;
- Target Context-scoped palette state and Restart reset.

Existing Amendment 002 requirements remain:

- versioned exact-RGB-bound PromptState;
- explicit Prompt versus Pixel Edit tools and histories;
- deterministic bounded AutoMaskProposalSet;
- no model-score-only proposal selection;
- 2D-first ranking and candidate hierarchy;
- optional bounded Gaussian support sanity, never ownership Evidence;
- first-class Ambiguous / Unavailable states;
- ProposalDecision separate from ViewAssessmentPolicy;
- Stable Mask replacement only on Confirm;
- real-model locked-runtime quality validation;
- Anchor-only mandatory Three-Stage scope.

## Pass 3 — tickets → specification / reverse scope audit

- Orphan tickets: []
- Every active ticket maps to Final Spec v1.1, an amendment, DG, inherited v1.0, migration, or hardening requirement.
- Ticket 04A maps to Amendment 002 Stage M1 and DG-21.
- Ticket 04B maps to Amendment 002 capability-gated visual prompts and DG-21.
- Reopened Ticket 07A maps to Amendment 002 Stage M2 and remains the declared Three-Stage completion gate.
- Ticket 07B maps to DG-22 and the fitted-image Prompt/Edit interaction requirement.
- Ticket 08 maps to adaptive planning plus the resolved-Anchor prerequisite.
- Tickets 19–21 remain justified by Stages 3–4, Amendment 001, and benchmark gates.
- DG-14 remains deferred.
- Result: **PASS**

No ticket introduces:

- persistent target-session stack;
- fixed user View count;
- direct Candidate 3D patching;
- unified fake Confidence percentage;
- identity-drift requirement;
- separate workspace;
- nearest/top-k/distance attribution fallback;
- complete Contributor as a production gate;
- mandatory semantic detector or semantic object database;
- implicit conversion of Paint strokes into Prompt constraints;
- silent conversion of unsupported Box/Mask constraints into Points;
- palette persistence across unrelated scenes.

## Pass 4 — final outcome → prerequisite reverse dependency audit

Native Selection backtrace:

```text
Ticket 16 native operation
← Ticket 15 current atomic Candidate / explicit Re-Lift
← Ticket 13 base Lift Readiness
← Ticket 14 reference Evidence/Lift contract
← Tickets 11/12 Included Stable View and dirty identity
← Ticket 09 Gallery / selected View correction
← Ticket 08 valid-pose adaptive planning
← Ticket 07B no-blind-spot fitted-image palette
← Ticket 07A resolved Three-Stage Anchor Mask
← Ticket 04B real Box/Mask visual prompts
← Ticket 04A Prompt/proposal foundation + Tickets 05/07 lifecycle/assessment
← Tickets 03/04 authoritative RGB and Mask lifecycle
← Tickets 01/02 context and authoritative renderer
```

Optional assessment branch:

```text
Ticket 10 P1 cross-view assessment
← Ticket 14 per-view P/N/V
← Tickets 07/09 assessment/presentation foundations
```

Production Evidence backtrace:

```text
Ticket 21 calibrated/hardened production
← Ticket 20 same-decision Direct Evidence + RGB continuity
← Ticket 19 authoritative RGB + renderer identity + Render Working Set
← Ticket 14 reference P/N/V semantics and fixtures
```

Reverse checks:

- No consumer precedes definition of its formal artifact.
- Ticket 04A cannot claim adapter/ranking/quality completion.
- Ticket 04B cannot claim ranking or Stable publication completion.
- Ticket 07A cannot close with point-only fake-predictor tests or the targeted Phase 4 browser closure alone.
- Prompt/proposal changes do not invalidate formal Evidence before Confirm.
- ProposalDecision cannot replace post-Stable ViewAssessmentPolicy.
- Ticket 07B changes presentation/pointer routing only.
- Ticket 08 cannot plan from unresolved Anchor proposal or blind-spot authoring state.
- Candidate pose validity precedes information-gain ranking.
- Cross-view assessment and Coverage cannot consume P/N/V before Ticket 14.
- Reference and production Evidence/Candidates cannot collide in identity/readiness.
- Complete Contributor is absent from the mandatory Camera→Native Selection path.
- Result: **PASS**

## Pass 5 — workflows + failures

- Typical inherited flows checked: 9
- Architecture / DG flows checked: 7
- Error/degradation flows checked: 16
- Invalid workflow references: 0
- Invalid error references: 0
- Result: **PASS**

Critical closure checks:

- Camera Inspection can publish RGB while Mask/Evidence are absent.
- Prompt and Paint tools have explicit non-overlapping pointer semantics.
- Visual prompt capability is truthful and unsupported combinations fail closed.
- Stage 1 preserves bounded materially distinct proposal alternatives and score semantics.
- Stage 2 is 2D-first and may return Ambiguous instead of false success/failure.
- Single-candidate quality risk is not silently auto-selected.
- Stage 3 publishes Stable only through Confirm.
- Prior Stable/Evidence/Candidate remain valid during unconfirmed work.
- Floating palette remains inside the fitted image without creating a permanent blind region.
- Move/collapse/Space-hide restore hit testing immediately.
- Generated View automatic Mask publication is not silently changed by the Anchor amendment.
- Ticket 08 rejects outside-room/behind-wall/blank-content candidates before gain ranking.
- Stable Mask publication invalidates exact per-view Evidence but does not auto-Lift.
- Reference P/N/V precedes production same-decision CUDA.
- Evidence failure preserves RGB/View/Mask/Gallery/previous Candidate.
- Reference Contributor failure remains diagnostic only.

## Mechanical critical-phrase audit

Critical semantics were checked in Tickets 03, 04, 04A, 04B, 05, 06, 07, 07A, 07B, 08, 10, 12, 13, 14, 15, 16, 18, 19, 20, 21, and 22.

Required phrases/semantics include:

- `RGB Ready` without Contributor/Evidence;
- explicit new attempt on Retry;
- `PromptState` exact RGB binding;
- explicit adapter capabilities;
- visual-prompt compiler fail-closed behavior;
- bounded `AutoMaskProposalSet`;
- 2D-first ranking and single-candidate quality gate;
- `ambiguous` / `unavailable` distinction;
- ProposalDecision versus ViewAssessment separation;
- Confirm-only Stable publication;
- fitted-image palette drag/collapse/Space-hide/no stale blind region;
- valid observation pose before information gain;
- `P/N/V` and `alpha × incoming transmittance`;
- Render/Evidence Working Set separation;
- same decision source;
- renderer/Evidence/runtime implementation identity;
- complete Contributor debug/reference only;
- no partial proposal/Evidence/Candidate publication.

Failures: []

Result: **PASS**

## Conclusion

No known graph, traceability, reverse-dependency, workflow, or scope gap remains in the v2.4 implementation plan.

This audit validates documentation and implementation ordering, not future code or real-model quality. Ticket 04B requires real visual-prompt adapter validation; reopened Ticket 07A requires ranking/calibration/performance closure; Ticket 07B requires browser interaction validation; Ticket 08 requires indoor camera-validity benchmarks before any may claim completion.
