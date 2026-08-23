# AI Select Domain Authority

Read this file for AI Select behavior, terminology, scope, or current authority.

## Authority order

1. Final Spec v2.0 Amendments 009→001 and the unamended v2.0 baseline, preserved through the immutable links in [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37).
2. #37 for current decision status, dependency frontier, implementation gates, and cutover state.
3. The relevant parent capability Issue #38–#47 and any exact child stage Issue; an explicitly accepted decision comment may refine that Issue without silently rewriting history.
4. Non-conflicting historical ADR decisions referenced by those Issues at migration snapshot [`aacad57`](https://github.com/Wormh0-le/supersimplat/tree/aacad57fc534acc43522ca4d51d41149b5ee9692).
5. Root `CONTEXT.md` for stable vocabulary where it does not conflict with #37 or the relevant current Issue.
6. Affected code, tests, runtime locks, and benchmark evidence.

The shipped runtime remains implemented v1.3 until an explicit reviewed cutover. Parent Issues #38–#47 are not implementation-ready. Root `CONTEXT.md` still contains historical v2 draft passages pending controlled consolidation; where they conflict with accepted Amendments or current Issues, the authority order above wins.

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
