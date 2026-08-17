# ADR 0019: Promote the Direct Evidence Candidate and bind production identity

Status: accepted

Date: 2026-08-17

## Context

Ticket 20 established production same-decision Direct Evidence, but Candidate
Re-Lift still ran a second complete-Contributor reference path and published a
reference-only Candidate. Readiness exposed the renderer, SAM adapter and
Evidence capabilities separately, so a browser could not prove that one
Candidate joined the exact calibrated Prompt, geometry, Mask Review, Evidence
and Lift Readiness policies accepted by the current release.

Execution attempts also need bounded replay records that survive a later
attempt long enough to recover a lost response without letting target disposal
retain stale publication authority.

## Decision

1. Current Candidate Re-Lift consumes only exact current per-View
   `production-direct` Evidence and atomically publishes a
   `production-ready` Candidate plus separate Uncertain IDs.
2. Complete-Contributor Candidate construction remains explicitly
   reference-only for diagnostics and Ticket 22 migration. It is not a
   production fallback.
3. The Runtime Profile publishes one checksum-bound production identity that
   joins authoritative renderer/runtime, the active SAM 3 Image Model
   Manifest, Prompt compiler/synthesis, TargetGeometryHint/local-View, Mask
   Review, Direct Evidence/aggregation and Lift Readiness identities.
4. The browser validates both the record checksum and every known policy,
   backend, model and runtime binding before reporting Available or allowing
   native Candidate application.
5. Direct Evidence, Prompt synthesis and Candidate Re-Lift retain bounded
   attempt admissions. Same-attempt replay returns the recorded complete
   success or failure; conflicting reuse fails closed. Exact target disposal
   removes only that target's replay authority, late completion publishes
   nothing, and delayed/foreign cleanup cannot erase a newer target.
6. The calibrated Lift Readiness identity is
   `lift-readiness/production-v1`. Mask Review remains a separate policy and
   Ticket 10 remains optional.

## Consequences

- Native Candidate application is available in ordinary production mode only
  for exact current production identity.
- Failed Evidence/Lift replacement preserves Views, Stable Masks and the prior
  inspectable Candidate.
- A changed policy or runtime rotates the production identity and invalidates
  incompatible publication/application without relabeling valid RGB as failed.
- No backend registry, automatic fallback, Prompt family, tracker or product
  retry control is introduced.
- Ticket 22 may contract the retained reference/legacy paths only after this
  production path remains green under the final regression.
