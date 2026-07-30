# 04B — Visual Prompt Adapter Enablement

Status: implemented — 2026-07-30

Blocked by: 04A

Blocks: 07A closure

## Final Spec mapping

- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- Ticket 04A — Prompt Authoring Layer + Multi-Prompt Proposal Foundation
- Ticket 07A — Three-Stage Anchor Mask Pipeline completion gate

## Purpose

Ticket 04A implemented the generic Prompt domain, capability negotiation, browser tools, request protocol, and bounded proposal seam. The currently locked adapter remains point-only:

```text
points                  true
negativePoints          true
boxes                    false
negativeBoxes            false
maskInput                false
negativeMaskConstraints  false
text                     false
negativeText             false
```

As a result, Box and Prompt Brush are visible only as capability-gated product concepts and cannot yet constrain real model inference.

Ticket 04B enables the non-text visual prompt families end to end:

```text
Positive / Negative Box
Positive / Negative Mask Constraint (Prompt Brush)
```

Text Prompt remains a future capability-gated extension and is not required for this ticket.

## Completion ownership

Ticket 04B owns model-adapter enablement only:

```text
PromptState visual constraints
→ deterministic adapter compilation
→ locked model/runtime request
→ unranked adapter proposal candidates
→ truthful capability advertisement
```

Ticket 04B does not own proposal ranking, candidate clustering, bounded representative selection, ambiguity policy, candidate acceptance, or Stable Mask confirmation. Ticket 07A consumes the enabled capabilities and remains the Three-Stage Pipeline completion owner.

### Strict ownership boundary

Ticket 04B MUST NOT:

- assign a cross-candidate ranking score or choose Ranking weights;
- perform exact/near-duplicate clustering for representative selection;
- define material-distinctness or bounded-set truncation policy beyond validating the existing transport bound;
- choose a suggested or selected proposal;
- publish `ProposalDecision`;
- classify `selected`, `ambiguous`, or `unavailable`;
- define automatic-selection margins or ambiguity reasons.

04B may validate each adapter-returned candidate independently and attach prompt-family diagnostics. It forwards structurally valid candidates to the existing proposal seam without comparing candidates against one another. Ticket 07A owns every cross-candidate operation.

## Inputs / preconditions

- Implemented Ticket 04A `PromptState`, request/result identity, toolbar modes, and capability contract
- Exact authoritative RGB and PromptState digest
- Locked SAM 3.1 runtime or an explicitly declared replacement adapter/runtime
- Existing bounded `AutoMaskProposalSet` publication
- Existing point-only compatibility adapter and tests
- Ticket 07A ranking feature/evaluator seam

## Outputs / handoff artifacts

- Versioned visual-prompt adapter capability identity
- Deterministic Point/Box/Mask-constraint compiler
- Positive and negative support declared separately for each family
- Real-model proposal fixtures for Box and Mask Constraint prompts
- Combined-prompt contract fixtures
- Browser/Companion end-to-end evidence
- Per-candidate prompt-family diagnostics for Ticket 07A

# 1. Verify and lock backend semantics

Before advertising a capability, document the exact locked backend semantics:

- accepted request type and field names;
- coordinate convention and inclusive/exclusive Box boundaries;
- mask encoding, dimensions, polarity, and threshold semantics;
- whether positive and negative constraints are native or adapter-composed;
- supported combinations and ordering rules;
- candidate count and score semantics;
- source commit, model manifest, runtime build, and adapter version.

A capability MUST remain `false` when the locked backend cannot satisfy it without an unversioned heuristic.

# 2. Deterministic prompt compilation

Implement a versioned compiler:

```text
PromptState
→ AdapterPromptProgram
→ model/runtime request(s)
```

The compiler MUST:

- preserve Prompt IDs and polarity in diagnostics;
- bind exact RGB dimensions and digest;
- compile prompts in a deterministic order;
- reject unsupported combinations before inference;
- never silently drop a prompt;
- never silently convert Box/Mask constraints into Points;
- include compiler policy/version in adapter capability identity;
- produce replay-equivalent requests for identical semantic inputs.

A declared, versioned fallback conversion is allowed only when it is part of the adapter contract, separately benchmarked, and visible in diagnostics. It must not masquerade as native support.

