# V2J — Acquisition UI + Expert Recovery

Status: **review-required — accepted product direction, not agent-ready**

Blocked by: V2H, V2I  
Blocks: none

## Authority

- Final Spec v2.0 Amendment 001;
- ADR 0022;
- Final Spec v2.0 §10 where not amended;
- ADR 0020 for Candidate auto-publication presentation.

## Goal

Present the minimal automatic-acquisition status surface and a secondary Expert Recovery workflow without reviving persistent planning controls.

## Product behavior

### While acquisition runs

- Show current phase, View progress, readiness, and terminal reason when available.
- Provide a dedicated Cancel.
- Do not expose Add Observation, Continue Acquisition, Generate More, camera planning, or live utility/coverage dashboards.

### After acquisition stops

When the target remains active, Expert Recovery may provide:

1. **Add Observation / Use Current View** — create a User-added View from the current Editor Camera;
2. **Continue Acquisition** — start a fresh bounded automatic attempt from exact current stable artifacts.

The recovery surface is secondary and may be available after successful Ready, Limited/Not Ready, budget/no-feasible/stage-failure terminals, or Cancel. Exact eligibility and labels remain review items.

## Required invariants

- User-added View uses authoritative RGB and the existing single-result/manual Mask path.
- It contributes only after Stable Mask publication and Included Participation.
- User Confirmed/manual Stable Masks retain reliability exemption.
- A new stable observation stales the prior Candidate; the prior Candidate stays inspectable but cannot be applied.
- Recovery never patches Candidate membership or Native Selection directly.
- Continue Acquisition creates a new loop attempt; it is not replay or identical-input retry.
- Suspended targets cannot recover until exact dependency compatibility is restored.
- Persistent Stop/Generate More/Regenerate controls remain absent.

## Review gates before decomposition

- availability matrix by terminal state;
- exact wording and placement of Expert Recovery actions;
- continuation budget/reset policy;
- relationship among Add Observation, Re-Lift, and Continue Acquisition;
- stale Candidate presentation;
- behavior when a Ready Candidate already exists;
- accessibility and responsive layout;
- migration of existing User-added View commands/APIs without duplicate control ownership.

## Validation families

- UI state tests for running, cancelled, Ready, Limited, Not Ready, failure, stale, and Suspended states;
- User-added View end-to-end identity tests;
- Candidate staleness and application blocking tests;
- fresh continuation-attempt tests;
- operator visual walkthrough at approximately 1280×720 and 1024×720;
- repository test/lint/locales/build gates.

## Non-goals

- no user-authored trajectory;
- no camera intervention during a running loop;
- no live default utility dashboard;
- no Candidate provenance browser;
- no automatic Native operation.
