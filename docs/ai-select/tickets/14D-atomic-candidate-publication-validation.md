# 14D — Atomic Candidate Publication & Reference Validation

Status: ready-for-agent — execution stage of parent Ticket 14

Blocked by: none (14C implemented)

Blocks: 13

## Current Final Spec mapping

- Parent Ticket 14
- Final Spec v1.3 §§20–22, 24–25
- ADR 0013

Final Spec v1.3 and parent Ticket 14 remain authoritative.

## Goal

Atomically publish the reference Candidate/Uncertain result with exact stale/current identity and close the parent Ticket 14 reference quality gate without introducing a second Candidate editing or provenance-inspection product surface.

## Inputs / preconditions

- current 14C aggregate classification;
- exact target/context/dependency identity;
- aggregation/Evidence policy identities;
- reference raster/backend/runtime identities.

## Outputs / handoff

- atomic reference Candidate containing Selected Stable Gaussian IDs only;
- Uncertain diagnostic set;
- bound Candidate identity sufficient for current/stale determination;
- minimal Candidate/Uncertain overlay state compatible with existing AI Select UI;
- parent Ticket 14 reference comparison/quality record for downstream Ticket 13 and later Ticket 20/21 work.

## Acceptance criteria

- [ ] Candidate publication is atomic; a failed replacement never destroys the previous inspectable Candidate.
- [ ] Candidate contains Selected only and keeps Uncertain separate.
- [ ] Candidate binds target/context/dependency, Stable input set, Evidence/aggregation policy, raster implementation, reference backend and runtime identity.
- [ ] Publishing a new Stable upstream input or changing Participation makes Candidate stale and requires explicit Re-Lift.
- [ ] Stale Candidate remains inspectable but cannot be treated as current/applicable.
- [ ] Candidate publication never mutates Native Selection or Native EditHistory.
- [ ] Reference Candidate is explicitly marked pre-production until Tickets 20/21 close.
- [ ] Minimal Candidate/Uncertain visualization reuses existing overlay/product seams and does not create a Candidate provenance browser or Gaussian Evidence inspector.
- [ ] Parent Ticket 14 fixtures report Gaussian precision/recall, novel-view rendered-mask IoU, background contamination, mixed ratio, user Add/Remove burden proxy, single-vs-multi-view effect and View-exclusion correctness where fixtures support those metrics.
- [ ] Reference backend discrepancies and threshold-near classification differences are recorded rather than hidden.
- [ ] Successful 14D closure makes parent Ticket 14 complete and makes Ticket 13 eligible subject to its other implemented prerequisites.

## Failure / recovery

- Lift/publication failure preserves Views, Stable Masks, Participation, per-view Evidence and previous Candidate.
- Stale or incompatible aggregate identity fails closed.
- No partial Candidate/Uncertain replacement becomes current.

## Validation

- atomic publication / failed replacement tests;
- stale/current Candidate identity tests;
- upstream Stable Mask and Participation invalidation tests;
- no Native Selection mutation test;
- Candidate Selected-only / Uncertain-separate test;
- reference quality fixture suite from parent Ticket 14;
- `npm test`;
- `npm run test:companion`;
- `npm run lint`;
- `npm run build`.

## Non-goals

- No Native Set/Add/Remove/Intersect; Ticket 16 owns native application.
- No Candidate provenance/source inspector.
- No Gaussian-level Evidence inspector.
- No direct 3D Candidate patch/edit system.
- No production same-decision CUDA Evidence claim; Ticket 20 owns it.
- No release hardening/calibration closure; Ticket 21 owns it.
