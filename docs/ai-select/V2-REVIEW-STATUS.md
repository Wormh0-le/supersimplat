# AI Select v2.0 Pre-implementation Review Status

Status: **parent-envelope review complete — decomposition gate active; no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendments 001–002: Expert Recovery, Seed/depth staging, seed-independent discovery.
- Amendments 003–006: deterministic q+s recurrence, regional Reliability, pseudo-mass/convergence, component Scope/Frontier Debt.
- Amendment 007: layered candidates + geometric pruning + shortlist ViewUtilityProbe.
- Amendment 008 / ADR 0029: hierarchical identities, Browser Decision Journal, deterministic budgets, exact replay/retry, Cancel/Suspend, and fresh Continue Attempt.
- Amendment 009 / ADR 0030: Publication Eligibility plus Readiness/terminal/consent matrix, explicit Ready/Limited actions, Re-Lift separation, and running-attempt Candidate application gate.
- Q11 / V2J: compact Session Strip, progressive-disclosure ownership, one-click safe auto-pause before authoritative editing, viewport-owned spatial authoring, read-only Spatial Edit HUD, existing Navigator/frustum and live-manipulation regression guards, and stable-boundary Dock publication.

## Review order

| Step | Area | Status |
|---|---|---|
| 0–2.4 | control plane through Scope Delta/Frontier Debt | complete |
| 3 | V2F hybrid View Utility | complete at parent-decision level |
| 4 | V2G/V2I identity, budgets, Journal, replay, continuation | complete at parent-decision level |
| 5 | V2H terminal publication | complete at parent-decision level |
| 6 | V2J UI + Expert Recovery presentation | complete at parent-decision level |
| 7 | parent-ticket decomposition | **next** |
| 8 | calibration/promotion/release ownership | pending |

## Current frontier

```text
next review item          = parent-ticket decomposition
reviewed parent direction = V2A–V2J
accepted cross-ticket     = Q4-B through Q11
agent-ready stages        = none
ticket in flight          = none
```

## Q10 invariants

- Publication requires an exact current converged scope-stable snapshot and complete production identity.
- Only `Ready + ready-low-gain` auto-publishes.
- Eligible forced-terminal Ready requires `Use Ready Candidate`.
- Eligible Limited requires `Use Limited Candidate`.
- Not Ready, scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, and late results cannot publish.
- Cancel never auto-publishes; a committed eligible pre-Cancel snapshot may be explicitly used afterward through a new Candidate Publication Attempt.
- Re-Lift recomputes and is not an alias for accepting an existing snapshot.
- Running acquisition temporarily blocks AI Candidate application but does not itself stale the prior Candidate.
- Candidate never self-applies Native Selection.

## Q11 invariants

- Evidence/Workflow, Spatial Authoring, and Selection Application are responsibility layers inside one continuous editor workspace, not three new surfaces.
- The Dock restores one compact Session Strip with at most one lifecycle/publication action; it never duplicates spatial commands.
- Passive inspection never pauses. Authoritative Mask/Anchor/Observation editing queues one safe pause and enters the requested mode after acknowledgement without a second click.
- Return to Scene View and Cancel adjustment never resume acquisition implicitly. Compatible resume and changed-input Continue remain explicit and identity-correct.
- Anchor/View authoring stays in the main 3D toolbar. Spatial Edit HUD is read-only feedback.
- Existing continuous frustum manipulation and Navigator ↔ frustum ↔ Dock linkage are regression baselines.
- Draft motion does not replace Dock Evidence. Staged Anchor and completed Observation results publish only at stable identity boundaries.
- A prior Candidate remains inspectable but application-blocked while acquisition runs; Ready/Limited consent and Native application remain separate.

## Known blockers

1. Every reviewed parent envelope still requires small TDD stage decomposition; no parent ticket may be implemented directly.
2. V2J decomposition must assign separate owners for Session Strip projection, auto-pause handoff, spatial HUD/toolbar state, stable Evidence publication, Candidate terminal presentation, and visual/accessibility regressions.
3. Numeric budget/cost/quality/Scope thresholds and GPU performance budgets need calibration owners.
4. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph owners.
5. Context Amendments 001–009 require one controlled glossary consolidation before v2 closeout.
