# AI Select Final Spec v1.1 — Amendment 004

## Sparse Key-View 3D-Guided Mask Acquisition with Optional Tracking

**Status:** Normative amendment to Final Spec v1.1  
**Date:** 2026-07-30  
**Applies to:** `ai-select-v1`  
**Amends:** Final Spec v1.1 §§18–20, 23–24, 27–32; Amendment 003 B4–B16  
**Related:** DG-24, DG-23, DG-21, DG-20, Tickets 06/07A/08/08A/09/12/14/20  
**Supersedes:** Amendment 003 requirements that make ordered object tracking, Bridge Views, correction memory, or tracker repropagation mandatory

This amendment is part of Final Spec v1.1 and has equal normative force for the clauses it amends.

Amendment 003 remains authoritative for object-level scope, conservative Anchor acquisition, and deferred Gaussian ownership except where this amendment explicitly changes the multi-view Mask acquisition route.

---

# C0. Mandatory D-double-prime product chain

The mandatory v1 chain is:

```text
Authoritative Anchor RGB
+ exact PromptState
→ conservative object-level Anchor acquisition
→ explicit user-confirmed Anchor Stable Mask
→ non-ownership TargetBootstrapArtifact
→ adaptive sparse Key Views
→ 3D-guided per-Key-View prompt synthesis
→ independent prompt-conditioned Mask inference per Key View
→ per-view assessment / correction / Participation
→ Included Stable View Annotations
→ per-view P/N/V Evidence
→ multi-view Gaussian ownership classification
```

Object tracking is not a mandatory stage.

---

# C1. TargetBootstrapArtifact remains non-ownership

Ticket 08 MAY derive a TargetBootstrapArtifact from authoritative depth, first-hit support, or an equivalent visible-surface method.

The artifact MAY contain:

```ts
interface TargetBootstrapArtifact {
    schemaVersion: number;
    targetContextId: string;

    anchorViewId: string;
    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;

    bootstrapPolicyDigest: string;
    supportDigest: string;
    artifactDigest: string;

    centerWorld: [number, number, number];
    extentWorld: [number, number, number];
    visibleSupportCount: number;
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
}
```

It MAY guide:

- target framing;
- candidate-camera generation;
- projected ROI / Box construction;
- projected positive and local-negative Prompt construction;
- conservative initial Working Set construction;
- render-quality and scene-support diagnostics.

It MUST NOT:

- publish final Owned Gaussian IDs;
- publish formal P/N/V Evidence;
- publish an AI Candidate;
- mutate Native Selection;
- claim unseen-surface completion;
- define a hard upper bound on later Evidence Working Set expansion.

A Gaussian MUST NOT become Rejected or Out of Scope solely because it is absent from the Anchor bootstrap support.

---

# C2. SparseKeyViewPlan

Ticket 08 MUST publish a bounded sparse Key-View plan.

```ts
interface PlannedKeyView {
    viewId: string;
    camera: CameraBinding;

    expectedObservationGain?: number;
    expectedDirectionalGain?: number;
    expectedRenderQuality?: number;

    validityPolicyDigest: string;
    plannerPolicyDigest: string;
}

interface SparseKeyViewPlanSegment {
    schemaVersion: number;
    segmentId: string;
    targetContextId: string;
    anchorStableMaskDigest: string;
    bootstrapDigest: string;
    plannerPolicyDigest: string;
    orderedKeyViews: readonly PlannedKeyView[];
    attemptId: string;
    artifactDigest: string;
}
```

The planner MUST decide separately:

```text
camera validity
expected target observation gain
directional diversity
render / scene support quality
resource cost
```

An invalid camera cannot be admitted because it has high theoretical information gain.

The mandatory plan MUST NOT require a tracker transition envelope, dense continuous sequence, or Bridge Views.

`Generate More` MUST append a new immutable plan segment. Existing completed segments and their View/RGB/Mask artifacts remain current. `Regenerate Auto Views` is the explicit operation that MAY supersede planner-owned segments.

---

# C3. Default per-Key-View Mask acquisition

Ticket 08A owns the default production Mask acquisition route.

For each authoritative Key-View RGB, the system MUST construct a versioned Prompt set from supported 2.5D information. Candidate Prompt families include:

- projected visible-support positive points;
- projected target center and extent;
- positive Box / ROI;
- local negative points or negative region around the projected target;
- Mask input from a compatible high-confidence projection when supported;
- Anchor-derived scale and framing diagnostics.

