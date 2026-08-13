# Ticket 14C reference aggregation policy comparison

Run date: 2026-08-13

This is a deterministic CPU reference stress fixture for aggregation policy
behavior. It is not a scene-quality calibration result and does not exercise
Ticket 20 production same-decision GPU Evidence.

The fixture gives one Gaussian two valid Included View artifacts:

| View              | Positive P | Negative N | Visible V |
| ----------------- | ---------: | ---------: | --------: |
| close / high-mass |        100 |          0 |       100 |
| context           |          0 |          1 |         1 |

The executable fixture is
`ReferenceGaussianEvidenceAggregationTests.test_per_view_cap_exposes_and_limits_close_view_dominance`.
It was run with:

```sh
uv run --project selection-service-companion --locked --python 3.12 \
  python -m unittest \
  selection-service-companion/tests/test_reference_gaussian_evidence_aggregation.py
```

## Recorded result

| Policy                         | Effective P | Effective N | Effective V | Close-View scale | Close-View share of effective V |
| ------------------------------ | ----------: | ----------: | ----------: | ---------------: | ------------------------------: |
| `raw-mass-sum/v1`              |         100 |           1 |         101 |                1 |                          99.01% |
| `per-view-visible-mass-cap/v1` |           1 |           1 |           2 |             0.01 |                             50% |

The raw policy exposes the original mass dominance. The default capped policy
limits each View to Visible Mass 1.0 and applies the same scale to that View's
P, N and V, so it preserves within-View evidence proportions without allowing
the close/high-mass View to silently overwhelm the context View. Both policies
retain both per-View records and classify this deliberately contradictory
fixture as Uncertain due to conflicting View support.

This result establishes declared, replayable reference behavior only. Real
scene calibration, classification-quality gates and production GPU stability
remain later work.
