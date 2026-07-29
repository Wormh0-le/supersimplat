# 07A — Object-level Anchor acquisition + conservative ProposalDecision

Status: reopened — object-level algorithm closure incomplete; retained browser/layout work remains accepted

Blocked by: 04A, 04B, 05, 07

Blocks: 07B

## Final Spec mapping

- Final Spec v1.1 §§10–13, 23, 26, 30–32
- Amendments 002 and 003
- DG-21 and DG-23
- Tickets 04B and 07

## Completion ownership

Ticket 07A owns the Anchor-only path:

```text
prompt-conditioned object proposals
→ conservative 2D-first ProposalDecision
→ Accept / Edit / Confirm
→ object-level Anchor Stable Mask
```

It does not own whole-image inventory, arbitrary part discovery, multi-view tracking, camera planning, or Gaussian ownership. Ticket 08/08A consume the confirmed Anchor as an object-identity seed.

## Superseded closure language

Amendment 003 supersedes the prior requirement to resolve materially distinct candidates through a benchmark-calibrated automatic Top-1 margin.

07A still requires locked-runtime benchmarks, but they validate a conservative policy:

- block obvious false auto-selection;
- detect/expose neighbour-object contamination;
- gate suspicious unique candidates;
- return `ambiguous` for multiple materially distinct plausible clusters;
- preserve manual/Prompt recovery;
- meet latency and memory bounds.

No model or policy score is a correctness probability unless separately proven.

## Retained completed work

Do not regress:

- exact RGB/Prompt/model/adapter/policy/attempt proposal identity;
- bounded `AutoMaskProposalSet` and explicit `ProposalDecision`;
- atomic Paint/Erase history;
- persistent Prompt markers and separate Prompt/Mask histories;
- explicit Accept before Editing Mask;
- Confirm-only Stable publication;
- stale-result rejection;
- proposal/status panel and primary action separation;
- resizable Dock and one fitted RGB/Mask/Prompt/pointer rectangle;
- schema-v2 cross-language digest.

## Remaining blockers

1. Single eligible candidate currently bypasses structural quality gating.
2. Truncation occurs before near-duplicate clustering.
3. Default candidate relies mainly on raw model score.
4. Unavailable causes collapse into generic prompt conflict.
5. Production-resolution feature extraction is unvalidated.
6. Boundary, containment, component, and neighbour-leak features are coarse.
7. Box/Mask consistency awaits Ticket 04B real adapter validation.
8. Frozen-scene contamination, stability, latency, and memory evidence is incomplete.

# Stage 1 — Object proposal preparation

Required flow:

```text
adapter candidates
→ structural validation
→ exact digest dedup
→ near-duplicate clustering
→ deterministic representative per cluster
→ materially distinct object-level clusters
→ bounded proposal set
```

Requirements:

- preserve declared raw-score semantics;
- bind proposals to exact RGB, PromptState, model, adapter/compiler, policies, and attempt;
- reject invalid candidates individually with diagnostics;
- cluster before truncation;
- publish no partial/stale set;
- preserve idempotent same-attempt replay and real Retry.

Stage 1 must not publish Stable Mask, select solely by model score, require whole-image inventory, or fabricate P/N/V.

# Stage 2 — Conservative 2D-first decision

## Hard consistency

Every capability-enabled Prompt family participates:

- positive Point inside;
- negative Point outside;
- positive Box fill/containment;
- negative Box overlap limit;
- positive/negative Mask Constraint agreement;
- future Text semantics only when advertised;
- exact RGB/Prompt/adapter/policy identity.

Advertised capability without an evaluator fails closed.

## Structural diagnostics

Record at least:

- area and bounding box;
- component count and largest-component ratio;
- positive-Point component;
- soft containment/nesting;
- pairwise IoU and area ratio;
- boundary contact and compactness;
- distance-transform Point-to-boundary distance;
- Box fill/spill;
- Mask-constraint agreement;
- near-duplicate cluster and materially-distinct relation.

