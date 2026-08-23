# ADR 0025: Adopt multi-channel consensus readout and leave-one-out reference benchmarking

Status: accepted 2026-08-23

Date: 2026-08-23

## Context

ADR 0024 adopted continuous q+s consensus with lagged Reliability, but a single soft foreground image cannot distinguish unknown support, high-support conflict, Core support, and newly revealed Frontier support. Whole-frame BCE would also let far background, resolution, and boundary pixels dominate a view-level reliability score.

Leave-one-out consensus is statistically cleaner because one View cannot support its own reliability estimate, but its repeated solves/readouts are expensive for an interactive multi-million-Gaussian product.

## Decision

1. The production baseline uses a multi-channel, same-decision Companion-internal readout over frozen Core, Frontier, and Context scope.
2. Support-aware membership is `q̃ = 0.5 + s(q - 0.5)`.
3. The readout accumulates semantic-scope mass, soft foreground mass, knownness mass, Core mass, and Frontier mass from the authoritative accepted `alpha × T` sequence.
4. Reliability reuses Strong Positive Interior, Local Negative Context Ring, Boundary Band, and Far Neutral region semantics.
5. Positive-interior residual receives bounded asymmetric Frontier/unknown protection. Negative-ring conflict does not receive a symmetric exemption.
6. Region residuals are normalized separately before forming one view-level residual. Far Neutral is excluded.
7. Insufficient trusted comparison support produces neutral reliability with a diagnostic reason, never an automatic penalty.
8. User Confirmed/manual Stable Masks remain exempt from automatic downweighting.
9. Leave-one-out consensus is a nonblocking offline/reference benchmark, not the production path.

## Consequences

- V2C must own the same-decision multi-channel readout and its GPU/reference identity.
- V2D must own trusted regional residuals, Frontier protection, robust view-level normalization, and the leave-one-out reference benchmark.
- V2E continues to weight semantic P/N only; raw V remains unchanged.
- The production path gains more channels and policy complexity, so register/global-write cost, VRAM, latency, and parity require explicit gates.
- Self-influence is measured rather than assumed harmless. A later ADR may promote a leave-one-out or influence-corrected method only if benchmark evidence justifies its cost.

## Rejected alternatives

- one soft foreground mask plus whole-frame BCE;
- production leave-one-out as the initial canonical path;
- treating low semantic-scope mass as background disagreement;
- symmetric Frontier protection for both positive and negative supervision;
- exposing readout maps as Browser product artifacts.
