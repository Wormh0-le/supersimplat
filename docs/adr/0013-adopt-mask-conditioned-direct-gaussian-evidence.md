# ADR 0013: Adopt Mask-Conditioned Direct Gaussian Evidence for AI Select Lifting

- **Status:** Accepted
- **Date:** 2026-07-23
- **Applies to:** `ai-select-v1`
- **Normative product spec:** `docs/specs/ai-select-final-spec-v1.1.md`
- **Supersedes in part:** ADR 0012 where it requires complete per-pixel Contributor artifacts as the production lifting representation
- **Decision Gate:** DG-20 — Mask-Conditioned Direct Gaussian Evidence

## Context

AI Select v1.0 established this production concept:

```text
Camera View
    ↓
gsplat RGB / complete per-pixel Contributor
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Gaussian Lifting
    ↓
AI Candidate
```

The complete Contributor path preserves pixel-to-Gaussian provenance by producing, for every rendered pixel, a variable-length list of Gaussian IDs and `alpha × transmittance` weights.

That work established valuable foundations:

- gsplat is the authoritative AI observation renderer;
- the editor owns Stable Gaussian IDs;
- `CameraBinding` binds the rendered RGB and the corresponding 3D frustum;
- lifting uses actual alpha-compositing contribution rather than nearest-Gaussian or top-k approximation;
- contributor mass is validated against raster alpha;
- attribution failures fail closed rather than silently producing a Candidate.

However, the complete Contributor representation creates structural cost and a correctness seam that the final lifting policy does not inherently require.

### Complete Contributor cost

The complete path requires:

```text
RGB rasterization
    ↓
per-pixel contributor count
    ↓
variable-size allocation or padded max-K allocation
    ↓
per-pixel contributor IDs + weights
    ↓
second aggregation pass
    ↓
per-Gaussian positive / negative / visible evidence
```

Its costs include:

- variable-length output;
- high GPU and host memory consumption;
- count/fill phases or padded `H × W × K` buffers;
- expensive transfer, hashing, caching, and lifecycle management;
- retaining pixel-level provenance that the production Candidate policy does not consume.

### Separate-kernel decision mismatch

The locked gsplat path obtains authoritative RGB/raster alpha from the main rasterizer and complete Contributor data from separate CUDA operations.

Although those operations consume the same projection and tile metadata, each CUDA kernel independently re-evaluates floating-point decisions such as:

- Gaussian validity near the alpha threshold;
- sigma validity near zero;
- accumulated transmittance;
- early termination near the transmittance threshold.

Near float32 decision boundaries, the RGB and Contributor kernels can produce slightly different alpha or contributor chains.

The existing implementation correctly fails closed and attempts bounded boundary reconstruction. However, this produces an undesirable product-level failure mode:

```text
authoritative RGB succeeds
+
one or a few Contributor pixels cannot be proven equivalent
→
the whole AI View preview is treated as failed
```

That coupling is inappropriate for Camera Inspection and unnecessary for the eventual 3D lifting result.

### Actual lifting requirement

For observable object selection, the production policy needs per-Gaussian Evidence, not a reusable complete pixel-to-Gaussian table.

For view `v`, pixel `p`, and Gaussian `g`, define the authoritative visible contribution:

\[
w_{v,p,g} = \alpha_{v,p,g} T_{v,p,g}
\]

Given target-positive, local-negative, and valid-observation weights:

\[
m^+_{v,p}, \quad m^-_{v,p}, \quad m^V_{v,p}
\]

the per-view Evidence required by lifting is:

\[
P_{v,g} = \sum_p m^+_{v,p} w_{v,p,g}
\]

\[
N_{v,g} = \sum_p m^-_{v,p} w_{v,p,g}
\]

\[
V_{v,g} = \sum_p m^V_{v,p} w_{v,p,g}
\]

These fixed per-Gaussian channels are sufficient for:

