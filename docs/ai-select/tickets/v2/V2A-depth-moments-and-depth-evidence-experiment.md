# V2A — Projected depth, CWED moments, and depth-Evidence experiment

Status: **reviewed parent envelope — awaiting stage decomposition; not agent-ready**

Blocked by: none  
Blocks: V2B's S1 shadow path  
Does not block: V2C, V2D, V2E

## Authority

- Final Spec v2.0 Amendment 002;
- ADR 0023;
- residual ADR 0021 for internal/same-decision depth readouts;
- current Direct Evidence and pinned gsplat runtime contracts.

## Repository-grounded facts

Pinned gsplat returns projected Gaussian depth in `meta["depths"]`, aligned with projected Gaussian rows. The current project-owned CUDA ABI consumes the other projection/intersection tensors but does not pass this depth tensor into `direct_evidence.cu`.

Current production Evidence remains `P/N/V` plus optional boundary diagnostics and one `negativeMass` channel.

## Goal

Provide a minimal same-decision depth-moment foundation for S1 Seed evaluation while keeping depth-classified Negative Evidence isolated as a nonblocking experiment.

## Reviewed stage intent

### V2A1 — Projected depth data path and CUDA ABI

- pass pinned `meta["depths"]` through the Python/C++/CUDA boundary;
- validate dtype, shape, device, finite values, row alignment, and render identity;
- rotate Direct Evidence ABI/source/runtime identity without changing current P/N/V semantics;
- cover reference fixtures and unsupported/mismatched input fail-closed behavior.

### V2A2 — CWED moments and dispersion

Inside the same accepted contribution loop, accumulate:

```text
M0 = Σw
M1 = Σwz
M2 = Σwz²
```

Derive CWED and depth variance only when `M0` passes the calibrated validity threshold. The moments remain Companion-internal and do not cross the Browser protocol.

### V2AX — Depth-aware Negative Evidence experiment

- compare optional front/near/behind or alternative depth relations as benchmark diagnostics;
- do not replace the production `negativeMass` schema;
- do not enter the Runtime Profile;
- do not block Consensus, Reliability, Aggregation, Utility, or orchestration;
- require a later explicit promotion decision if quality/cost gates pass.

## Reviewed acceptance decisions

- [x] Canonical term is Contribution-Weighted Expected Depth (CWED).
- [x] CWED is not first-hit or authoritative visible-surface depth.
- [x] Depth moments use the accepted `alpha × incoming T` contribution sequence.
- [x] Low-mass pixels are depth-invalid; high variance weakens depth influence.
- [x] No standalone depth protocol artifact is introduced.
- [x] Current single Negative Mass remains the production contract.
- [x] Classified N is an experimental sidecar, not a critical-path dependency.

## Validation families for later stages

- projected-row/depth alignment and fail-closed ABI tests;
- CUDA/reference moment parity;
- zero/low-mass and multi-layer variance fixtures;
- RGB/P/N/V unchanged with moment writes enabled;
- latency, registers, global writes, VRAM, OOM, and supported-GPU evidence;
- V2AX real-scene ablation against the unchanged single-N baseline.

## Non-goals

- No Conservative Seed construction (V2B).
- No consensus soft-mask implementation (V2C).
- No production Evidence schema migration for classified N.
- No Browser depth artifact or new visibility authority.
