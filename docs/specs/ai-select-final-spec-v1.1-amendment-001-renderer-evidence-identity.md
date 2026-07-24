# AI Select Final Spec v1.1 — Amendment 001

## Renderer / Evidence Implementation Identity and RGB Continuity

**Status:** Normative amendment to Final Spec v1.1  
**Date:** 2026-07-24  
**Applies to:** `ai-select-v1`  
**Amends:** Final Spec v1.1 §§5.4, 16, 18, 30, 31, 32  
**Related:** ADR 0013, DG-20, Tickets 14/19/20/21

This amendment is part of **AI Select Final Spec v1.1** and has equal normative force for the clauses it amends. It does not change the product model or FlashSplat-style Evidence mathematics. It closes two implementation-identity gaps required to make the RGB → Stable Mask → Direct Evidence chain replayable and fail-closed.

---

# A1. Normative identity additions

The authoritative observation and every production Evidence artifact MUST bind explicit implementation identity in addition to Camera, scene, Mask, policy, and Working Set identity.

The minimum implementation identity is:

```ts
interface RasterRuntimeIdentity {
  /** Identity of the authoritative raster implementation and decision chain. */
  rasterImplementationId: string;

  /** Identity of the selected Evidence backend and its material configuration. */
  evidenceBackendId: string;

  /** Exact build/runtime identity needed to reproduce the implementation. */
  runtimeBuildId: string;
}
```

The concrete values MAY be digests or structured version strings, but they MUST distinguish material changes including:

```text
rasterizer source revision
CUDA/C++ extension or pinned gsplat fork revision
compiler/build configuration that affects raster decisions
ABI and supported runtime contract
PyTorch/CUDA/runtime combination where material
enabled raster/Evidence kernel policy
fast-math / precision / termination policy where material
Evidence backend kind and configuration
```

A human-readable package version alone is insufficient when two builds can produce different raster acceptance, transmittance, or termination decisions.

---

# A2. Amendment to Final Spec §5.4 — Correctness identity

The identity list in Final Spec §5.4 is extended to:

```text
Target / Scene / Splat dependency
CameraBinding
RGB digest
Stable Mask digest（Evidence 使用时）
Evidence Policy digest（Evidence 使用时）
Render Working Set token
Evidence Working Set token
Stable Gaussian ID mapping
rasterImplementationId
evidenceBackendId（Evidence 使用时）
runtimeBuildId
```

An authoritative RGB artifact MUST bind at least:

```text
CameraBinding
Target dependency identity
Render Working Set token
rasterImplementationId
runtimeBuildId
RGB digest
```

A production Evidence artifact MUST additionally bind:

```text
Stable Mask digest
Evidence Policy digest
Evidence Working Set token
evidenceBackendId
```

Implementation identity is part of cache, stale-result, artifact reuse, Candidate readiness, and Selection Service readiness decisions. Matching Camera/scene inputs do not make artifacts compatible when implementation identity differs.

---

# A3. RGB-only and mask-conditioned traversal continuity

AI Select normally creates artifacts in this order:

```text
RGB-only authoritative render
    ↓
Stable Mask authored against that RGB
    ↓
mask-conditioned Direct Evidence traversal
```

The fact that RGB and Evidence are produced at different times does not weaken the same-decision requirement.

For a View used by production Direct Evidence:

1. The initial RGB-only render and the later mask-conditioned Evidence traversal MUST use the same `rasterImplementationId` and a compatible `runtimeBuildId` / render policy.
2. The RGB-only mode and RGB+Evidence mode MUST use the same Direct-Evidence-capable authoritative raster implementation.
3. Enabling Evidence writes MUST NOT alter authoritative RGB for identical scene, CameraBinding, Render Working Set, and render policy inputs, except within an explicitly declared and validated RGB parity policy.
4. The Evidence attempt MUST reuse the exact CameraBinding, authoritative render scope, Render Working Set identity, scene dependency identity, and relevant raster policy that produced the Stable Mask's bound RGB.
5. The Evidence traversal MUST produce or verify the authoritative RGB digest associated with the Stable Mask before publishing Evidence.
6. A matching formula implemented by an independently deciding kernel is not sufficient proof of continuity.

The preferred production behavior is:

```text
same raster implementation
same authoritative accepted-contribution decision chain
same alpha / incoming T / termination semantics
optional Evidence writes enabled by the Stable Mask policy
```

One literal CUDA launch is not required, but no later pass may independently re-decide boundary-sensitive acceptance or termination.

---

# A4. Renderer migration and incompatibility

A change to `rasterImplementationId`, incompatible `runtimeBuildId`, or material raster policy MUST NOT silently reuse an RGB/Mask/Evidence binding produced by the old implementation.

When renderer identity changes:

```text
old authoritative RGB
old Stable Mask binding
old per-view Evidence
old Candidate dependency
```

become incompatible for new production Direct Evidence unless a versioned migration/parity procedure has explicitly proven compatibility.

The default fail-closed recovery is:

```text
1. mark incompatible Evidence/Candidate stale or unavailable;
2. rerender authoritative RGB under the new rasterImplementationId;
3. present the new RGB for review;
4. regenerate, revalidate, or explicitly rebind the Mask through a declared workflow;
5. recompute Evidence and Candidate.
```

The system MUST NOT:

- keep the old Mask silently bound to a visually similar but differently identified RGB;
- claim same-decision equivalence solely because source formulas look identical;
- preserve a production-ready Candidate across an incompatible renderer migration;
- mutate CameraBinding to bypass implementation identity invalidation.

