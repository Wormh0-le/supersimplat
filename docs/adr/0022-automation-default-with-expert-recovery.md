# ADR 0022: Keep automatic acquisition as the default and preserve expert recovery

Status: accepted  
Date: 2026-08-23

## Context

Final Spec v2.0 initially removed User-added View and left post-loop continuation unset. That produces a simple automatic happy path, but it also removes the strongest recovery mechanism for a professional editor: the operator may know exactly which missing angle would expose a handle, thin structure, occluded side, or identity ambiguity that the planner failed to acquire.

The product should not force every user to manage cameras, nor should it trap an expert in `Limited → Re-Lift → Restart` when a deliberate observation can resolve the problem.

## Decision

1. Adaptive Acquisition remains the default after Anchor confirmation. The running loop does not expose camera management or persistent Generate More controls.
2. Expert Recovery is available only while no loop is running and the target is active.
3. Expert Recovery retains User-added View as `Add Observation / Use Current View`, using authoritative RGB, Stable Mask, Participation, Direct Evidence, and current identity rules.
4. Expert Recovery adds `Continue Acquisition`, which starts a fresh bounded loop attempt from exact current stable artifacts. It is not same-attempt replay and not a persistent planning control.
5. New stable observations stale the prior Candidate; they never patch Candidate membership or Native Selection directly.
6. User Confirmed/manual Stable Masks retain authority and are exempt from automatic reliability downweighting.
7. The recovery surface is secondary/advanced. The normal product story remains `Anchor → automatic acquisition → Candidate → explicit Native application`.

## Consequences

- Final Spec v2.0 is amended rather than silently rewritten.
- The v1.3 User-added View implementation remains a migration asset and must not be deleted by V2J.
- V2J changes from capability removal to acquisition UI plus Expert Recovery.
- V2G/V2I/V2J must define continuation eligibility, budget reset, identity hierarchy, and stop-state presentation before becoming agent-ready.
- The product preserves simplicity for ordinary users while retaining a high-leverage escape hatch for difficult scenes.
- Additional recovery states increase lifecycle and UI testing scope.

## Rejected alternatives

### Fully automatic with no expert camera input

Rejected because planner failure can leave no way to add missing geometric evidence without restarting the target.

### Always-visible camera planning controls

Rejected because they turn the product back into a view-management workflow and burden the normal happy path.

### Allow user intervention during a running loop

Deferred. The user cancels first, then enters Expert Recovery. This keeps attempt identity and progressive publication boundaries tractable.

## Supersession

This ADR is implemented by Final Spec v2.0 Amendment 001 and supersedes only the v2.0 decision to remove User-added View and leave post-loop continuation unset. ADR 0020, ADR 0021, and the carried-over v1.3 safety boundaries otherwise remain current.
