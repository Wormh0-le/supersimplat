# Project Documentation and Traceability

Read this file when changing guidance, vocabulary, current planning, or historical records. Also read [Agent guidance structure](README.md).

## Ownership

- [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) owns the current product contract, accepted simplification, retained user behavior, outcome roadmap, rolling queue, and explicit supersedes mapping.
- Active queue issues own concrete scope, blockers, necessary inputs, acceptance evidence, and implementation status. Outcome tracks and conditional research are not a second executable backlog.
- Root `CONTEXT.md` owns stable vocabulary, not task counts, readiness, production parameter values, release status, or detailed implementation plans.
- `docs/agents/**` owns task-specific agent guidance. `.interface-design/system.md` owns reusable interface/layout rules.

Do not restore deleted specs, ADRs, reviews, tickets, or `.scratch` as a parallel current control plane. Historical specifications remain reachable through immutable commit `504e8885b87575761dc2e367e520b7dfba46884b`; the pre-simplification repository is `b76aa99c0545988f3807677105052260e476cbce`.

## Lifecycle

A material decision names the problem, chosen simplification, retained behavior, and explicit supersedes scope in #37. Update the owning active slice and relevant guidance, not every historical document. Do not let an old specification override a later accepted scope decision.

Superseded unimplemented issues close as `not_planned`, with a title routing to their replacement in #37 and no ready label. Their original bodies/comments may remain intact for traceability; historical ready/blocker wording is not current authority. Preserved Q10/Q11 behavior remains required even when its original planning ticket is archived. Do not mark cancelled plans completed or erase previous acceptance evidence.

Feature completion needs evidence, not a closed dependency alone. Update the completed slice and current queue; do not maintain the retired parent graphs. Distinguish code review, actual test execution, runtime qualification, and permission to activate production.

## Validation

For content-only changes, check current authority, retained behaviors, links, terminology, Issue status/replacement mapping, label meaning, and consistency with the active queue. Check the diff contains no unintended executable change. Use [Project verification](execution-and-verification.md); do not claim runtime testing from documentation checks.

Keep rationale short and tied to the actual failure or user outcome. Avoid adding a new process document for every internal implementation step.
