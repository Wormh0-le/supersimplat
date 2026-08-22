# V2D — Observation Reliability

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2A, V2C
Blocks: V2E

## Final Spec v2.0 mapping

- Final Spec v2.0 §7.2, §5 (consumes depth-classified N);
  `CONTEXT.md` non-normative "Observation Reliability"

## Goal

Compute versioned view-level Observation Reliability weights from the residual
between the consensus soft mask and each View's Stable Mask, scoped strictly to
P/N semantic mass, with the adopted anti-self-confirmation guardrails.

## Inputs / preconditions

- V2C consensus soft-mask readout under the View's CameraBinding;
- V2A depth-classified N;
- Stable Mask identity + User Confirmed / manual-edit provenance flags;
- visibility/transmittance trust information from the same-decision raster.

## Outputs / handoff

- Versioned view-level reliability weight per Included observation;
- residual record per View: visibility-gated pixel BCE (trusted-transmittance
  pixels only) + separate boundary-band component; IoU diagnostic-only;
- guardrail implementation with calibration-parameterized parameters:
  lagged consensus (revision-k weights from consensus k−1), warm-up uniform
  weights, non-zero `r_min` floor, frontier protection for newly seen
  foreground, stronger penalty for contradiction in well-observed
  high-confidence regions, maximum-revisions cap;
- policy identity `reliability-weight-policy/experimental-v*`.

## Acceptance criteria

- [ ] Weights apply ONLY to P/N semantic mass; raw V stays unweighted and
      faithful for realized Observation Coverage; Mask distrust never becomes
      "not observed".
- [ ] Residual = visibility-gated BCE + independent boundary-band term;
      IoU appears in diagnostics only, never in weight computation.
- [ ] Weight scope is view level; region/per-pixel scope is out of scope.
- [ ] Reliability never silently modifies a Stable Mask, never equals
      Participation, and never alone triggers Excluded.
- [ ] Low-weight Views remain inspectable and carry concrete residual/reason.
- [ ] User Confirmed / manually edited Stable Masks are exempt from automatic
      downweighting; Review-state Views follow standard reliability.
- [ ] All guardrail parameters are named calibration inputs (spec §12),
      structurally enforced (e.g. `r_min > 0`, finite max revisions).
- [ ] Policy runs under `experimental-v*`; promotion by explicit key change.

## Validation

- Companion residual-computation tests (gated pixels, boundary band);
- exemption tests (User Confirmed, manual edit);
- lagged-consensus ordering test (weights never see same-round consensus);
- r_min/floor and max-revisions enforcement tests.

## Non-goals

- No aggregation change (V2E); no readiness policy change; no Stable Mask
  mutation; no region/per-pixel weights.