- positive object support;
- local background counter-evidence;
- visible observation strength;
- multi-view consistency;
- Selected / Rejected / Uncertain classification;
- Observation Coverage;
- explicit Re-Lift;
- per-view exclusion and replacement.

## Decision

Adopt **Mask-Conditioned Direct Gaussian Evidence** as the production lifting representation for AI Select v1.1.

The normative flow becomes:

```text
Camera View
    ↓
authoritative gsplat RGB
    ↓
Independent Versioned Mask
    ↓
mask-conditioned per-view Gaussian Evidence (P / N / V)
    ↓
multi-view Evidence aggregation and policy classification
    ↓
AI Candidate + Uncertain
    ↓
Native Set / Add / Remove / Intersect
```

Complete per-pixel Contributor artifacts are no longer required for normal AI View readiness, Camera Inspection preview, Anchor publication, or production lifting.

They remain permitted as a bounded **debug/reference backend** for:

- algorithm equivalence tests;
- regression fixtures;
- local attribution inspection;
- diagnosis of rasterizer or Evidence-kernel defects;
- benchmark comparison during migration.

## 1. Separate observation rendering from Evidence computation

An AI View is render-ready when its authoritative gsplat RGB for the exact `CameraBinding` is available and valid.

```text
RGB Ready
≠
Evidence Ready
```

Evidence is mask-conditioned and therefore cannot be a mandatory output of the mask-independent RGB render request.

A successful RGB render must not be converted into `View Render Failed` merely because a complete Contributor or Evidence operation failed.

The system must distinguish:

- **View Render Failure** — camera or authoritative RGB unavailable;
- **Mask Failure** — mask generation/editing failed;
- **Evidence Failure** — per-view Gaussian Evidence could not be produced;
- **Lift Failure** — multi-view aggregation, classification, or publication failed.

## 2. Preserve authoritative raster semantics

The production Direct Evidence path must derive each Evidence update from the same authoritative raster traversal semantics used to produce the corresponding AI RGB.

For every accepted Gaussian/pixel contribution, RGB and Evidence must share:

- the same projected Gaussian data;
- the same front-to-back ordering;
- the same sigma evaluation;
- the same alpha value;
- the same Gaussian validity decision;
- the same incoming transmittance `T`;
- the same `alpha × T` weight;
- the same early-termination decision.

The architectural requirement is **same decision source**, not necessarily one literal CUDA launch.

A multi-pass implementation is valid only when later passes reuse authoritative decisions rather than independently re-deciding contributor acceptance in a way that can diverge from RGB.

## 3. Directly accumulate per-Gaussian Evidence

For every accepted contribution with:

\[
w = \alpha T
\]

the production path accumulates fixed channels:

```cpp
positiveMass[g] += positiveWeight[p] * w;
negativeMass[g] += negativeWeight[p] * w;
visibleMass[g]  += visibleWeight[p]  * w;
```

Optional versioned channels may include:

- boundary/mixed mass;
- per-view observation count;
- high-confidence positive mass;
- diagnostic footprint statistics.

CUDA outputs raw Evidence. Multi-view aggregation and final classification remain in a versioned Evidence Policy rather than being hard-coded into the rasterizer.

## 4. Use local positive, boundary, and negative regions

The default Mask Evidence policy must not treat the entire image outside the target mask as equally strong negative evidence.

The initial policy uses:

- **strong positive interior** — an eroded or otherwise high-confidence target region;
- **boundary/ignore band** — low-weight or neutral pixels around uncertain mask edges;
- **local negative context ring** — nearby background used for leakage and attachment disambiguation;
- **far region** — neutral for this target.

Soft mask probabilities are allowed. Positive, negative, and visible weights are independent and need not sum to one.

## 5. Separate Render Working Set from Evidence Working Set

Two different sets are required.

### Render Working Set

The conservative CameraBinding-specific set of all Gaussians that may affect authoritative RGB, occlusion, transmittance, or termination.

