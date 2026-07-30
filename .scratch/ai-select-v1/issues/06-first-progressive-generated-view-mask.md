# 06 — Progressive Generated RGB + Legacy Mask Baseline Isolation

Status: implemented tracer bullet — current Mask path is superseded by Tickets 04C and 08B

Blocked by: 05

Blocks: 07

## Current normative mapping

- Final Spec v1.3 §§5, 13–16, 24–26
- ADR 0016

## Retained implementation outcome

Ticket 06 proved the progressive Generated View lifecycle:

```text
planned CameraBinding
→ authoritative gsplat RGB
→ publish RGB-ready AIView immediately
→ independent Mask work
→ independent Evidence state
```

The following remain current:

- stable `viewId` and exact CameraBinding/RGB identity;
- RGB Ready independent from Mask and Evidence;
- Generated frustum derived from the exact CameraBinding;
- progressive publication without moving Editor Camera;
- Render failure distinct from Mask failure;
- late/stale result rejection;
- completed Views retained across later failures;
- Stable Mask publication dirties Evidence but does not automatically Lift.

## Superseded Mask baseline

The implemented Ticket 06 Mask route used projected Anchor support and one independent single-frame pass through the then-current Multiplex-derived adapter. It also coupled the provider response to automatic assessment/publication.

Under Final Spec v1.3 this path is a legacy migration fixture only. It is not:

- a current production Mask provider;
- Route A or an automatic fallback;
- a valid source of current `generated-view-mask/v1` artifacts;
- evidence that SAM 3.1 Multiplex is appropriate for static segmentation;
- a current Prompt synthesis or Mask Review contract.

Tickets 04C and 08B replace it with:

```text
SAM 3 Image instance adapter
+ current Point/Positive-Box contract
+ TargetGeometryHint-guided per-View Prompt
+ single-mask inference
+ separate MaskReviewPolicy/publication
```

## Current acceptance criteria

- [x] Generated AIView publishes as soon as authoritative RGB is ready.
- [x] RGB, Mask and Evidence states remain independent.
- [x] Render and Mask failure remain distinct.
- [x] completed View/RGB/frustum state survives later failure.
- [x] stale results are rejected.
- [ ] legacy `generated-view-mask/v1`, propagated source and provider-returned assessment are rejected by the current 08B migration.
- [ ] no current production call reaches the Ticket 06 Multiplex-derived Mask implementation.

## Failure and recovery

- RGB failure preserves a failed View record and offers true Retry.
- Legacy Mask failure preserves View/RGB and cannot publish a current Stable Mask.
- User Confirmed Stable Masks remain authoritative through migration.

## Historical implementation record

The previous fixed-pair planner and projected-support Mask implementation remain available in repository history and tests only as migration/regression inputs. Former DG-24 language describing this route as a production fallback is superseded and non-normative.

## Non-goals

- No current SAM adapter implementation.
- No current local Key-View planner.
- No automatic route fallback.
- No formal P/N/V Evidence.
