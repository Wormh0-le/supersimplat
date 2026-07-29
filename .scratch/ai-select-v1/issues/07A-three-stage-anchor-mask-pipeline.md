# 07A — Complete Three-Stage Anchor Mask Pipeline + Ranking / Ambiguity UX

Status: reopened — algorithm closure incomplete after 2026-07-29 review; Phase 4 browser layout fixes retained

Blocked by: 04A, 04B, 05, 07

Blocks: 07B

## Final Spec mapping

- Final Spec v1.1 §§10–13, 23, 26, 30–32
- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- Ticket 04B — Visual Prompt Adapter Enablement
- Ticket 07 — Local ViewAssessmentPolicy + Participation

## Completion ownership

Ticket 07A remains the end-to-end completion owner for:

```text
Stage 1 — Prompt-conditioned Proposal Generation integration
Stage 2 — 2D-first Proposal Ranking / Ambiguity Decision
Stage 3 — Candidate Acceptance / Editing / Confirm
```

Ticket 04A owns Prompt/proposal infrastructure. Ticket 04B enables real Box and Mask-constraint adapter semantics. Ticket 07B owns the post-07A movable/collapsible floating palette. Ticket 07A alone may claim the Three-Stage Anchor Mask Pipeline complete.

## Retained completed work

The following work remains valid and must not regress:

- exact RGB/Prompt/model/adapter/policy/attempt proposal identity;
- bounded `AutoMaskProposalSet` and explicit `ProposalDecision`;
- atomic Paint/Erase stroke history;
- persistent positive/negative prompt markers and active cursors;
- separate Prompt and Mask histories;
- explicit Accept Candidate before Editing Mask;
- Confirm-only Stable Mask publication;
- stale-result rejection against Prompt and local-edit revisions;
- distinct proposal/status panel and primary action area;
- vertically resizable AI Select Dock;
- fitted image rectangle shared by RGB, Mask, Prompt overlays, box preview, and pointer mapping;
- neutral non-interactive space outside the fitted image;
- localized Prompt summary and nonduplicated failure presentation;
- schema-v2 cross-language ProposalSet digest based on shared binary64 number canonicalization.

Ticket 07B may change palette placement behavior but must preserve this fitted-image and lifecycle foundation.

## Reopening findings

The targeted Phase 4 browser closure fixed proposal publication and Dock layout, but algorithm review found that Stage 2 still behaves as a conservative ambiguity heuristic rather than a production-calibrated 2D-first ranking policy.

Closure blockers:

1. A single eligible candidate is selected without structural quality gating, so one oversized table-plus-chairs mask can still silently win.
2. Multiple materially distinct candidates are generally classified ambiguous without a benchmark-calibrated ranking score or decision margin.
3. Suggested candidate selection still relies primarily on raw model score.
4. Unavailable outcomes collapse several distinct causes into a generic prompt conflict.
5. Candidate truncation occurs before near-duplicate clustering and may discard useful alternatives.
6. Pure-Python per-pixel feature extraction and pairwise scans are not validated at production image sizes.
7. Point boundary distance, containment, and neighbour-leak features are coarse heuristics.
8. Box and Mask Constraint hard consistency cannot be considered complete until Ticket 04B enables and validates their real adapter semantics.
9. Frozen-scene score/support ablations, stability runs, latency, and peak-VRAM evidence remain incomplete.

# Stage 1 — Proposal Generation integration

Consume Ticket 04A/04B output without collapsing materially distinct alternatives.

Required flow:

```text
adapter candidates
→ structural validation
→ exact-mask digest deduplication
→ near-duplicate clustering
→ materially distinct representative selection
→ deterministic bounded proposal set
```

Stage 1 MUST:

- preserve raw score name and declared semantics;
- bind every proposal to RGB, PromptState, model, adapter capability/compiler, proposal policy, ranking policy, and attempt identities;
- reject invalid candidates individually;
- retain candidate-level rejection diagnostics;
- cluster near duplicates before applying the proposal-count bound;
- record deterministic truncation/cluster policy;
- publish no partial set on failure or cancellation;
- preserve same-attempt replay and explicit new-attempt Retry.

Stage 1 MUST NOT:

- publish Stable Mask;
- select solely by `out_probs` or another raw model score;
- turn ambiguity into technical failure;
- require formal P/N/V Evidence.

A one-element proposal set remains legal, but it is not automatically high quality.

# Stage 2 — 2D-first Proposal Ranking

## 2.1 Ranking priority

The versioned policy must prioritize:

```text
1. hard prompt consistency
2. candidate hierarchy and relative geometry
3. 2D structural quality
4. declared model score
5. optional bounded Gaussian support sanity
```

No field is a calibrated correctness probability unless separately proven.

## 2.2 Hard prompt consistency

Candidate eligibility must evaluate every capability-enabled prompt family:

