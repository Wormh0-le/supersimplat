# DG-23 — Object-level 2.5D Bootstrap, Ordered Mask Tracking, and Deferred Gaussian Ownership

- **Status:** CLOSED
- **Date:** 2026-07-29
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendments 001–003
- **Anchor acquisition owner:** Ticket 07A
- **2.5D bootstrap / sequence planner owner:** Ticket 08
- **Tracking implementation owner:** Ticket 08A
- **Repropagate lifecycle owner:** Ticket 12
- **Final Gaussian ownership owner:** Tickets 14 and 20

## Decision question

After a user confirms an object-level Anchor Mask, how should AI Select obtain reliable multi-view Masks for final 2D→3D Gaussian lifting without requiring whole-image object inventory, prematurely declaring Gaussian ownership, or independently rediscovering the object in every Generated View?

## Context

The product target for AI Select v1 is one **object instance** selected from an unstructured 3DGS scene. Arbitrary part-level discovery and complete semantic scene decomposition are not required.

The current tracer-bullet Generated View path performs:

```text
Anchor support projection
→ synthesized positive points
→ one independent single-frame SAM pass per Generated View
```

This proves progressive View/RGB/Mask publication, but it does not provide a production object-identity mechanism across larger view changes.

A whole-image proposal inventory would add scene-wide proposal generation, deduplication, hierarchy, association, and cache lifecycle even though the user is selecting only one object instance. Conversely, lifting a provisional binary Gaussian ownership set from one Anchor and using it as the identity source can create a self-reinforcing error loop.

ArtisanGS demonstrates a useful separation: user-guided 2D object selection can be propagated over an ordered view sequence with object-level mask tracking and human correction, while 3D geometry assists camera planning and working-set localization. The present decision adopts that architectural separation while retaining AI Select's P/N/V Evidence contract rather than adopting ArtisanGS's final binary Gaussian optimization.

Reference:

- NVIDIA Research, *ArtisanGS: Interactive Tools for Gaussian Splat Selection with AI and Human in the Loop*, arXiv:2602.10173, 2026.
- https://research.nvidia.com/labs/sil/projects/ArtisanGS/

## Decision

Adopt the following production architecture:

```text
Object-level Anchor acquisition
→ explicit user-confirmed Anchor Stable Mask
→ 2.5D target bootstrap from depth / first-hit support
→ adaptive Key View planning + ordered Bridge Views
→ object-level multi-view mask tracking
→ human correction keyframes + explicit repropagate
→ Included Stable View Annotations
→ final per-view P/N/V Evidence
→ multi-view Gaussian ownership classification
```

The central rule is:

> Use 3D geometry early for localization, camera validity, ordering, and ROI; defer Gaussian ownership until the final multi-view Evidence stage.

## Decision 1 — v1 target granularity is one object instance

The default target is one spatially localized object instance.

AI Select v1 does not require:

- arbitrary part-level selection;
- automatic part/whole hierarchy discovery;
- whole-image object inventory;
- semantic labels or a scene-wide object database;
- automatic decomposition of every object in the scene.

A component such as a door or drawer may still be selected when the user's Box/Point/Mask constraints identify it as the intended instance. The system does not need to infer a universal ontology for whether it is a part or an object.

## Decision 2 — Anchor acquisition remains prompt-conditioned and conservative

The Anchor path remains:

```text
Authoritative Anchor RGB
+ Point / Box / Mask Constraint
→ prompt-conditioned model candidates
→ exact and near-duplicate clustering
→ conservative ProposalDecision
→ explicit Accept / Edit / Confirm
→ Anchor Stable Mask
```

Ticket 07A must prevent obvious false automatic selection and expose `ambiguous` when materially distinct object-level candidates remain plausible. It is not required to learn or calibrate a general Top-1 correctness probability.

A whole-image `segment everything` inventory is not a mandatory prerequisite. It may be evaluated later as an on-demand fallback, but it is not part of v1 closure.

## Decision 3 — early 3D is 2.5D bootstrap, not ownership

From the confirmed Anchor Stable Mask, the system may derive a versioned bootstrap artifact using authoritative depth, first-hit support, or equivalent visible-surface data.

The bootstrap may contain:

- visible target support points;
- robust target center;
- visible extent / scale estimate;
- conservative local ROI or Working Set hint;
- camera framing and transition diagnostics.

It must not contain or claim:

- final Owned Gaussian IDs;
- a formal Candidate;
- P/N/V ownership Evidence;
- Native Selection mutation;
- completion of unseen surfaces.

## Decision 4 — planner outputs Key Views and Bridge Views

Ticket 08 produces an ordered tracking sequence rather than only an unordered set of high-gain cameras.

```text
Key View
= expected to add useful object observation and may later participate in Lift

Bridge View
= inserted to keep adjacent tracking transitions bounded
  and is not expected to add independent Lift value
```

The planner must evaluate camera validity before information gain and must also evaluate transition cost between adjacent sequence frames.

A tracking sequence may contain Bridge Views that are not shown as primary review targets and are excluded from Lift by default.

## Decision 5 — tracking membership and Lift participation are separate

The following states are independent:

```text
trackingMembership: anchor | key | bridge | none
participation: included | excluded
```

A Bridge View may be necessary for tracking while remaining Excluded from final P/N/V lifting.

A Key View may still be Excluded because its Mask is Review/Failed, RGB is unsuitable, or the user explicitly excludes it.

No tracking role automatically grants Lift participation.

## Decision 6 — object-level tracking is the production multi-view Mask path

Ticket 08A owns the production path:

```text
Anchor Stable Mask + ordered sequence
→ tracker session
→ progressive per-view tracked Mask proposals
→ assessment / correction
→ Stable Mask publication
```