# 3. Box Prompt enablement

## 3.1 Positive Box

Enable Positive Box only after the real adapter demonstrates that the Box constrains proposal generation for the intended image coordinate system.

Required behavior:

- non-empty in-bounds rectangle;
- exact mapping from fitted-image pixels to authoritative RGB pixels;
- no off-by-one expansion or clipping;
- Box identity survives Retry and stale-result rejection;
- proposals preserve Box-consistency diagnostics.

## 3.2 Negative Box

Negative Box is an independent capability.

If the backend does not natively support it, keep `negativeBoxes=false` unless a versioned adapter program is implemented and validated. Do not advertise negative support merely because positive Box works.

# 4. Mask Constraint / Prompt Brush enablement

## 4.1 Positive Mask Constraint

The Prompt Brush produces a coarse constraint artifact, not a final Editing Mask.

Required behavior:

- artifact dimensions exactly match authoritative RGB;
- digest and unused bits are validated;
- prompt artifact is immutable and PromptState-bound;
- model inference consumes the constraint without mutating Editing Mask;
- proposal diagnostics record constraint agreement.

## 4.2 Negative Mask Constraint

Negative Mask Constraint is independently capability-gated.

If unsupported natively, it remains disabled unless a declared adapter composition is implemented and benchmarked. It must never be approximated by silently sampling a few negative Points.

# 5. Combined prompt programs

Validate at least:

```text
Point+ + Point−
Point+ + Positive Box
Point+ + Negative Box, when supported
Positive Box + Mask Constraint
Point+/Point− + Positive/Negative Mask Constraint
multiple prompts of the same supported family
```

The adapter must define whether prompt order is commutative. When it is not, the compiler order is normative and versioned.

Unsupported combinations must return `unsupportedPromptCombination` or an equivalent structured capability failure before model execution.

# 6. Proposal publication

Visual prompts must feed the same bounded proposal transport contract established by 04A.

Required properties:

- adapter-returned structurally valid candidates are forwarded without cross-candidate ranking or clustering;
- invalid candidates are rejected individually;
- score name and semantics are preserved without interpreting them as a selection score;
- proposal identities bind model, adapter capability, compiler policy, RGB, PromptState, and attempt;
- no proposal becomes Editing or Stable automatically;
- same-attempt replay remains idempotent;
- explicit Retry mints a new attempt.

Candidate comparison, near-duplicate clustering, material-distinct representative selection, and deterministic truncation policy belong exclusively to Ticket 07A.

# 7. Capability publication

Capabilities switch to `true` only after real runtime validation:

```ts
boxes: boolean;
negativeBoxes: boolean;
maskInput: boolean;
negativeMaskConstraints: boolean;
```

Changing any capability or compilation semantics MUST rotate `capabilityDigest` and invalidate incompatible replay artifacts.

Text fields remain:

```ts
text: false;
negativeText: false;
```

unless a separate later ticket explicitly enables them.

# 8. Ticket 07A handoff

04B must provide enough structured prompt facts for 07A to evaluate:

- Positive Box fill/containment and spill inputs;
- Negative Box overlap inputs;
- Positive Mask agreement inputs;
- Negative Mask disagreement inputs;
- prompt-family-specific candidate rejection causes;
- capability/compiler identity.

04B does not choose Ranking thresholds, combine these facts into a score, compare candidates, cluster candidates, select representatives, or define automatic-selection margins.

# Acceptance criteria

## Capability and protocol

- [ ] Positive Box works through the locked real adapter and advertises `boxes=true`.
- [ ] Negative Box is either genuinely supported and advertises `negativeBoxes=true`, or remains explicitly disabled with a reason.
- [ ] Positive Mask Constraint works through the locked real adapter and advertises `maskInput=true`.
- [ ] Negative Mask Constraint is either genuinely supported and advertises `negativeMaskConstraints=true`, or remains explicitly disabled with a reason.
- [ ] Text capabilities remain unchanged unless separately approved.
- [ ] Capability digest changes whenever supported semantics change.
- [ ] Unsupported families/combinations fail closed before inference.

## Correctness

