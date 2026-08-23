# V2J — Acquisition UI + Expert Recovery

Status: **review-required — product direction accepted; awaits Q10 publication matrix; not agent-ready**

Blocked by: V2H, V2I

## Goal

Present minimal automatic-acquisition state and secondary Expert Recovery without exposing persistent camera planning.

## Accepted lifecycle inputs

- running UI binds one Acquisition Series/Attempt and current Iteration phase;
- Cancel terminates the current Attempt and rejects late publication;
- Add Observation is available only after termination and creates a normal User-added View;
- Continue Acquisition creates a fresh Attempt, resets per-Attempt allowances, and preserves Series cumulative caps/current artifacts;
- Continue is not replay, resume, retry, or Generate More;
- Suspended/stale targets must satisfy exact compatibility or recovery rules before new work;
- new Stable observations/scope inputs apply existing Candidate stale rules.

## Remaining review gates

- Q10-dependent availability and wording for Ready/Limited/Not Ready and each terminal outcome;
- `Use Limited Candidate` versus Re-Lift labels and consent;
- whether a prior current Candidate remains applicable while a new Attempt is running;
- progress/budget presentation without exposing debug accounting;
- stale Candidate presentation, accessibility, responsive layout, and migration of existing User-added View actions.

## Validation families

Running/cancelled/suspended/stale/terminal UI; fresh Continue Attempt and Series-cap display; User-added View identity; Candidate stale/application blocking; 1280×720 and 1024×720 walkthroughs; tests/lint/locales/build.
