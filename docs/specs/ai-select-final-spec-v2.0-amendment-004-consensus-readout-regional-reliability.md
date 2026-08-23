# AI Select Final Spec v2.0 Amendment 004 — Same-decision consensus readout and regional Reliability

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–003  
**Decision record:** `docs/adr/0025-adopt-multichannel-consensus-readout-and-loo-reference.md`

## 1. Purpose

Amendment 003 adopted continuous `q+s` consensus and a deterministic bounded recurrence, but left the per-View readout and Observation Reliability residual undefined. This amendment adopts:

- a multi-channel same-decision Consensus Readout for the production baseline;
- trusted, asymmetric, region-normalized residuals for view-level Reliability;
- leave-one-out consensus only as a nonblocking offline reference benchmark.

The readout and residual remain Companion-local derived computation. They do not create observation, ownership, Candidate, or Native Selection authority.

## 2. Clarified clauses

This amendment clarifies Final Spec v2.0 §§5 and 7.1–7.3, Amendment 003, and the V2C/V2D/V2E parent envelopes.

Amendments 001–003 remain current. Runtime behavior remains the implemented v1.3 baseline until reviewed implementation stages are calibrated and explicitly promoted.

## 3. Frozen semantic scope

One Solver Iteration consumes the frozen scope revision from Amendment 003. The semantic readout scope is:

```text
Core ∪ Discovery Frontier ∪ Context
```

Out-of-Scope and render-only Gaussians do not contribute semantic moments. They still participate in the authoritative front-to-back raster chain and therefore continue to affect occlusion, incoming transmittance, accepted contribution weights, and termination.

No semantic scope member is Candidate membership merely because it participates in the readout.

## 4. Support-aware membership

For Gaussian `i`, the readout consumes the lagged consensus state:

```text
q_i ∈ [0,1]  membership tendency
s_i ∈ [0,1]  support / knownness
```

It derives support-aware membership:

```text
q̃_i = 0.5 + s_i (q_i - 0.5)
```

Therefore:

- `s_i = 1` preserves `q_i`;
- `s_i = 0` contracts the prediction to neutral `0.5`;
- weakly supported extreme `q_i` cannot masquerade as a high-confidence prediction.

`q̃_i` is not a calibrated probability and does not replace raw Evidence.

## 5. Same-decision readout moments

For every accepted contribution with authoritative weight `w_i = alpha_i × incoming_T_i`, the raster family may accumulate the following Companion-internal moments:

```text
M_scope(u)    = Σ_{i∈scope}    w_i
M_fg(u)       = Σ_{i∈scope}    w_i q̃_i
M_known(u)    = Σ_{i∈scope}    w_i s_i
M_core(u)     = Σ_{i∈Core}     w_i
M_frontier(u) = Σ_{i∈Frontier} w_i
```

The Companion derives, only where `M_scope` satisfies the calibrated validity contract:

```text
P(u) = M_fg / M_scope          soft foreground prediction
K(u) = M_known / M_scope       knownness / trust support
C(u) = M_core / M_scope        Core contribution fraction
F(u) = M_frontier / M_scope    Frontier contribution fraction
```

Requirements:

- moments use the same accepted sequence and `alpha × T` decisions as authoritative RGB and Direct Evidence;
- low or non-finite `M_scope` is invalid comparison support, not background evidence;
- `P/K/C/F` remain Companion-local and do not cross the Browser protocol as formal artifacts;
- the readout does not create a second visibility authority; raw `V` remains realized observation truth;
- implementation identity, memory layout, numerical tolerance, GPU cost, and reference parity are versioned and validated before production promotion.

## 6. Stable Mask regions used for Reliability

Reliability reuses the existing Stable Mask Evidence-region semantics instead of evaluating the whole frame uniformly:

1. **Strong Positive Interior** — target foreground supervision;
2. **Local Negative Context Ring** — local background/counter-evidence supervision;
3. **Boundary Band** — low-weight or diagnostic-only ambiguity region;
4. **Far Neutral** — excluded from Reliability.

