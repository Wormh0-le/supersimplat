# AI Select Final Spec v2.0 Amendment 001 — Automation-default, expert-recoverable acquisition

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** `docs/specs/ai-select-final-spec-v2.0.md`  
**Decision record:** `docs/adr/0022-automation-default-with-expert-recovery.md`

## 1. Purpose

Final Spec v2.0 made adaptive acquisition fully automatic after Anchor confirmation and removed User-added View. Product review accepted a different orientation:

> Automatic acquisition is the default path, while an expert can take over after the loop stops when additional or deliberately placed observation is useful.

This amendment changes only recovery and expert-control semantics. It does not weaken the automatic happy path or the Candidate/Native Selection safety boundary.

## 2. Superseded clauses

This amendment supersedes the following v2.0 clauses where they conflict:

- §0.1 item 4, which removed User-added View;
- §1 statements that User-added View no longer exists;
- §10 statements that Anchor is the only user-placed camera and that post-loop continuation is unset;
- V2J scope that deletes User-added View commands, APIs, locales, and tests.

All other Final Spec v2.0 clauses remain current.

## 3. Product orientation

### 3.1 Default path

After Anchor Stable Mask confirmation, the bounded utility-driven Acquisition Loop starts automatically. The normal path does not ask the user to choose View count, camera family, or next direction.

### 3.2 Expert Recovery

Expert Recovery is a secondary target-local surface available only when:

- the Acquisition Loop is not running;
- the Current Target Context is active rather than Suspended;
- the user explicitly opens or invokes a recovery/advanced action.

It may be used after any terminal result, including Ready, Limited, Not Ready, budget exhaustion, no-feasible-view, stage failure, or user Cancel.

Expert Recovery provides two distinct intents:

1. **Add Observation / Use Current View** — capture the current Editor Camera as a User-added View;
2. **Continue Acquisition** — start a fresh bounded Acquisition Loop attempt from the exact current stable artifacts.

Neither action is a persistent planning dashboard or a revival of `Generate More`.

## 4. User-added View contract

A User-added View:

- uses an explicit Editor-authored `CameraBinding`;
- renders authoritative gsplat RGB through the existing validated path;
- uses the current single-result SAM/manual Mask authoring workflow;
- becomes Evidence input only after Stable Mask publication and Included Participation;
- receives production Direct Evidence under the same identity and fail-closed rules as Generated Views;
- remains target-local and is disposed by Restart Current Target;
- never moves the Anchor or silently changes the automatic planner's prior decisions.

A User Confirmed or manually edited Stable Mask retains user authority and is exempt from automatic reliability downweighting, consistent with Final Spec v2.0 §7.2.

## 5. Continuation contract

`Continue Acquisition`:

- starts a new acquisition attempt with a new loop-level identity;
- consumes the exact current Views, Stable Masks, Participation, raw Evidence, consensus inputs, and current dependency/policy identities;
- does not replay or mutate the completed attempt;
- receives a fresh bounded budget under the reviewed continuation policy;
- does not automatically apply a Candidate or mutate Native Selection.

The exact continuation budget, eligibility by stop reason, and presentation label remain implementation-review items owned by the V2G/V2I/V2J review.

## 6. Candidate and correction behavior

Publishing or including a new Stable observation makes dependent Evidence/readiness current only after recomputation and makes any prior Candidate stale by existing identity rules. The prior Candidate remains inspectable but cannot be applied while stale.

The user may then:

- run explicit Re-Lift against the exact current Evidence; or
- choose Continue Acquisition before a later Candidate publication attempt.

Expert Recovery never patches Candidate membership directly and never bypasses Native Set/Add/Remove/Intersect.

## 7. UI constraints

- The automatic acquisition status remains the default visible workflow.
- Expert Recovery is secondary and absent while the loop is running.
- The dedicated running-loop Cancel remains.
- Persistent Stop, Generate More, Regenerate, and identical-input retry controls remain retired.
- Default UI still avoids live coverage/utility dashboards; diagnostics may expose them under the existing calibration policy.

## 8. Migration

The implemented v1.3 User-added View capability is retained as a migration foundation. V2J must adapt and reposition it as Expert Recovery rather than delete it. Obsolete deletion-oriented V2J documentation is removed or marked historical.

## 9. Non-goals

This amendment does not introduce:

- user-authored planner trajectories;
- camera-by-camera orchestration during a running loop;
- automatic Native Selection application;
- persistent target history;
- Candidate provenance or Gaussian Evidence inspection;
- an unbounded acquisition loop.
