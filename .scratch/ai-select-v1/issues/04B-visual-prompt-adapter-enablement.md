# 04B — Visual Prompt Adapter Enablement

Status: implemented historical baseline — superseded for current static production by Ticket 04C

Blocked by: 04A

Blocks: 04C

## Current normative mapping

- Final Spec v1.3 §§0, 6–8, 16, 26
- ADR 0016

## Historical outcome

Ticket 04B established truthful capability publication, deterministic Prompt compilation, positive/negative Point support, Positive Box support, raw candidate preservation, and real-model GPU fixtures.

Its production implementation used a SAM 3.1 Multiplex checkpoint and a custom static-image surface built from Multiplex detector/tracker internals. It also proved that a user-authored binary Prompt Brush is not a valid mapping to SAM previous-mask logits and therefore disabled that capability.

The following retained lessons remain valid:

- capability claims must match real runtime behavior;
- unsupported Prompt families fail before inference;
- Prompt, RGB, capability, model and attempt identities are immutable and digest-bound;
- Paint/Erase never enter model requests;
- raw model score is not a correctness probability;
- a binary Prompt Brush must not masquerade as previous-prediction logits;
- Positive Instance Box uses authoritative-image pixel coordinates.

## Superseded current-production claims

Ticket 04C replaces these parts of the 04B implementation:

- SAM 3.1 Multiplex as the static Anchor/Key-View model;
- private tracker-head static prediction and fabricated multiplex state;
- the former generic visual Prompt schema containing Negative Box and Mask Constraints;
- permanent disabled Prompt Brush/Negative Box product placeholders;
- fixed `multimask_output=true` behavior;
- Multiplex-specific Model Manifest and runtime digest.

## Preservation requirements for 04C

04C must preserve:

- exact stale-result rejection;
- deterministic Point/Box compilation;
- candidate Mask/score identity;
- real Retry and cancellation safety;
- User Confirmed Stable Mask authority;
- the negative regression proving binary Brush data is not previous logits.

04B is not reopened. New static production work starts at 04C.
