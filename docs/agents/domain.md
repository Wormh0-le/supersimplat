# AI Select Domain Authority

Read this file for AI Select behavior, terminology, scope, or current authority.

## Authority order

1. Final Spec v2.0 Amendments 009→001 and the unamended v2.0 baseline, preserved through the immutable links in [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37).
2. #37 for current decision status, dependency frontier, implementation gates, and cutover state.
3. The relevant parent capability Issue #38–#47 and any exact child stage Issue; an explicitly accepted decision comment may refine that Issue without silently rewriting history.
4. Non-conflicting historical ADR decisions referenced by those Issues at migration snapshot [`504e888`](https://github.com/Wormh0-le/supersimplat/tree/504e8885b87575761dc2e367e520b7dfba46884b).
5. Root `CONTEXT.md` for stable vocabulary where it does not conflict with #37 or the relevant current Issue.
6. Affected code, tests, runtime locks, and benchmark evidence.

The production baseline remains v1.3 until each explicit qualified v2 cutover. Establish which stages have landed and which gates are active from current Issues and affected code; a target specification does not establish shipped behavior. Where historical draft passages in `CONTEXT.md` conflict with accepted Amendments or current Issues, the authority order above wins.

## Implementation gate

Before implementing a v2 stage, read #37, the relevant parent map, and the exact child Issue, including comments, dependencies, migration boundary, and validation contract. Implement only an open child linked from #37, labeled `ready-for-agent`, and eligible at the current frontier with its blockers closed or explicitly resolved by accepted authority.

`ready-for-agent` describes contract completeness, not dependency readiness. Parent Issues #38–#47 are capability maps even when they carry that label; execute their eligible child stages. Follow [GitHub workflow](issue-tracker.md) for claiming and closing work. If the gate is unmet or authority conflicts, identify the specific blocker and continue independent authorized work.

## Stable domain model

- Automatic bounded acquisition is the default; terminal or paused Expert Recovery retains Add Observation and Continue Acquisition.
- Seed is a prior; Core, seed-independent Discovery Envelope, reversible component Frontier, and Context are distinct.
- q/s Consensus is deterministic, bounded, regional, and non-executable.
- View Utility uses a finite layered pool and a hybrid prospective probe; only the selected winner receives formal acquisition.
- Browser owns Acquisition Series/Attempt/Iteration state, Decision Journal, and deterministic budgets.
- Candidate publication uses two gates: exact Publication Eligibility plus Readiness/terminal/consent class.
- Only eligible Ready-low-gain normal success auto-publishes; eligible forced Ready and Limited require explicit state-specific actions.
- Re-Lift recomputes exact current Stable inputs and is not an alias for accepting an existing terminal snapshot.
- A running Attempt may block Candidate application without making the prior Candidate stale.
- Candidate and Native Selection remain separate; Candidate never self-applies.
- Evidence/Workflow, Spatial Authoring, and Selection Application are responsibility layers inside one continuous editor workspace.
