# V2J — Progressive acquisition UI + Expert Recovery

Status: **review-required parent envelope — current review frontier; not agent-ready**

Blocked by: V2H, V2I  
Blocks: none

## Authority

Final Spec Amendments 001, 008, and 009; ADRs 0022, 0029, and 0030; existing AI Select Dock/toolbar/status patterns.

## Goal

Present automatic acquisition, Candidate publication/consent, and secondary Expert Recovery with progressive disclosure. Preserve a canvas-first selection workflow without exposing persistent planner management or internal algorithm dashboards.

## Accepted behavior from earlier reviews

### While acquisition runs

- show current phase/progress and a dedicated Cancel;
- keep any prior Candidate inspectable;
- temporarily disable Set/Add/Remove/Intersect from the AI Candidate;
- do not expose Add Observation, Continue Acquisition, or camera management;
- do not display live Utility/Coverage/Frontier internals by default.

### At terminal

- eligible Ready-low-gain Candidate appears automatically;
- forced-terminal Ready may offer `Use Ready Candidate`;
- eligible Limited may offer `Use Limited Candidate`;
- Not Ready or publication-ineligible results offer no Candidate-use action;
- stale/scope-advanced/non-converged/Suspended reasons remain explicit;
- prior Candidate remains inspectable and current/stale/application-blocked states are distinct.

### Expert Recovery

When no Attempt runs and the target is active, secondary recovery may include:

- Add Observation / Use Current View;
- Continue Acquisition as a fresh bounded Attempt;
- Re-Lift after changed Stable inputs;
- Restart when the current target workflow should be discarded.

Recovery never patches Candidate or Native Selection directly.

## Q11 review gates

- progressive-disclosure hierarchy: primary action, secondary recovery menu, and advanced diagnostics;
- exact terminal-state action availability and priority;
- labels and descriptions for Use Ready, Use Limited, Continue, Add Observation, Re-Lift, Cancel, and Restart;
- prior Candidate current/stale/temporarily-blocked presentation;
- whether Expert Recovery appears inline, in an overflow menu, or in a dedicated terminal panel;
- status language for normal success, forced terminal, Limited, Not Ready, Cancel, stale, non-converged, and Suspended;
- accessibility, keyboard/focus, locale length, and 1024×720 / 1280×720 behavior;
- optional advanced diagnostics without a default live metrics dashboard.

## Validation families

State/action availability matrix; focus/keyboard/ARIA; locale expansion; responsive visual walkthrough; Candidate application blocking; explicit Ready/Limited consent; Add Observation and Continue identity; stale/prior Candidate; full repository test/lint/locales/build gates.

## Non-goals

No user-authored trajectory, camera intervention during a running Attempt, persistent Generate More/Regenerate controls, default algorithm dashboard, Candidate provenance browser, or automatic Native operation.