- positive Point inside Mask;
- negative Point outside Mask;
- positive Box fill/containment above policy threshold;
- negative Box overlap below policy threshold;
- positive Mask Constraint agreement above threshold;
- negative Mask Constraint disagreement below threshold;
- supported Text semantics when a future adapter enables Text;
- exact RGB/Prompt/adapter/policy identity.

If a capability is advertised but no evaluator exists, fail closed with a structured policy error. Do not silently ignore the prompt.

## 2.3 Structural features

Record at least:

- area fraction and bounding box;
- connected-component count;
- largest-component ratio;
- component containing each positive Point;
- soft containment ratio and nesting graph;
- pairwise IoU and area ratio;
- boundary-contact fraction;
- compactness/perimeter proxy;
- distance-transform-based positive-Point boundary distance;
- Box fill and spill ratios;
- Mask-constraint overlap/disagreement;
- near-duplicate cluster identity;
- materially distinct relation.

Exact one-pixel containment is insufficient. Containment thresholds must be benchmark-owned policy data.

## 2.4 Single-candidate quality gate

Exactly one eligible candidate does not imply automatic selection.

A single candidate must enter Review/Ambiguous refinement when structural diagnostics indicate risks such as:

- extreme area fraction;
- multiple substantial disconnected components;
- low largest-component ratio;
- excessive boundary contact;
- positive Point unnaturally close to candidate boundary;
- large Box spill;
- low prompt-constraint agreement;
- instability across repeated equivalent runs or prompt revisions.

The policy must distinguish:

```text
selected — unique and structurally credible
ambiguous — plausible but suspicious; user refinement/acceptance required
unavailable — no prompt-consistent editable candidate
```

## 2.5 Multi-candidate ranking and calibrated margin

For materially distinct eligible candidates, implement a versioned ranking function or decision tree whose inputs and thresholds are explicit.

Automatic Top-1 selection requires:

- no active ambiguity reason;
- benchmark-calibrated margin over alternatives;
- stability under declared score/numeric perturbations;
- no single feature, including model score or optional support, dominating outside policy.

When the margin is insufficient, preserve alternatives and return `ambiguous`.

## 2.6 Model score semantics

The model score:

- remains declared by adapter semantics;
- is one ranking feature only;
- is never shown as a correctness percentage;
- requires frozen-scene ablation;
- cannot rescue a prompt-inconsistent or structurally invalid candidate.

## 2.7 Optional Gaussian support sanity

Low-cost support may provide:

- computability check;
- gross support-sparsity warning;
- bounded tie-break between otherwise comparable 2D candidates;
- projected-support disconnectedness warning.

It MUST NOT:

- become formal P/N/V Evidence;
- classify Gaussian ownership;
- be the primary selector;
- override prompt consistency;
- use nearest/top-k/distance attribution as formal semantics;
- destroy all editable candidates solely because center-projection support is weak.

The decision record must state whether support participated and whether removing it changes the result.

## 2.8 Structured unavailable and ambiguity reasons

Do not collapse all empty outcomes to `prompt-conflict`.

Required reason families include:

```text
no-foreground-candidate
positive-point-missed
negative-point-included
positive-box-underfilled
negative-box-overlap
positive-mask-disagreement
negative-mask-overlap
all-candidates-full-frame
all-candidates-structurally-invalid
nested-part-vs-whole
similar-score-different-area
multiple-disconnected-targets
box-spill
neighbour-object-leak-risk
model-score-disagreement
single-candidate-quality-risk
insufficient-decision-margin
```

Each reason must carry affected proposal IDs and map to a corrective action.

# Stage 3 — Acceptance / Editing / Confirm

## Selected

```text
selected proposal
→ explicit Accept Candidate
→ Editing Mask
```

Selection never publishes Stable automatically.

## Ambiguous

Preserve 2–4 materially distinct alternatives and allow:

- explicit alternative selection;
- Point/Box/Mask prompt refinement according to capability;
- Paint/Erase manual or hybrid correction;
- Retry or prompt reset.

A suggested candidate may be shown but must not claim certainty.

## Unavailable

Preserve RGB, PromptState, prior Stable Mask, and local Editing Mask. Allow prompt revision, Retry, and manual Empty→Paint. Do not relabel the View as Render Failed.

## Manual/hybrid editing

Paint/Erase modifies Editing Mask only. Accepted proposal provenance remains recorded. Ranking is not silently rerun and PromptState is not inferred from painted pixels.

## Confirm and Ticket 07 integration

```text
Editing Mask
→ Confirm Mask
→ Stable Mask revision
→ Ticket 07 ViewAssessmentPolicy
→ Good / Review / Failed
→ Participation default
```

`ProposalDecision` and `ViewAssessmentPolicy` remain distinct.

Confirm Anchor must block pending/unresolved prompt, proposal, ranking, or edit state. A user-confirmed manual/hybrid Mask may proceed after automatic ambiguity/unavailable recovery.