- [ ] Box coordinates match authoritative RGB pixels at different Dock sizes and device-pixel ratios.
- [ ] Prompt Brush artifact dimensions, digest, and padding bits are validated.
- [ ] No visual prompt is silently discarded or converted to Points.
- [ ] Prompt Brush never directly mutates Editing Mask.
- [ ] Paint/Erase never enters the adapter request.
- [ ] Combined supported prompts are deterministic and replayable.
- [ ] Late results cannot attach to newer PromptState/RGB/capability identity.

## Proposal handoff

- [ ] Visual prompts produce adapter candidates through the existing proposal schema.
- [ ] Proposal diagnostics retain per-family consistency facts.
- [ ] Ticket 07A can reject candidates that violate enabled Box/Mask constraints.
- [ ] 04B performs no cross-candidate ranking, clustering, representative selection, or `ProposalDecision` publication.
- [ ] A one-element compatibility result does not falsely claim multi-candidate quality closure.

## Browser validation

- [ ] Positive Box drag produces a real model request and visible proposal change.
- [ ] Supported negative Box produces a real model request and visible exclusion effect.
- [ ] Positive Prompt Brush produces a real model request and visible proposal change.
- [ ] Supported negative Prompt Brush produces a real model request and visible exclusion effect.
- [ ] Unsupported visual tools remain discoverable but disabled with a precise reason.
- [ ] Retry, Prompt Undo/Redo, Restart Target, and stale-result rejection pass for visual prompts.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- locked real-model/GPU adapter tests
- cross-DPR browser coordinate walkthrough
- Point + Box + Mask combined-prompt walkthrough
- capability rotation/replay incompatibility test
- Ticket 07A hard-consistency contract tests
- ownership regression proving 04B does not rank, cluster, select, or publish `ProposalDecision`

# Non-goals

- No Text Prompt enablement.
- No proposal ranking or cross-candidate scoring.
- No exact/near-duplicate clustering or representative selection.
- No material-distinctness or bounded-set truncation policy.
- No suggested/selected candidate or `ProposalDecision` publication.
- No automatic-selection margin or ambiguity policy.
- No Generated View planner changes.
- No formal P/N/V Evidence.
- No automatic Stable Mask publication on the Anchor path.
- No implicit conversion between Prompt Brush and Paint/Erase.

# Implementation outcome

- The locked SAM 3.1 capability now truthfully enables positive Box and
  positive Mask Constraint. Negative Box, negative Mask Constraint, and Text
  remain disabled with precise adapter-owned reasons.
- `sam3.1-visual-prompt-compiler/v1` binds authoritative RGB dimensions and
  digest, PromptState digest, capability digest, deterministic prompt order,
  inclusive pixel Box semantics, independent Box branches, and binary-union
  Mask composition.
- The real adapter preserves all structurally valid SAM alternatives in source
  order and attaches per-prompt consistency diagnostics. This 04B layer does
  not compare, cluster, rank, truncate, or select candidates; the retained 07A
  proposal seam remains the downstream decision owner.
- Browser trust-boundary validation rejects missing or mismatched visual
  diagnostics, stale capability/compiler identity, malformed Prompt Brush
  dimensions/digest/padding, and unsupported prompt families before inference.
- The Model Manifest and runtime digest rotate for the new compiler/adapter
  semantics. Operators must reinstall the manifest; model weights remain
  external and unchanged.

# Completion evidence

- Focused browser contract tests cover capability rotation, explicit disabled
  reasons, visual-diagnostic completeness, replay identity, Prompt Undo/Redo,
  Retry, Restart Target, and stale-result rejection.
- Focused Companion tests cover deterministic Point/Box/Mask compilation,
  inclusive authoritative pixel coordinates, native-coordinate normalization,
  Mask artifact validation, unsupported-family fail-closed behavior, combined
  prompts, and the unranked candidate handoff.
- The opt-in locked GPU fixture uses source commit
  `5dd401d1c5c1d5c3eedff06d41b77af824517619` and checkpoint SHA-256
  `0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6`.
  It proves Point, positive Box, positive Mask, and combined requests produce
  materially different real-model candidates while retaining all three raw
  alternatives and exact prompt diagnostics.
- Production GPU correctness is established only for this visual-prompt
  adapter slice. It does not establish Direct Gaussian Evidence correctness,
  renderer parity, calibration, or a negative visual-prompt implementation.
