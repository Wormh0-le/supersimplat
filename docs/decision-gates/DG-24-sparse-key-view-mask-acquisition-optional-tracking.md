# DG-24 — Sparse Key-View Mask Acquisition with Optional Tracking

- **Status:** CLOSED
- **Date:** 2026-07-30
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendments 001–004
- **Supersedes:** DG-23 decisions that made ordered object tracking, Bridge Views, correction memory, or tracker repropagation mandatory
- **Anchor owner:** Ticket 07A
- **2.5D bootstrap / sparse Key-View planner owner:** Ticket 08
- **Multi-view Mask acquisition owner:** Ticket 08A
- **Dirty / refresh lifecycle owner:** Ticket 12
- **Final Gaussian ownership owner:** Tickets 14 and 20

## Decision question

After a user confirms an object-level Anchor Stable Mask, what is the minimum production architecture needed to obtain reliable multi-view Masks for final 2D→3D Gaussian lifting?

In particular, must AI Select require an object tracker and a dense ordered view sequence, or can sparse high-value Key Views be segmented independently with 3D-guided prompts?

## Context

AI Select v1 selects one object instance and ultimately classifies Gaussians from multiple Included Stable Masks using P/N/V Evidence.

ArtisanGS demonstrates that dense rendered views plus video object segmentation and correction memory can produce useful multi-view masks. It does not establish that a tracker is necessary for sparse adaptive views or for AI Select's P/N/V lifting objective.

AI Select already has:

```text
confirmed object-level Anchor Stable Mask
+ exact CameraBinding / RGB identities
+ first-hit / visible-support seams
+ independent Generated View RGB publication
+ projected-support + single-frame SAM baseline
+ per-view Review / Exclude / manual correction
```

The product should first test whether a small number of high-value independently segmented Key Views already meet downstream Gaussian quality and user-effort targets.

## Decision

Adopt the D-double-prime architecture:

```text
Object-level Anchor acquisition
→ explicit user-confirmed Anchor Stable Mask
→ non-ownership 2.5D target bootstrap
→ adaptive sparse Key Views
→ 3D-guided per-Key-View prompt synthesis
→ independent prompt-conditioned SAM inference per Key View
→ per-view Review / correction / Participation
→ optional tracker augmentation only if benchmark-justified
→ Included Stable View Annotations
→ final per-view P/N/V Evidence
→ multi-view Gaussian ownership classification
```

The central rule is:

> Sparse 3D-guided per-view segmentation is the default production path. Tracking is an optional augmentation, not a mandatory identity mechanism.

## Decision 1 — object-level Anchor scope is unchanged

Ticket 07A remains responsible for conservative prompt-conditioned Anchor acquisition and explicit Accept / Edit / Confirm.

No whole-image object inventory, arbitrary part discovery, or early Gaussian ownership is required.

## Decision 2 — early 3D remains non-ownership bootstrap

Ticket 08 may derive visible support, center, extent, projected ROI, candidate-camera framing, and prompt-synthesis hints from the confirmed Anchor.

The bootstrap:

- may seed camera planning and per-view Prompt synthesis;
- may seed a conservative Evidence Working Set;
- must not publish Owned Gaussian IDs, Candidate, P/N/V, or Native Selection;
- must not become a hard upper bound on later Evidence Working Set expansion;
- must not claim unseen-surface completion.

## Decision 3 — sparse Key Views are the mandatory planner output

Ticket 08 selects a bounded set of high-value Key Views using:

- camera validity;
- target observation gain;
- directional diversity;
- render / scene support quality;
- resource budget;
- marginal-gain stopping.

The mandatory v1 plan does not require:

- a dense video-like trajectory;
- Bridge Views;
- tracker transition envelopes;
- tracker-specific ordering.

The plan may expose deterministic review order, but that order is not a tracking contract.

`Generate More` appends an immutable Key-View plan segment. Completed segments and their current View/RGB/Mask artifacts remain valid. `Regenerate Auto Views` is the explicit operation that may supersede planner-owned segments.

## Decision 4 — default per-Key-View Mask acquisition

For each authoritative Key-View RGB, Ticket 08A synthesizes versioned prompts from available 2.5D information, including any supported combination of:

- projected positive support points;
- projected object center / extent;
- positive Box or ROI;
- local negative points or negative region outside the projected target;
- prior high-confidence Mask input when supported;
- Anchor-derived scale and framing diagnostics.

Each Key View is inferred independently. A Key View does not require adjacent frames or persistent tracker memory.

The existing projected-positive-points + single-frame SAM path remains baseline A. Ticket 08A adds an enhanced 3D-guided per-view path as candidate/default production path B.

## Decision 5 — multi-view Mask acquisition spike precedes final route closure

Ticket 08A begins with a bounded spike comparing:

