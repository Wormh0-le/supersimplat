# Ticket 14D locked-GPU reference Candidate quality record

Run date: 2026-08-13

This record exercises the verified locked Contributor reference backend on an
RTX 4090 D with Python 3.12.12, PyTorch 2.11.0+cu128, CUDA 12.8 and the pinned
gsplat source/runtime identity. It is a small deterministic synthetic scene,
not real-scene release calibration and not Ticket 20 production same-decision
Evidence.

The executable record is:

```sh
uv run --project selection-service-companion --locked --extra renderer --python 3.12 \
  python scripts/benchmarks/run_reference_candidate_quality.py
```

Its machine-readable output is
`docs/ai-select/benchmarks/14d-reference-candidate-quality.json`.

## What the fixture actually measures

- The locked gsplat complete-Contributor backend renders two Included Views.
- Ground-truth target Stable IDs generate the two Stable Masks.
- The resulting real Contributor P/N/V artifacts are aggregated and published
  as one reference Candidate.
- A third camera, which did not participate in Lift, renders both the Candidate
  and the known target IDs. Their pixel masks are compared for novel-view IoU.
- The second View is then excluded and the aggregate is rerun to check that it
  no longer contributes.

## Recorded Candidate metrics

| Metric                            | Value |
| --------------------------------- | ----: |
| Gaussian precision                | 1.000 |
| Gaussian recall                   | 1.000 |
| Novel-view rendered-mask IoU      | 1.000 |
| Background contamination          | 0.000 |
| Mixed ratio                       | 0.250 |
| User Add burden proxy             |     0 |
| User Remove burden proxy          |     0 |
| Single→multi false-positive delta |     0 |
| Single→multi false-negative delta |     0 |
| View exclusion correct            |  true |

Peak VRAM reported by the reference renderer was 8,855,552 bytes. Candidate
and ground-truth novel-view masks both contained 452 foreground pixels and had
the same digest.

Only the complete-Contributor reference producer is implemented end to end in
this repository. The JSON therefore records `reference-autograd` as unavailable
instead of fabricating a second artifact; the discrepancy list and
threshold-near/classification-difference counts are empty. If an independent
autograd producer is added later, the existing comparison contract will record
its per-channel errors and classification differences without threshold
retuning.

This closes the Ticket 14 reference-quality fixture at its declared scope.
Real-scene calibration, repeat-run production classification stability,
latency/VRAM/OOM release gates and production same-decision Evidence remain
Tickets 20/21 work.