An explicit, benchmarked migration mechanism MAY be added later. Such a mechanism MUST be versioned and MUST preserve exact artifact provenance; visual similarity alone is insufficient.

---

# A5. Amendment to Final Spec §16 — Direct Evidence requirement

The opening sentence of Final Spec §16 is strengthened from recommendation to requirement:

> **The formal production path MUST accumulate Evidence from the authoritative raster decision chain.**

For each accepted contribution:

```text
w = alpha × incoming T
```

The same accepted contribution and the same `w` MUST be used for authoritative RGB and Evidence accumulation.

The production path MUST satisfy all of the following:

- same `rasterImplementationId` for RGB-only and RGB+Evidence modes;
- compatible `runtimeBuildId` and raster policy;
- exact Stable Mask → RGB digest binding verification;
- same projected data, order, alpha, incoming T, validity, and termination decision source;
- raw P/N/V output only from declared Mask weights;
- no complete Contributor dependency in the normal request path;
- no nearest/top-k/distance/center/visibility-only fallback.

A failed identity or RGB-binding check is an Evidence Failure. It MUST NOT relabel the already valid historical RGB as Render Failed, but it MUST block publication of new Evidence and Candidate.

---

# A6. Amendment to Final Spec §18 — GaussianEvidenceArtifact schema

The normative per-view artifact schema is extended to:

```ts
interface GaussianEvidenceArtifact {
  schemaVersion: number;

  targetContextId: string;
  targetDependencyToken: string;
  sceneVersion: string;
  splatVersion: string;

  viewId: string;
  cameraBindingDigest: string;
  rgbDigest: string;
  stableMaskDigest: string;
  evidencePolicyDigest: string;

  renderWorkingSetToken: string;
  evidenceWorkingSetToken: string;

  /** Authoritative RGB / traversal implementation identity. */
  rasterImplementationId: string;

  /** Distinguishes reference/autograd and production-direct backends. */
  evidenceBackendKind: 'reference' | 'production-direct';

  /** Exact Evidence backend source/configuration identity. */
  evidenceBackendId: string;

  /** Reproducible build and material runtime identity. */
  runtimeBuildId: string;

  stableGaussianIds: Uint32Array;

  positiveMass: Float32Array;
  negativeMass: Float32Array;
  visibleMass: Float32Array;

  boundaryMass?: Float32Array;
}
```

All arrays MUST describe the same ordered `stableGaussianIds` domain.

The artifact MUST become stale or incompatible when any of the following changes materially:

```text
Target / Scene / Splat dependency
CameraBinding
authoritative RGB digest
Stable Mask
Evidence Policy
Render Working Set
Evidence Working Set
Stable Gaussian ID mapping
rasterImplementationId
evidenceBackendKind / evidenceBackendId
runtimeBuildId
material raster/Evidence kernel policy
```

Reference and production artifacts are not interchangeable merely because their numerical arrays appear similar.

---

# A7. Candidate and readiness propagation

A Candidate produced from per-view Evidence MUST retain enough identity to determine:

```text
which rasterImplementationId produced its authoritative observations
which evidenceBackendKind/evidenceBackendId produced its Evidence
which runtimeBuildId and Evidence Policy were used
whether that backend is accepted for current production application
```

Reference/autograd Candidates MAY exist for development, benchmarking, and UI integration, but they MUST be visibly and programmatically non-production until the current Selection Service readiness policy accepts them.

Set/Add/Remove/Intersect MUST be disabled for:

- stale Candidates;
- renderer-incompatible Candidates;
- runtime-incompatible Candidates;
- reference-only Candidates when production application is required;
- Candidates whose underlying RGB/Mask/Evidence identity chain cannot be verified.

Disabling application MUST NOT destroy the inspectable Candidate or mutate Native Selection.

---

# A8. Required validation additions

The Stage 3/4 and core acceptance gates in Final Spec §§30–32 are extended with the following mandatory tests:

1. **RGB-only vs RGB+Evidence parity**  
   Identical inputs under one `rasterImplementationId` produce the same authoritative RGB digest or satisfy the declared validated parity policy.

2. **Stable Mask binding verification**  
   An Evidence attempt with a mismatching RGB digest publishes no artifact and does not silently rebind the Mask.

3. **Renderer migration invalidation**  
   Changing `rasterImplementationId` or incompatible `runtimeBuildId` invalidates incompatible RGB/Mask/Evidence/Candidate reuse and requires explicit recovery.

4. **Backend distinction**  
   Reference/autograd and production-direct artifacts cannot collide in cache, artifact identity, Candidate readiness, or Native application state.

5. **Reproducibility record**  
   Benchmark and production records include source/build/runtime identity sufficient to reproduce the raster/Evidence path.

6. **Same-decision regression**  
   A CameraBinding known to trigger complete Contributor/raster-alpha mismatch produces stable Direct Evidence without Contributor reconciliation.

7. **Failure isolation**  
   Identity or Evidence failure preserves the valid RGB, View, Stable Mask, Gallery, and previous Candidate while publishing no partial Evidence.

---

# A9. No product-flow change

This amendment does not change the v1.1 user flow:

```text
Authoritative RGB
→ Stable Mask
→ per-view P/N/V Evidence
→ multi-view Lift
→ Candidate + Uncertain
→ Native Selection operation
```

It only makes the implementation and artifact trust chain explicit so the product can safely render RGB before a Mask exists and compute Evidence later without recreating the separate-kernel ambiguity that ADR 0013 was intended to remove.