The current projected-support + independent single-frame SAM path remains:

- a completed tracer-bullet baseline;
- a tracker failure fallback;
- a benchmark comparison;
- an optional correction initializer.

It is not the production object-identity contract after Ticket 08A closes.

The tracker backend is not selected by this DG. Ticket 08A begins with a bounded spike comparing available tracking backends and the current baseline. A later ADR locks the chosen backend, runtime identity, transition limits, memory policy, and fallback rules.

## Decision 7 — correction frames are confirmed tracker references

A user may correct a Generated View through Prompt refinement or Paint/Erase.

```text
Editing correction
→ no propagation change

Confirm correction
→ Stable Mask revision
→ eligible correction reference
→ propagationDirty
→ explicit Update Multi-view Masks
```

Only a confirmed Stable Mask may become tracker reference memory.

A correction reference can influence adjacent or subsequent tracked Masks during explicit repropagation. Repropagation remains atomic, preserves prior Stable Masks on failure, and never automatically performs final Evidence/Lift.

## Decision 8 — final Gaussian ownership remains P/N/V based

The final ownership path is unchanged:

```text
Included Stable View Annotations
→ per-view positive / negative / visible Evidence
→ multi-view aggregation
→ Selected / Uncertain / Rejected / Out of Scope
→ Candidate + Uncertain
```

Tracker confidence, tracker memory score, prompt score, and 2D proposal score are not formal Gaussian ownership Evidence.

Ticket 14 remains the reference P/N/V contract owner. Ticket 20 remains the production same-decision GPU Evidence owner.

## Decision 9 — bridge and tracking artifacts have explicit identity

Tracking and sequence artifacts bind at least:

```text
targetContextId
scene / splat revision
Anchor CameraBinding and RGB digest
Anchor Stable Mask digest
bootstrap policy and digest
sequence-plan policy and digest
tracker backend / model / runtime identity
reference-frame Stable Mask digests
attempt identity
```

Any incompatible change makes dependent tracking results stale. Late results cannot publish into a newer Target Context, sequence plan, Anchor revision, or reference-memory revision.

## Decision 10 — view planning remains adaptive

DG-23 does not mandate a fixed circular trajectory or fixed View count.

Ticket 08 continues to own:

- valid indoor observation poses;
- target observation gain;
- directional diversity;
- bounded resource budget;
- marginal-gain early stop;
- Generate More / Stop / Regenerate behavior.

It adds sequence ordering and bounded transition planning. Bridge frames are generated only when needed to connect useful Key Views under the selected tracking backend's declared transition envelope.

## Rejected alternatives

### Mandatory whole-image object inventory

Rejected for v1 because the product selects one user-specified object instance and does not require scene-wide object enumeration, proposal hierarchy, or persistent semantic object IDs.

### Provisional single-view Gaussian ownership as tracking truth

Rejected because an Anchor Mask error can contaminate the provisional ownership set and then be projected into every later view, reinforcing the original mistake.

### Independent single-frame SAM as the only production propagation method

Rejected because every view must rediscover object identity independently and large view changes or occlusion can cause drift or instance switches. It remains a baseline and fallback.

### Fixed full orbit / fixed number of views

Rejected because indoor geometry, training-view support, occlusion, and object placement make a universal orbit invalid. The planner remains validity- and gain-driven.

### Include every tracking frame in Lift

Rejected because Bridge Views may be redundant, low quality, or created only for transition continuity. Tracking membership does not imply Participation.

### Use tracker confidence as Gaussian ownership confidence

Rejected because tracker confidence is a 2D propagation diagnostic and does not replace alpha/transmittance-based per-Gaussian positive, negative, and visible Evidence.

## Consequences

### Positive

- one reliable object identity is maintained across multiple views;
- no mandatory scene-wide inventory or per-scene semantic training;
- 3D geometry helps planning without prematurely deciding ownership;
- human correction can improve an entire tracking run rather than patching one frame only;
- existing Stable Mask, Participation, dirty-state, and P/N/V contracts remain usable;
- current single-frame propagation remains a valid baseline/fallback.

### Costs

- ordered sequence and Bridge View planning;
- tracker session/runtime lifecycle;
- correction-memory and partial/full repropagation semantics;
- additional artifact identities and stale-result gates;
- backend spike and a later implementation ADR;
- Gallery/Review UI must expose tracking roles without conflating them with Participation.

## Ticket ownership

```text
07A — object-level Anchor acquisition and conservative ProposalDecision
07B — floating Prompt/Edit palette interaction
08  — 2.5D bootstrap + adaptive Key/Bridge sequence planning
08A — object-level tracking + correction memory + backend spike
09  — Gallery / inspection / tracking-role presentation
12  — explicit tracker repropagate and dirty/stale lifecycle
14  — reference P/N/V final lifting
20  — production same-decision P/N/V Evidence
```

## Required implementation sequence

```text
04B Visual Prompt Adapter Enablement
→ 07A Object-level Anchor Acquisition
→ 07B Floating Prompt/Edit Palette
→ 08 2.5D Bootstrap + Key/Bridge Sequence Planner
→ 08A Phase-0 tracker spike
→ tracker implementation ADR
→ 08A production tracking path
→ 09 / 11 / 12 multi-view correction lifecycle
→ 14 reference P/N/V final Lift
→ 20 production same-decision Evidence
```

## Non-goals

DG-23 does not:

- choose a tracker backend before the bounded spike;
- require arbitrary part selection;
- require whole-image segmentation inventory;
- change Confirm-only Stable Mask publication;
- change explicit Repropagate / explicit Re-Lift semantics;
- replace P/N/V with binary optimization or tracker confidence;
- require watertight geometry or unseen-surface completion;
- make Bridge Views automatically Included.