```text
A. existing projected-support + independent single-frame SAM
B. enhanced 3D-guided per-Key-View SAM
C. object-level VOS tracker over an ordered/dense rendered sequence
D. hybrid: independent Key-View SAM references + tracker between references
```

The comparison must include final downstream outcomes, not only 2D tracking IoU:

- Gaussian precision / recall;
- background Gaussian contamination;
- Mixed / Uncertain ratio;
- user correction count and Add / Remove burden proxy;
- identity-switch and neighbouring-instance contamination;
- per-object latency and peak VRAM;
- failure recovery and implementation/runtime complexity.

Exit rule:

> If enhanced per-Key-View SAM meets the locked quality and user-effort targets with a small bounded number of Key Views, v1 does not adopt a mandatory tracker.

A tracker or hybrid route enters production only through a later ADR that records measurable downstream benefit and its additional lifecycle cost.

## Decision 6 — Bridge Views are capability-gated

Bridge Views and transition envelopes exist only if the selected optional tracker/hybrid backend requires them.

They are not part of the mandatory Ticket 08 planner contract.

If adopted later:

- auxiliary tracking frames remain distinct from Key Views;
- tracking membership remains distinct from Lift Participation;
- auxiliary frames default Excluded;
- tracker confidence is not P/N/V ownership Evidence.

## Decision 7 — correction is per-view by default

The default correction lifecycle is:

```text
Prompt / Paint correction
→ Editing Mask
→ Confirm
→ new Stable Mask revision for that View
→ that View Evidence dirty
→ Lift dirty
```

Confirming a correction does not automatically create tracker memory or dirty other Views.

If an optional tracker/hybrid backend is adopted, `Use as Tracking Reference` is a separate explicit action. Only that action creates a correction reference and enables explicit repropagation.

## Decision 8 — refresh and repropagate are capability-gated

Ticket 12 owns generic dirty-state and Mask refresh semantics:

- retry/refresh one Key View under the selected per-view acquisition policy;
- mark only changed Stable View Evidence dirty;
- keep Re-Lift explicit;
- preserve prior Stable Masks on failure.

Tracker repropagation exists only when the selected backend advertises that capability. It is not a mandatory v1 action.

## Decision 9 — final ownership remains P/N/V based

Formal lifting still consumes only:

```text
Render Ready
+ Participation Included
+ current Stable Mask
```

Prompt scores, acquisition backend scores, tracker confidence, bootstrap support, plan order, and optional auxiliary roles do not authorize Gaussian ownership.

The TargetBootstrapArtifact may seed an Evidence Working Set, but later Included View support must be able to expand that set. Gaussians outside the bootstrap seed cannot be rejected merely because the Anchor did not observe them.

## Rejected alternatives

### Mandatory dense tracking pipeline

Rejected because the product may reach target Gaussian quality with fewer independently segmented Key Views and avoid tracker session, Bridge, reference-memory, and repropagation complexity.

### Mandatory Bridge planning before backend selection

Rejected because transition limits are backend-specific and irrelevant to the default independent per-view route.

### Independent per-view SAM with projected positive points only

Retained as a baseline, but insufficient as the final default without evaluating Box/ROI, local negatives, Mask input, and stronger 2.5D prompt synthesis.

### Tracker confidence as ownership confidence

Rejected because it is a 2D acquisition diagnostic, not alpha/transmittance-based per-Gaussian Evidence.

### Anchor bootstrap as hard Gaussian search bound

Rejected because unseen sides may become visible in later Key Views.

## Ticket ownership

```text
07A — object-level Anchor acquisition
07B — Prompt/Edit palette interaction
08  — non-ownership 2.5D bootstrap + adaptive sparse Key-View planning
08A — multi-view Mask acquisition spike + enhanced per-Key-View SAM + optional augmentation decision
09  — Gallery / inspection / acquisition-status presentation
12  — generic dirty/refresh lifecycle + optional tracker repropagate when capability exists
14  — reference P/N/V final lifting
20  — production same-decision P/N/V Evidence
```

## Required implementation sequence

```text
04B Visual Prompt Adapter Enablement
→ 07A Object-level Anchor Acquisition
→ 07B Floating Prompt/Edit Palette
→ 08 2.5D Bootstrap + Sparse Key-View Planner
→ 08A multi-view Mask acquisition spike
→ acquisition-route ADR
→ 08A production 3D-guided per-Key-View path
→ optional tracker/hybrid augmentation only if ADR selects it
→ 09 / 11 / 12 multi-view review and correction lifecycle
→ 14 reference P/N/V final Lift
→ 20 production same-decision Evidence
```

## Non-goals

DG-24 does not:

- choose a concrete tracker;
- require Bridge Views;
- require dense trajectories;
- require whole-image object inventory;
- change Confirm-only Stable publication;
- make correction references automatic;
- replace P/N/V with Mask/tracker confidence;
- require watertight geometry or unseen-surface completion.