# Performance requirements

The ranking implementation must be validated at production resolutions and bounded proposal count.

Preferred implementation characteristics:

- packed-bit or vectorized area/IoU operations;
- vectorized connected components/distance transform through an approved dependency or efficient native path;
- one-pass reusable per-candidate statistics;
- unordered pair computation reused for both directed relations;
- no Python `list[bool]` expansion as the production hot path.

Required benchmark cases:

```text
1280 × 720 × 4 proposals
1920 × 1080 × 4 proposals
```

Report latency, peak host memory, and peak VRAM where model inference participates.

# Required real-scene validation

Frozen authoritative gsplat RGB cases must include:

- table top surrounded by chairs;
- whole table versus table-top part;
- chair beside table with similar color;
- cabinet door versus whole cabinet;
- monitor versus wall/desk;
- thin object;
- object touching each image edge;
- fragmented 3DGS render;
- small object;
- no valid proposal;
- multiple plausible nested proposals.

Report:

```text
first-interaction acceptable-mask rate
acceptable mask after one refinement
mean prompt actions
neighbour-object contamination
reference IoU where available
false auto-selection rate
ambiguous rate
proposal-unavailable rate
manual recovery success
decision stability across repeated runs
ranking latency and host memory
end-to-end latency and peak VRAM
model-score ablation
optional-support ablation
```

Mandatory regression:

```text
one positive click on table top
→ must not silently auto-select table + multiple chairs
```

Acceptable outcomes are correct selection, explicit part/whole ambiguity, or prompt refinement request.

# Acceptance criteria

## Stage 1

- [ ] Near-duplicate clustering occurs before bounded truncation.
- [ ] Materially distinct alternatives are retained deterministically.
- [ ] Candidate-level rejection diagnostics survive to ProposalDecision.
- [ ] Cross-language schema-v2 digest golden vectors remain valid.
- [ ] Late/cancelled results cannot publish partial or stale proposals.

## Stage 2

- [ ] Every capability-enabled prompt family participates in hard consistency.
- [ ] Single-candidate structural quality gate is implemented.
- [ ] Multi-candidate ranking has explicit versioned policy and calibrated margin.
- [ ] Model score is not the sole selector and has ablation evidence.
- [ ] Optional support is bounded and has ablation evidence.
- [ ] Decision stability is tested under repeated runs/perturbations.
- [ ] Structured ambiguity/unavailable reasons map to corrective actions.
- [ ] 720p/1080p performance gates pass.

## Stage 3

- [ ] Accept Candidate is explicit.
- [ ] Proposal, Editing, Stable, Assessment, and Participation states remain distinct.
- [ ] Existing Stable/Evidence/Candidate remain current until replacement Confirm.
- [ ] Manual Paint/Erase recovers from every proposal state.
- [ ] Generated View automatic publication remains unchanged.

## Ticket 04B integration

- [ ] Positive Box and Positive Mask Constraint real adapter paths pass.
- [ ] Negative Box/Mask capabilities are truthfully enabled or remain explicitly disabled.
- [ ] Box/Mask constraint diagnostics reach ranking.
- [ ] Text remains capability-gated and is not required for closure.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- cross-language proposal digest golden fixtures
- locked real-model/GPU benchmark
- frozen-scene ranking benchmark
- model-score and optional-support ablations
- 720p/1080p ranking performance benchmark
- real browser proposal selection/refinement/manual-recovery walkthrough
- Ticket 05 Confirm and Ticket 07 Assessment integration
- Generated View automatic publication regression

# Non-goals

- No floating palette drag/collapse/Space-hide work; Ticket 07B owns it.
- No Adaptive Generated View planner; Ticket 08 owns it.
- No cross-view proposal ranking.
- No formal P/N/V Evidence.
- No semantic object database.
- No mandatory Text Prompt enablement.
- No direct 3D Candidate editing.

# Dependency graph segment

```text
04A → 04B ───────────────┐
                          ▼
05 → 06 → 07 ─────────── 07A
                          │
                          ▼
                         07B
                          │
                          ▼
                          08
```

## Phase 4 retained implementation record — 2026-07-29

The completed Phase 4 pass:

- moved the Prompt/Edit toolbar into the fitted image surface;
- separated scrollable proposal/status information and fixed primary actions;
- added native vertical Dock resizing;
- unified RGB/Mask/Prompt/box/pointer mapping on one `ResizeObserver`-driven fitted rectangle;
- made outside space neutral and non-interactive;
- localized Prompt summaries and collapsed technical failure details;
- fixed `maskArtifactInvalid` through schema-v2 shared binary64 numeric canonicalization;
- validated a real gsplat Anchor and installed SAM 3.1 proposal path.

Those fixes remain accepted. They do not substitute for the reopened algorithm, calibration, performance, and multi-prompt closure requirements above.
