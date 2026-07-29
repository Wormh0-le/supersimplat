# AI Select Final Spec v1.1 — Amendment 003

## Object-level 2.5D Bootstrap, Ordered Mask Tracking, and Deferred Gaussian Ownership

**Status:** Normative amendment to Final Spec v1.1  
**Date:** 2026-07-29  
**Applies to:** `ai-select-v1`  
**Amends:** Final Spec v1.1 §§1, 10, 18–20, 23–24, 27–32; Amendment 002 Stage 2 closure language  
**Related:** DG-23, DG-21, DG-20, Tickets 06/07A/08/08A/09/12/14/20  
**Does not supersede:** Amendment 001 renderer/Evidence identity or Amendment 002 Prompt/Edit and Stable Mask lifecycle requirements

This amendment is part of Final Spec v1.1 and has equal normative force for the clauses it amends.

It adopts an object-level multi-view Mask acquisition architecture inspired by ArtisanGS while retaining AI Select's existing independent View/Mask/Evidence lifecycle and final P/N/V Gaussian lifting contract.

---

# B0. Scope and target granularity

AI Select v1 targets one **object instance** at a time.

The implementation MUST support selecting a spatially localized object instance through user Prompt and direct Mask correction.

The implementation is not required to provide:

- arbitrary part-level discovery;
- automatic part/whole hierarchy resolution;
- whole-image object inventory;
- scene-wide semantic instance IDs;
- automatic decomposition of every object in the scene.

A visually distinct component may still be selected when the user explicitly identifies it as the target. This amendment defines no universal ontology for whether that component is a part or an object.

---

# B1. Supersession of automatic Top-1 calibration requirement

This amendment supersedes Amendment 002 and DG-21 language that requires Ticket 07A to automatically resolve materially distinct eligible candidates through a benchmark-calibrated Top-1 decision margin.

Ticket 07A still MUST:

- preserve materially distinct alternatives;
- enforce every capability-enabled Prompt constraint;
- cluster near duplicates before bounded truncation;
- apply a single-candidate structural quality gate;
- prevent obvious neighbour-object leakage from silently succeeding;
- return structured `selected`, `ambiguous`, or `unavailable` decisions;
- pass locked-runtime false-auto-selection, contamination, latency, and recovery benchmarks.

Ticket 07A is permitted and expected to return `ambiguous` when two or more materially distinct object-level candidate clusters remain plausible.

A model score or versioned heuristic MAY choose a default preview or a representative inside one near-duplicate cluster. It MUST NOT be presented as a calibrated correctness probability.

---

# B2. Anchor object acquisition

The mandatory Anchor path is:

```text
Authoritative Anchor RGB
+ exact PromptState
→ prompt-conditioned proposal candidates
→ structural validation
→ exact deduplication
→ near-duplicate clustering
→ conservative ProposalDecision
→ explicit Accept Candidate
→ Editing Mask
→ optional Paint / Erase correction
→ Confirm Mask
→ Anchor Stable Mask
```

A mandatory whole-image proposal inventory is not part of the v1 Anchor path.

The Anchor Stable Mask is the object-identity seed for later tracking. It is not a final Gaussian ownership classification.

---

# B3. Conservative ProposalDecision

After hard Prompt consistency and near-duplicate clustering, Ticket 07A follows this minimum decision policy:

```text
0 eligible clusters
→ unavailable

1 eligible cluster + credible representative
→ selected

1 eligible cluster + structural risk
→ ambiguous

2 or more materially distinct eligible clusters
→ ambiguous
```

Structural risk includes, under versioned policy:

- extreme image-area occupancy;
- multiple substantial disconnected components;
- low largest-component ratio;
- excessive image-boundary contact;
- excessive positive-Box spill;
- Prompt constraint disagreement;
- likely neighbouring-object leakage;
- unstable output under equivalent repeated execution.

A `selected` proposal still requires explicit user acceptance before becoming Editing Mask and explicit Confirm before becoming Stable Mask.

---

# B4. TargetBootstrapArtifact

After Anchor Stable Mask confirmation, the system MAY derive a 2.5D target bootstrap from authoritative depth, first-hit visible support, or an equivalent declared visible-surface method.

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

    centerWorld: [number, number, number];
    extentWorld: [number, number, number];

    visibleSupportCount: number;
    quality:
        | 'usable'
        | 'limited'
        | 'unavailable';

    reasons: readonly string[];
}
```

The artifact MAY guide:

- target framing;
- camera validity checks;
- candidate-camera generation;
- local ROI construction;
- transition ordering;
- conservative Evidence Working Set hints.

It MUST NOT contain or claim:

- final Owned Gaussian IDs;
- formal P/N/V Evidence;
- AI Candidate publication;
- Native Selection mutation;
- unseen-surface completion.

---

# B5. TrackingSequencePlan

Ticket 08 MUST publish an ordered sequence plan rather than only an unordered camera set.

```ts
interface TrackingSequenceView {
    viewId: string;
    role: 'key' | 'bridge';
    camera: CameraBinding;