A spatially chunked Render Working Set is valid only when it is proven render-equivalent to the complete scene for that CameraBinding.

### Evidence Working Set

The target-local set whose Stable Gaussian IDs receive Evidence writes, typically:

```text
Evidence Working Set = Core Target Set ∪ Context Set
```

Gaussians outside the Evidence Working Set still participate in projection, ordering, occlusion, transmittance, and termination when they are in the Render Working Set. They simply do not receive `P/N/V` writes.

The implementation must never rasterize only the Evidence Working Set when doing so would remove occluders or alter transmittance.

## 6. Preserve per-view raw Evidence

The system stores a versioned per-view Evidence artifact before cross-view aggregation.

A conforming artifact binds at least:

```text
target / scene / splat dependency identity
CameraBinding digest
authoritative RGB digest
Stable Mask digest
Evidence Policy digest
Render Working Set token
Evidence Working Set token
Stable Gaussian IDs
positiveMass[]
negativeMass[]
visibleMass[]
optional boundaryMass[]
```

Per-view artifacts permit:

- excluding one View;
- replacing one Stable Mask;
- incremental Re-Lift;
- cross-view consistency analysis;
- limiting the influence of a single close/high-resolution View;
- atomic publication of a new Candidate without destroying the prior valid Candidate.

## 7. Preserve observable-object semantics

AI Select v1.1 selects Gaussians supported by valid observation. It does not claim to recover unobserved physical ownership.

The internal classification remains:

```text
Selected
Uncertain
Rejected
Out of Scope
```

The new Evidence interpretation maps:

- strong consistent target ownership → `Selected`;
- strong consistent local-background ownership → `Rejected`;
- mixed target/background evidence → `Uncertain(reason=mixed-or-boundary)`;
- insufficient visible evidence → `Uncertain(reason=unobserved-or-insufficient)`;
- outside the target Evidence scope → `Out of Scope`.

Unobserved Gaussians are not automatically negative.

## 8. Stage implementation through a reference PoC

The implementation proceeds in stages.

### Stage A — Reference Evidence PoC

Use stock gsplat capabilities, autograd/feature rendering, or another independently testable reference method to validate:

- `P/N/V` sufficiency;
- mask-band policy;
- multi-view aggregation;
- classification margins;
- selection quality;
- per-view artifact lifecycle.

This stage may be slower and is not the production trust boundary.

### Stage B — Same-decision production path

Implement a locked Direct Evidence path that accumulates Evidence from the authoritative raster decision chain.

The preferred production implementation is a project-owned/pinned CUDA extension or a controlled pinned gsplat fork.

### Stage C — Calibration and hardening

Validate:

- reference-vs-production Evidence equivalence;
- repeat-run classification stability;
- atomic accumulation nondeterminism;
- VRAM and latency;
- spatial working-set equivalence;
- OOM/cancellation behavior;
- atomic Candidate publication.

## 9. Retain complete Contributor only as reference/debug capability

The complete Contributor backend must not remain on the normal Camera Inspection or Anchor RGB critical path.

It may remain available behind an explicit debug/reference boundary. Failure of that backend must not invalidate an otherwise valid RGB observation or a successful production Direct Evidence Lift.

No production policy may silently fall back from Direct Evidence to nearest-Gaussian, top-k, distance, center projection, or visibility-only attribution.

## Consequences

### Positive

- removes complete per-pixel variable-length Contributor data from the production lifting contract;
- eliminates RGB/Contributor alpha alignment as a normal product gate;
- makes Camera Inspection RGB readiness independent from later mask-conditioned lifting;
- reduces GPU/host memory and artifact-transfer pressure;
- makes the formal artifact proportional to the Evidence Working Set;
- preserves actual `alpha × transmittance` semantics;
- supports incremental multi-view Evidence and explicit Re-Lift;
- retains Stable Gaussian ID traceability;
- makes mixed/boundary and unobserved states explicit.

### Costs