Every Prompt family is capability-gated. Unsupported Prompt types MUST fail closed and MUST NOT be silently dropped or converted.

Each Key View is inferred independently:

```text
Key-View RGB
+ exact CameraBinding
+ exact TargetBootstrapArtifact
+ exact 3D-guided Prompt set
→ prompt-conditioned model candidates
→ per-view validation / assessment
→ Auto Good / Review / Failed
→ Stable Mask publication where policy permits
```

A Key View MUST NOT depend on adjacent frames or tracker memory in the default route.

---

# C4. Multi-view Mask acquisition spike

Before production closure, Ticket 08A MUST compare:

```text
A. existing projected-support + independent single-frame SAM
B. enhanced 3D-guided per-Key-View SAM
C. object-level VOS tracker over an ordered/dense rendered sequence
D. hybrid Key-View references + tracker propagation
```

The benchmark MUST use the same authoritative RGBs and report both acquisition metrics and final downstream metrics.

Required metrics include:

```text
2D acceptable-mask rate
neighbouring-instance contamination
identity-switch rate where applicable
user correction count
per-object latency
peak VRAM
fallback / failure rate
final Gaussian precision / recall
background Gaussian contamination
Mixed / Uncertain ratio
user Add / Remove burden proxy
```

The default production decision rule is:

> If route B meets the locked final Gaussian quality, latency, and user-effort targets with a bounded sparse Key-View budget, v1 MUST NOT require a tracker.

A tracker or hybrid route enters production only through a separate ADR that records measurable downstream benefit, supported scene classes, runtime/resource limits, and added lifecycle semantics.

---

# C5. Optional tracker augmentation

If a later ADR selects route C or D, the implementation MAY add:

- ordered auxiliary tracking frames;
- tracker transition limits;
- Bridge Views;
- reference memory;
- explicit tracker repropagation;
- tracker-local identity-drift diagnostics.

These capabilities are optional and MUST be advertised explicitly.

If enabled:

```text
trackingMembership
≠
participation
```

Auxiliary / Bridge frames default Excluded and do not automatically contribute Evidence.

Tracker confidence, memory score, sequence role, and transition score are Mask-generation diagnostics only. They MUST NOT be formal Gaussian ownership Evidence.

---

# C6. Correction lifecycle

The mandatory correction lifecycle is per View:

```text
Prompt / Paint correction
→ Editing Mask
→ Confirm
→ new Stable Mask revision
→ that View Evidence dirty
→ Lift dirty
```

Confirming a correction MUST NOT automatically:

- create tracker memory;
- dirty unrelated Views;
- start multi-view propagation;
- compute Evidence;
- Re-Lift.

If optional tracker/hybrid capability exists, `Use as Tracking Reference` MUST be a separate explicit action.

```ts
interface CorrectionReference {
    schemaVersion: number;
    viewId: string;
    stableMaskDigest: string;
    rgbDigest: string;
    cameraBindingDigest: string;
    referenceRevision: number;
    artifactDigest: string;
}
```

Only this explicit action may create or replace a CorrectionReference and mark optional tracker propagation dirty.

---

# C7. Dirty-state and Mask refresh

Ticket 12 MUST support generic Mask acquisition dirtiness independently of tracker capability.

At minimum it exposes or derives:

```text
maskAcquisitionDirtyViewIds
optional propagationDirty
EvidenceDirtyViewIds
liftDirty
candidateStale
contextSuspended
```

For the default per-view route:

- retry/refresh affects only the selected View attempt;
- a new automatic proposal does not replace a user-confirmed Stable Mask silently;
- Confirmed Stable Mask change dirties only matching per-view Evidence and Lift;
- failure preserves prior Stable Mask and matching Evidence/Candidate;
- Re-Lift remains explicit.

`propagationDirty` and `Update Multi-view Masks` exist only if the selected optional backend advertises propagation capability.

Optional tracker repropagation MUST remain explicit and MUST never automatically Re-Lift.

---

# C8. Progressive publication

Every AIView publishes RGB independently from Mask and Evidence.

A default Key View MAY progress through:

```text
RGB Ready + Mask Not Requested
→ RGB Ready + Mask Generating
→ RGB Ready + Auto Stable Mask
```

or:

```text
RGB Ready + Mask Generating
→ RGB Ready + Mask Review / Mask Failed
```