    expectedObservationGain?: number;
    expectedDirectionalGain?: number;
    transitionCostFromPrevious?: number;

    validityPolicyDigest: string;
    plannerPolicyDigest: string;
}

interface TrackingSequencePlan {
    schemaVersion: number;
    planId: string;
    targetContextId: string;

    anchorStableMaskDigest: string;
    bootstrapDigest: string;
    plannerPolicyDigest: string;

    orderedViews: readonly TrackingSequenceView[];
    attemptId: string;
}
```

The planner MUST decide separately:

```text
camera validity
observation value
directional diversity
adjacent-frame tracking transition cost
```

An invalid camera cannot be admitted because it has high theoretical information gain.

The planner MUST remain bounded and adaptive. This amendment defines no fixed orbit and no fixed View count.

---

# B6. Key View and Bridge View semantics

```text
Key View
= intended to add useful target observation
  and may become an Included Stable View

Bridge View
= intended primarily to keep tracking transitions bounded
  and is Excluded from final Lift by default
```

Each AIView gains a tracking role independent of Participation:

```ts
interface AIViewTrackingState {
    trackingMembership:
        | 'anchor'
        | 'key'
        | 'bridge'
        | 'none';

    sequencePlanId?: string;
    sequenceIndex?: number;
}
```

The following invariant is mandatory:

```text
trackingMembership
≠
participation
```

A Bridge View MAY become Included only through the same explicit Stable Mask and Participation rules as any other View. No role automatically authorizes Lift participation.

---

# B7. MaskTrackingRun

Ticket 08A owns object-level multi-view Mask tracking.

```ts
interface MaskTrackingRun {
    schemaVersion: number;
    trackingRunId: string;
    targetContextId: string;

    anchorStableMaskDigest: string;
    sequencePlanDigest: string;

    trackerBackendId: string;
    trackerModelId: string;
    runtimeBuildId: string;
    trackingPolicyDigest: string;

    referenceFrameStableMaskDigests: readonly string[];
    attemptId: string;
}
```

The production path is:

```text
Anchor Stable Mask
+ ordered Anchor / Key / Bridge RGB sequence
+ confirmed correction references
→ tracker session
→ progressive tracked Mask proposals
→ per-view validation / assessment
→ atomic Stable Mask publication where allowed
```

The tracker MUST maintain one object identity across the sequence. It MUST NOT silently switch to another similar instance.

The tracker backend is selected only after a bounded implementation spike and a separate ADR. The spike MUST compare the current projected-support + single-frame SAM baseline against candidate object-level tracking backends.

---

# B8. Current single-frame SAM path

The existing Generated View path based on Anchor support projection and one single-frame SAM pass remains valid as:

- a completed progressive-publication tracer bullet;
- a benchmark baseline;
- a fallback after tracker failure or unsupported runtime;
- an initializer for a correction frame.

After Ticket 08A production closure, it MUST NOT be described as the sole production object-identity propagation contract.

Fallback use MUST retain explicit backend identity and diagnostics.

---

# B9. Tracked Mask publication

Tracked Masks are independent per-view Mask artifacts.

A Generated View MAY progress through:

```text
RGB Ready + Mask Tracking
→ RGB Ready + Tracked Mask Review
→ RGB Ready + Auto Stable Mask
```

or:

```text
RGB Ready + Mask Tracking
→ RGB Ready + Mask Failed
```

Mask or tracker failure MUST NOT relabel a valid RGB as View Render Failed.

Automatic Stable Mask publication MUST be atomic and version-bound to:

- exact View and CameraBinding;
- exact RGB digest;
- exact tracking run;
- tracker backend/model/runtime;
- reference-memory revision;
- tracking policy;
- exact Mask artifact digest.

Late or stale results MUST be discarded.

Bridge Views default to Excluded even when a Stable Mask exists.

---

# B10. CorrectionReference

A user correction becomes tracker reference memory only after Confirm.

```ts
interface CorrectionReference {
    schemaVersion: number;
    viewId: string;
    stableMaskDigest: string;
    rgbDigest: string;
    cameraBindingDigest: string;
    createdFromTrackingRunId?: string;
    referenceRevision: number;
}
```

The lifecycle is:

```text
Prompt / Paint correction
→ Editing Mask only
→ no propagation invalidation