## Single-cluster quality gate

One cluster becomes `ambiguous` when risk includes extreme area, substantial disconnected components, low largest-component ratio, excessive image-edge contact, Point near boundary, Box spill, constraint disagreement, likely neighbour leakage, or repeated-run instability.

## Minimum decision rules

```text
0 eligible clusters
→ unavailable

1 credible eligible cluster
→ selected

1 risky eligible cluster
→ ambiguous

2+ materially distinct plausible clusters
→ ambiguous
```

The user resolves material ambiguity through candidate choice, Box/negative Point/Mask refinement, or direct editing.

## Model score

Model score may select a representative inside one near-duplicate cluster or the default preview in `ambiguous`. It cannot override Prompt consistency, rescue structural invalidity, be shown as a correctness percentage, or silently resolve materially distinct clusters.

## Optional Gaussian support

Low-cost support may report computability, gross sparsity, or disconnected projected support. It is not P/N/V, ownership, or the primary selector.

## Structured reasons

At minimum:

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
nested-object-scope-ambiguity
multiple-disconnected-targets
box-spill
neighbour-object-leak-risk
model-score-disagreement
single-candidate-quality-risk
multiple-materially-distinct-candidates
```

Every reason maps proposal/cluster IDs to a corrective action.

# Stage 3 — Accept / Edit / Confirm

```text
selected
→ explicit Accept
→ Editing Mask

ambiguous
→ choose / refine / Paint / Retry

unavailable
→ refine / Retry / manual Empty→Paint

Editing Mask
→ Confirm
→ Stable Mask
→ Ticket 07 ViewAssessment / Participation
```

Prompt/proposal work never mutates the prior Stable Mask. Paint/Erase modifies Editing Mask only and does not silently rerun ProposalDecision. Confirm Anchor blocks unresolved Prompt/proposal/edit state.

The confirmed Anchor is an object-identity seed, not Gaussian ownership.

# Performance and frozen-scene validation

Validate at:

```text
1280×720×4 proposals
1920×1080×4 proposals
```

Use packed/vectorized Mask operations; no Python `list[bool]` production hot path.

Cases include table surrounded by chairs, similar chairs, cabinet/door, monitor/desk/wall, refrigerator/wall, thin/small objects, image-edge contact, fragmented render, no proposal, and multiple plausible object candidates.

Report acceptable-mask rate, one-refinement success, Prompt count, neighbour contamination, false auto-selection, ambiguous/unavailable rates, manual recovery, repeat stability, latency, host memory, VRAM, model-score ablation, and optional-support ablation.

Mandatory regression:

```text
one positive click on a table surrounded by chairs
→ never silently accept table + multiple chairs
```

# Acceptance criteria

- [ ] Cluster before bounded truncation.
- [ ] Retain materially distinct object-level clusters deterministically.
- [ ] Preserve candidate rejection diagnostics and digest golden vectors.
- [ ] Apply all enabled Prompt families as hard consistency.
- [ ] Implement single-cluster quality gate.
- [ ] Implement the minimum conservative decision rules.
- [ ] Multiple materially distinct plausible clusters return `ambiguous`.
- [ ] Model score is not the sole selector; ablation exists.
- [ ] Structured reasons map to corrective actions.
- [ ] 720p/1080p gates pass.
- [ ] Accept, Editing, Stable, Assessment, and Participation remain distinct.
- [ ] Manual recovery works from every decision state.
- [ ] Confirmed Anchor handoff is identity seed only.
- [ ] Ticket 04B Box/Mask paths and truthful capabilities pass.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- locked-runtime adapter smoke
- frozen-scene decision benchmark
- browser Accept/Edit/Confirm walkthrough

# Non-goals

- No whole-image object inventory.
- No arbitrary part-level discovery.
- No general calibrated Top-1 ranker.
- No multi-view tracking, camera planning, or final P/N/V ownership.
- No automatic resolution of materially distinct plausible candidates.