# 04A — Historical Prompt Authoring + Proposal Foundation

Status: implemented historical foundation — current Prompt contract is migrated by Ticket 04C

Blocked by: 03, 04, 05

Historical consumer: 04B

Current migration consumer: 04C

## Current normative mapping

- Final Spec v1.3 §§4, 6–8, 16, 24–26
- ADR 0016

## Current status

Ticket 04A proved several reusable foundations:

- Prompt Authoring and direct Mask Editing are separate modes and histories;
- Prompt/RGB/model/capability/attempt identity is immutable and digest-bound;
- model output is transported as a bounded candidate set rather than silently publishing a Stable Mask;
- Accept, Editing Mask and Confirm are distinct;
- stale results fail closed;
- Paint/Erase mutate Editing Mask only;
- raw model score is not a correctness probability.

Ticket 04C is the current owner of the production Prompt schema and adapter migration.

## Superseded 04A surface

The original 04A implementation and the historical record below modeled a generic Prompt surface containing:

```text
Negative Box
Positive/Negative Prompt Brush or Mask Constraint
Positive/Negative Text Prompt
multiple Positive Boxes
```

Those families are not current v1 requirements. Final Spec v1.3 removes them from PromptState, toolbar, capability records and model requests.

The current v1 Prompt surface is exactly:

```text
Positive Point
Negative Point
at most one Positive Instance Box
```

Paint and Erase remain Editing Mask tools. Previous-prediction logits are Companion-owned internal refinement state and are not a Prompt Brush or binary Mask.

## Preservation requirements for 04C and 07A

Current implementation must preserve:

- exact authoritative-image pixel coordinates;
- deterministic Point/Box compilation;
- Prompt and Editing histories remaining separate;
- bounded candidate transport;
- explicit user candidate choice for one-click ambiguity;
- explicit Accept before Editing Mask;
- Confirm-only Anchor Stable publication;
- Retry/cancellation/stale-result safety;
- User Confirmed Stable Mask authority.

Current implementation must not preserve as active behavior:

- Negative Box or Mask Constraint evaluators;
- Prompt Brush tools or brush-to-`mask_input` conversion;
- Text Prompt fields;
- permanent disabled placeholders for removed tools;
- fixed `multimask_output=true` for every request;
- automatic model-score selection as correctness.

## Historical implementation record

The remainder of the former 04A design is represented by repository history and existing migration fixtures. It is non-normative and must not be reconstructed as a current closure gate.

## Current acceptance criteria

- [x] Historical Prompt/Edit separation and candidate identity are retained.
- [ ] Ticket 04C rotates Prompt schema/capability identity and removes excluded Prompt families.
- [ ] Ticket 07A uses the simplified candidate-choice flow rather than the historical general ranker.
- [ ] Old Prompt artifacts fail current schema validation instead of being converted.

## Non-goals

- No current model migration; Ticket 04C owns it.
- No current candidate-choice completion; Ticket 07A owns it.
- No Negative Box, Prompt Brush, Mask Constraint or Text compatibility UI.