The residual does not reinterpret missing or invalid readout support as Negative Evidence.

## 7. Trusted comparison support

A pixel contributes to the production residual only when the readout supplies valid semantic-scope mass and sufficient knownness under the versioned policy. Exact mass and knownness gates are calibration-owned.

If a View has insufficient trusted comparison support:

```text
Reliability weight = 1.0 (neutral)
reason = insufficient-comparison-support
```

Insufficient support is not evidence that the observation is unreliable.

User Confirmed or manually edited Stable Masks remain exempt from automatic downweighting and retain semantic weight `1.0`.

## 8. Asymmetric regional residual

### 8.1 Positive interior

Positive-interior disagreement may be reduced when the lagged readout indicates substantial Frontier contribution or weak knownness. This **Positive Frontier Protection** prevents a newly revealed true target part from being punished merely because the previous consensus did not contain it.

Conceptually:

```text
positive residual
= trusted BCE(P, 1)
× calibrated Frontier/unknown protection
```

The protection is bounded and cannot turn a well-supported contradiction into zero residual.

### 8.2 Local negative ring

Negative-ring disagreement uses trusted `BCE(P, 0)` without a symmetric Frontier exemption. A Stable Mask that says background while a high-knownness consensus predicts foreground is a material conflict that must remain visible to Reliability.

### 8.3 Boundary band

Boundary residual is normalized separately and receives a lower calibrated coefficient, or remains diagnostic-only in an initial implementation. It must not dominate the view score.

### 8.4 Far neutral

Far-neutral pixels do not enter Reliability.

## 9. Region-normalized view residual

A View-level residual is formed from separately normalized region means rather than a raw whole-frame sum:

```text
D_view = a · mean(trusted positive-interior residual)
       + b · mean(trusted negative-ring residual)
       + c · mean(trusted boundary residual)
```

The exact coefficients, robust cross-View normalization, non-zero reliability floor, warm-up behavior, and degenerate-view handling remain calibration/review inputs. Region normalization prevents resolution, object size, or ring area from dominating solely by pixel count.

Reliability remains view-level. Per-pixel maps are internal readout/diagnostic data, not product-facing per-pixel Reliability weights.

## 10. Production baseline versus leave-one-out reference

The production baseline uses lagged consensus derived from the complete canonical Included Stable observation set.

A leave-one-out reference benchmark may compute, for View `c`:

```text
Consensus excluding View c
→ readout under View c
→ reference residual / reliability
```

The leave-one-out path:

- is offline/reference-only and nonblocking;
- does not sit on the v2 critical path;
- measures self-influence gaps, ranking changes, Candidate quality, latency, and memory cost;
- cannot enter the production Runtime Profile without a later evidence-backed decision and explicit identity promotion.

## 11. Atomicity and failure

- Readout and residual terms are private Solver Iteration outputs.
- Partial or failed readouts do not replace the current Consensus Revision.
- A readout failure preserves Stable Masks, raw P/N/V, the prior complete Consensus Revision, and the prior inspectable Candidate.
- Non-converged recurrence remains governed by Amendment 003 and cannot publish Candidate.

## 12. Remaining review gates

Before V2C/V2D/V2E decomposition, later review must still close:

- exact `q0/s0` and q/s update transforms;
- robust residual-to-weight normalization across Views;
- warm-up count, non-zero floor, and degenerate robust-scale handling;
- convergence metric, numerical tolerance, and maximum Solver Iterations;
- Scope Delta promotion/rejection and Frontier Debt thresholds;
- GPU channel layout, performance budget, and locked reference parity;
- calibration, policy freeze, and production-promotion ownership.

## 13. Non-goals

This amendment does not:

- publish consensus maps to the Browser;
- make the soft readout a visibility or ownership authority;
- adopt production leave-one-out Reliability;
- introduce per-pixel product Reliability weights;
- change the current single Negative Mass production contract;
- modify Stable Mask, Participation, Candidate, Native Selection, or EditHistory authority.