- requires a new versioned Evidence artifact and lifecycle;
- requires a new reference PoC and benchmark suite;
- production same-decision accumulation likely requires custom CUDA or a pinned gsplat modification;
- atomic accumulation introduces floating-point reduction-order nondeterminism;
- complete pixel-level provenance is not available in the normal production artifact;
- ViewAssessment, Coverage, and Lift Readiness must migrate from Contributor terminology to Evidence/visibility terminology.

### Risks and mitigations

#### Large Gaussian crossing target/background

A primitive may receive material positive and negative mass. It must become Uncertain/Mixed rather than being forced into a binary class.

#### Mask propagation error

Per-view raw Evidence, View exclusion, Stable Mask review, and cross-view conflict detection remain required.

#### Remote background over-penalization

Use a local context ring and neutral far region.

#### Occlusion error from target-only rendering

The complete conservative Render Working Set continues to participate in rasterization; only Evidence writes are target-local.

#### Atomic nondeterminism

Use calibrated policy margins, repeat-run tests, and classification-stability acceptance criteria. Do not place classification boundaries at the last few float32 ULPs.

#### Representation entanglement

One Gaussian may encode both object and background appearance. The policy may identify it as mixed but cannot split the primitive without a separate scene-edit/reconstruction operation.

## Compatibility and migration

ADR 0012 remains authoritative for:

- the AI Select product/tool model;
- Current Target Context;
- authoritative gsplat RGB;
- versioned independent masks;
- Participation;
- explicit Repropagate/Re-Lift;
- Candidate lifecycle;
- Native Selection authority;
- scene-dependency suspension and exact Undo recovery.

This ADR supersedes only the parts of ADR 0012 and Final Spec v1.0 that require complete per-pixel Contributor artifacts as:

- an AI View render-readiness condition;
- an Anchor Confirm binding;
- the production lifting representation;
- the production Evidence-cache format.

During migration:

1. authoritative RGB remains unchanged;
2. complete Contributor remains available as a reference/debug path;
3. AI View state separates RGB readiness from Evidence readiness;
4. Final Spec v1.1 and revised tickets govern new implementation;
5. old Contributor-based fixtures remain valid reference fixtures until explicitly replaced;
6. Candidate publication remains fail-closed and atomic.

## Rejected alternatives

### Increase global contributor-alpha tolerance

Rejected because a small total-alpha residual does not prove correct Stable Gaussian ID attribution.

### Renormalize Contributor weights

Rejected because it changes mass without identifying which Gaussian attribution is wrong.

### Quarantine mismatch pixels as the v1 production contract

Rejected as the primary architecture because it weakens the complete-provenance invariant without removing the expensive Contributor representation. It may remain a diagnostic experiment.

### Use top-k contributors

Rejected because weak contributions may accumulate materially across pixels/views and top-k is not equivalent to complete alpha-compositing Evidence.

### Rasterize only the target/local Working Set

Rejected because removing non-target occluders changes transmittance and creates false visible support.

### Make complete Contributor mandatory for RGB Preview

Rejected because Contributor is mask-independent overhead and its failure should not invalidate a successful authoritative observation render.

## Validation requirements

Before the Direct Evidence path becomes the only production Lift backend, the implementation must demonstrate:

- strong-evidence `P/N/V` agreement with a trusted reference backend;
- stable final classification on repeated identical inputs;
- no production dependency on complete Contributor publication;
- correct Stable Gaussian ID mapping;
- correct per-view invalidation on Camera/Mask/Policy/Working-Set changes;
- full-scene/reference parity for spatial Render Working Sets;
- unobserved Gaussians remain Uncertain rather than Rejected;
- mixed boundary Gaussians remain Uncertain;
- failed Evidence/Lift does not destroy the last valid Candidate;
- failed Evidence does not turn a valid RGB View into Render Failed;
- no silent truncation, nearest-Gaussian, top-k, or best-effort attribution fallback.
