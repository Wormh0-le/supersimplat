# 10 — Optional Cross-view Evidence Consistency Diagnostics

Status: planned optional enhancement — not a core release blocker

Blocked by: 14, 09, 07

Blocks: none

## Final Spec mapping

- Final Spec v1.3 §§14, 20–21, 24–26
- ADR 0013
- ADR 0016

## Purpose

Add optional cross-view diagnostics after exact per-View P/N/V Evidence exists. This ticket may identify material conflict between Included Stable Views, but it does not own per-View Mask Review or Lift Readiness.

## Inputs

- current Included Stable View Annotations;
- exact per-View P/N/V/visibility artifacts from Ticket 14;
- current CameraBinding and Stable Mask identities;
- Gallery/Review presentation seams;
- versioned cross-view diagnostic policy.

## Outputs

- optional `cross-view-evidence-conflict` diagnostics;
- supporting/conflicting View references;
- actionable inspection suggestions;
- no automatic Mask, Participation, Evidence or Candidate mutation.

## Ownership boundaries

Ticket 10 may answer:

```text
Do current Included Views provide materially conflicting target evidence?
```

It must not answer:

```text
Is this single 2D Mask geometrically usable?       → Ticket 07
Is Gaussian visibility/coverage sufficient to Lift? → Ticket 13
Which Gaussian is owned by the target?              → Tickets 14/20
```

`low-visible-support` and `weak-gaussian-support` are not Ticket 10 Review reasons. Visibility sufficiency, coverage and Not Ready / Limited / Ready remain Ticket 13 authority.

## Required behavior

- diagnostics consume exact Stable-Mask-bound P/N/V and policy identities;
- material conflict is derived from versioned support/conflict logic, not raw 2D Mask area;
- missing or stale Evidence produces no fabricated reason;
- optional diagnostics never revoke User Confirmed authority;
- diagnostics never trigger Mask refresh, re-inference, Participation change, Re-Lift or Candidate mutation;
- backend route, tracker confidence and Multiplex state are absent from the current contract;
- absence of Ticket 10 output does not block Ticket 13 readiness or Ticket 21 core release closure.

## Acceptance criteria

- [ ] cross-view conflict binds exact per-View Evidence and Stable Mask identities.
- [ ] missing/stale Evidence yields no diagnostic.
- [ ] weak/low visibility remains Ticket 13 Lift Readiness, not Ticket 10.
- [ ] no current backend/tracker terminology enters the artifact or UI.
- [ ] User Confirmed Stable state is never silently downgraded.
- [ ] Ticket 10 failure leaves Mask Review, Participation, Evidence, readiness and Candidate unchanged.
- [ ] core v1 release can close without this optional enhancement.

## Validation

- P/N/V conflict fixtures;
- missing/stale Evidence fixtures;
- no-low-support-reason ownership regression;
- no-mutation failure fixtures;
- optional-feature absence release walkthrough;
- repository test/lint/build.

## Non-goals

- No per-View MaskReviewPolicy.
- No Lift Readiness or coverage classification.
- No semantic identity-drift detector.
- No Mask acquisition backend or tracker logic.
- No production Direct Evidence kernel.