Mask failure MUST NOT relabel valid RGB as View Render Failed.

Every automatic Mask artifact MUST bind:

- exact target and scene revision;
- exact View and CameraBinding;
- exact RGB digest;
- exact TargetBootstrapArtifact digest;
- exact Prompt synthesis policy and Prompt digest;
- acquisition backend/model/runtime identity;
- attempt identity;
- exact Mask artifact digest.

Late or stale results MUST be discarded.

---

# C9. Gallery and Review presentation

Ticket 09 MUST expose without conflation:

- Anchor / Key / User-added role;
- optional Auxiliary / Bridge role only when capability exists;
- RGB status;
- Mask acquisition backend and status;
- Stable Mask quality;
- Participation;
- Evidence status;
- optional tracking/reference status only when enabled.

Filtering or navigation MUST NOT mutate Participation, Mask identity, optional reference memory, Evidence, or Candidate identity.

---

# C10. Final Lift input and Working Set expansion

Formal lifting continues to consume exactly:

```text
AIViews
WHERE
  renderStatus = ready
  AND participation = included
  AND current Stable Mask exists
```

Key-View role, plan order, Prompt score, acquisition backend score, optional tracker confidence, and optional reference status do not authorize Evidence production.

The TargetBootstrapArtifact MAY seed a conservative Evidence Working Set, but it MUST NOT be the hard search-space upper bound.

Ticket 14/20 MUST allow later Included View Mask support to expand the Evidence Working Set. Full conservative Render Working Set occluders continue to participate in alpha compositing and incoming transmittance.

---

# C11. Failure and recovery

## Bootstrap unavailable

Retain Anchor RGB and Stable Mask. Use bounded local cameras or user-added Views. Fabricate no Gaussian ownership.

## No useful Key View

Retain Anchor and completed Views. Stop Limited or request a user-added View.

## Per-view acquisition failure

Retain View/RGB and prior Stable Mask. Offer retry with the selected backend, baseline fallback, manual correction, or Exclude.

## Optional tracker failure

Retain all current per-view artifacts. Tracker failure MUST NOT disable default independent per-view acquisition where that route is supported.

## Identity-drift suspicion

Only applies to optional tracking/hybrid routes. Publish Review/fail-closed behavior and do not overwrite a prior Stable Mask silently.

## Stale bootstrap / plan / Prompt / backend

Discard the result. Never attach an old Mask to a newer target, Anchor, View, RGB, CameraBinding, bootstrap, Prompt, or runtime identity.

---

# C12. Ticket ownership

```text
07A
= object-level Anchor acquisition
  + conservative ProposalDecision
  + Accept / Edit / Confirm

07B
= fitted-image Prompt/Edit palette interaction

08
= TargetBootstrapArtifact
  + adaptive sparse Key-View plan
  + append-only Generate More segments

08A
= multi-view Mask acquisition spike
  + enhanced 3D-guided per-Key-View SAM
  + acquisition-route ADR
  + optional tracker/hybrid augmentation only if selected

09
= Gallery / frustum / acquisition-status presentation

12
= generic Mask refresh and dirty/stale lifecycle
  + optional propagation lifecycle when capability exists

14 / 20
= final P/N/V Gaussian ownership
```

---

# C13. Required validation

The benchmark MUST include:

- table surrounded by chairs;
- multiple visually similar chairs;
- cabinet body and cabinet door;
- refrigerator against a wall;
- small and thin objects;
- partial occlusion;
- sparse large viewpoint changes;
- poor or fragmented 3DGS render;
- per-view correction;
- optional tracker correction/repropagation only when that route is evaluated.

Report at least:

```text
Anchor false auto-selection rate
Key-View usable rate
per-view acceptable-mask rate
neighbour-object contamination
identity-switch rate where applicable
manual correction count
per-view and end-to-end latency
peak VRAM
final Gaussian precision / recall
background Gaussian contamination
Mixed / Uncertain ratio
user Add / Remove burden proxy
```

---

# C14. Non-goals

This amendment does not:

- choose a tracker before the Ticket 08A spike;
- require tracking, Bridge Views, or dense trajectories;
- require whole-image object inventory;
- require part-level selection;
- make early visible support a formal Candidate;
- make correction references automatic;
- replace explicit Confirm or Re-Lift;
- replace P/N/V with Mask/tracker confidence;
- require watertight geometry or unseen-surface completion.
