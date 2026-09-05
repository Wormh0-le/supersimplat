# AI Select Domain Authority

Read this file for behavior, terminology, scope, or implementation eligibility.

## Current authority

[Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) owns the accepted product contract, simplification decision, preserved Q10/Q11 behavior, and rolling queue. Read its current body before following an older document.

Authority order:

1. The accepted current decisions in #37, including its explicit supersedes and retained-behavior sections.
2. The relevant active queue issue, its accepted decisions, actual blockers, and evidence.
3. Unchanged product requirements and accepted implementation contracts retained by #37.
4. Historical specifications, amendments, ADRs, and superseded issues for rationale only where compatible.
5. Root `CONTEXT.md` for stable vocabulary and these task-specific guides.

The 2026-09-05 simplification replaces mandatory execution of the old V2A–V2J graph. #39–#47 and #57–#112 are historical planning records; their retained ready/blocker/cutover wording does not authorize work. Completed #38 and #49–#56 retain their accepted history. A planning closure is not an implementation acceptance.

Shipped behavior remains v1.3 until a qualified explicit cutover. Establish active behavior from affected code, current gates, and evidence, not from target-spec language or issue counts.

## Rolling implementation gate

Implement a feature slice only when it is open, listed in #37's current queue, labeled `ready-for-agent`, and actually unblocked with required inputs available. Read its body and comments before claiming it. Only the next few executable slices receive that label; roadmap outcomes, missing-data work, and conditional research do not.

Keep a slice small and demonstrable through a real consumer. Internal TDD steps are not automatically separate issues. A blocked slice does not authorize reviving an old dependency graph or silently inventing fixtures, policies, or product behavior. State the concrete blocker and continue independent authorized work.

Documentation, investigation, and expressly authorized maintenance do not need a new feature ticket. Follow [GitHub workflow](issue-tracker.md) for tracker writes and claims.

## Scope discipline

Preserve input identity, complete occlusion, unknown-versus-background semantics, seed-external discovery, atomic replacement, bounded work, late-result refusal, and explicit Native application. Preserve the accepted Candidate consent and Q11 interaction behavior.

S1, sophisticated Reliability, iterative feedback, LOO, and elaborate Debt/hysteresis are conditional mechanisms, not a mandatory bundle. A new mechanism needs a concrete failure case and a minimal comparison showing value. Uniform-weight single-pass diagnostics remain a development/shadow baseline, not a production Candidate or a fake converged solver.

Do not restore full hash-chain journals, generic resource-accounting frameworks, or cross-restart exact-run replay as default prerequisites. Simplification is not permission to weaken real protocol validation or existing accepted tensor-integrity proof.