Confirm correction
→ new Stable Mask revision
→ optional CorrectionReference
→ propagationDirty = true
→ explicit Update Multi-view Masks
```

The system MUST NOT repropagate continuously while a user is painting.

A correction on a Bridge View MAY become tracker reference memory while the View remains Excluded from Lift.

---

# B11. Explicit tracker repropagation

Ticket 12 `Update Multi-view Masks` consumes:

```text
current Anchor Stable Mask
+ current confirmed CorrectionReferences
+ current TrackingSequencePlan
+ current tracker backend/model/runtime/policy
```

It produces a new bound tracking run and atomically publishes replacement per-view Mask revisions.

Repropagation MAY be full-sequence or policy-declared bounded-range repropagation. The affected range and reference dependencies MUST be explicit.

Repropagation MUST:

- be user-triggered;
- preserve prior Stable Masks on failure;
- publish no partial stable replacement set when the contract requires atomic group publication;
- reject late results against current identities;
- refresh assessment/Participation inputs after publication;
- never automatically compute P/N/V Evidence or AI Candidate.

---

# B12. Gallery and Review presentation

Ticket 09 MUST expose without conflation:

- Anchor / Key / Bridge tracking role;
- sequence position;
- RGB status;
- tracking/Mask status;
- correction-reference status;
- Stable Mask quality;
- Participation;
- Evidence status.

Bridge Views SHOULD be visually de-emphasized or grouped by default but remain inspectable.

Filtering, sequence navigation, or correction-reference inspection MUST NOT mutate Participation or Mask identity.

---

# B13. Final Lift input remains unchanged

Formal Gaussian lifting consumes exactly:

```text
AIViews
WHERE
  renderStatus = ready
  AND participation = included
  AND stableMaskId exists
```

Tracking role, tracker confidence, sequence position, and correction-reference status do not independently authorize Evidence production.

Ticket 14 continues to define per-view P/N/V and multi-view classification. Ticket 20 continues to define production same-decision Evidence.

Tracker confidence MAY be stored as a Mask-generation diagnostic. It MUST NOT be used as formal Gaussian ownership Evidence or shown as a Gaussian correctness percentage.

---

# B14. Failure and recovery

## Bootstrap unavailable

Retain Anchor RGB and Stable Mask. Planner falls back to bounded local camera moves or user-added Views. No Gaussian ownership is fabricated.

## No valid tracking sequence

Retain Anchor and completed Views. Stop with an actionable Limited state or request user-added Views.

## Tracker failure

Retain every published RGB and prior Stable Mask. Offer tracker Retry, single-frame fallback, manual correction, or View exclusion.

## Identity drift / instance switch suspicion

Do not silently publish as Auto Good. Mark Review, preserve the prior Stable Mask when present, and request correction or exclusion.

## Repropagate failure

Retain prior Stable Masks, matching Evidence, and prior Candidate. Publish no incompatible partial replacement.

## Stale sequence or reference memory

Discard the result. Never attach an old tracked Mask to a newer Anchor, RGB, CameraBinding, sequence, Target Context, or correction-reference revision.

---

# B15. Ticket ownership

```text
07A
= object-level Anchor candidate acquisition
  + conservative ProposalDecision
  + Accept / Edit / Confirm

07B
= fitted-image Prompt/Edit palette interaction

08
= TargetBootstrapArtifact
  + valid adaptive Key Views
  + Bridge Views
  + ordered TrackingSequencePlan

08A
= tracker backend spike
  + MaskTrackingRun
  + correction-memory integration
  + progressive tracked Mask production
  + single-frame fallback

09
= Gallery / frustum / sequence-role / tracking-state presentation

12
= propagation dirty state
  + explicit tracker repropagate
  + atomic replacement / stale-result lifecycle

14 / 20
= final P/N/V Gaussian ownership
```

---

# B16. Required validation

The planning/tracking benchmark MUST include:

- one table surrounded by chairs;
- multiple visually similar chairs;
- cabinet body and cabinet door;
- refrigerator against a wall;
- small object;
- thin object;
- partial occlusion;
- large adjacent-camera transition;
- poor or fragmented 3DGS render;
- correction keyframe followed by repropagation.

Report at least:

```text
Anchor false auto-selection rate
Anchor neighbour-object contamination
tracking identity-switch rate
tracked-mask drift
correction recovery rate
Key View usable rate
Bridge View count
single-frame fallback rate
per-view and end-to-end latency
peak VRAM
final Gaussian precision / recall
background Gaussian contamination
Mixed / Uncertain ratio
user Add / Remove burden proxy
```

The implementation MUST compare:

```text
A. projected-support + independent single-frame SAM baseline
B. selected object-level tracking backend
C. tracking backend + confirmed correction references
```

---

# B17. Non-goals

This amendment does not:

- choose a concrete tracker before the Ticket 08A spike;
- require whole-image proposal inventory;
- require part-level selection;
- make early visible support a formal Gaussian Candidate;
- require fixed full-orbit views;
- make Bridge Views Included by default;
- replace explicit Confirm, Repropagate, or Re-Lift actions;
- replace P/N/V with tracker confidence or binary Mask optimization;
- require watertight geometry or unseen-surface completion.