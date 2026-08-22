# V2I — Browser loop orchestration + attempt semantics

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2F, V2G
Blocks: V2J

## Final Spec v2.0 mapping

- Final Spec v2.0 §3 (runtime ownership), §8 (attempt/lifecycle);
  `CONTEXT.md` non-normative "Acquisition Loop Orchestration and Attempt
  Semantics"

## Goal

Generalize the implemented serial generated-view queue into the acquisition
loop state machine: browser-driven stepwise orchestration over the existing
validated transport, with Companion loop-scoped derived state and whole-loop
attempt semantics.

## Inputs / preconditions

- `src/ai-select/generated-view-controller.ts` serial queue + per-View
  pipeline pattern (generalization, not a new transport);
- View Utility selection + rescoring triggers (V2F);
- budgets/stop reasons/termination (V2G);
- Companion consensus cache keyed by target + dependency identity (V2C).

## Outputs / handoff

- Browser loop state machine: candidate selection request → render →
  Mask/Evidence → rescore, stepwise, consuming readiness reasons, never
  publishing;
- Companion loop-scoped derived state alive across requests keyed by target +
  dependency identity, disposable by policy; no autonomous Companion session —
  every request independently validated, identity-bound, replayable;
- attempt semantics for the whole loop: one attempt, exact same-attempt
  replay, Cancel effective immediately preserving all completed Views /
  Stable Masks / raw Evidence / prior Candidate, suspend/resume only at View
  boundaries, dependency changes stale a suspended attempt instead of silent
  resume;
- progressive publication of only independent, complete, identity-correct AI
  Views; late results never overwrite newer dependency identities.

## Acceptance criteria

- [ ] The loop runs over the existing validated request/response transport;
      no new transport or Companion-autonomous session exists.
- [ ] Every request is independently validated and identity-bound.
- [ ] Whole loop = one attempt; exact same-attempt replay reproduces the same
      observable sequence (deterministic policies).
- [ ] Cancel takes effect immediately and preserves all completed products.
- [ ] Suspend/resume only at View boundaries; dependency change marks the
      suspended attempt stale instead of silently continuing.
- [ ] Iteration failure preserves all independently valid products; late
      results never attach to a newer dependency identity.
- [ ] Native Selection never changes as a result of internal consensus
      revisions.
- [ ] The browser consumes readiness reasons but holds no publication
      authority.

## Validation

- State-machine tests for each stop reason / cancel / suspend path;
- replay determinism tests across the loop;
- stale-on-dependency-change tests;
- existing generated-view-controller regression suite stays green.

## Non-goals

- No UI controls (V2J), no publication policy (V2H), no utility/budget math.
