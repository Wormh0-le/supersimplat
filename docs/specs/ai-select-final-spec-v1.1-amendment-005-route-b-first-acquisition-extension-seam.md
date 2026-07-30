# AI Select Final Spec v1.1 — Amendment 005

## Route-B-First 3D-Guided Per-Key-View Acquisition with C/D Extension Seams

**Status:** Normative amendment to Final Spec v1.1  
**Date:** 2026-07-30  
**Applies to:** `ai-select-v1`  
**Amends:** Amendment 004 C3–C5, C12–C14  
**Related:** DG-25, DG-24, Tickets 06/08/08A/09/12/14/20/21  
**Supersedes:** requirements that make A/B/C/D comparison or an acquisition-route ADR a prerequisite for Ticket 08A route-B implementation or closure

This amendment is part of Final Spec v1.1 and has equal normative force for the clauses it amends.

Amendment 004 remains authoritative for sparse Key Views, non-ownership bootstrap, per-view correction, optional tracking, and final P/N/V ownership except where this amendment changes route-selection and extension-interface requirements.

---

# D0. Selected production route

Ticket 08A MUST proceed directly with:

```text
Route B
= enhanced 3D-guided independent prompt-conditioned SAM inference
  for each sparse authoritative Key View
```

Route B is the selected v1 production route. It is not blocked by an A/B/C/D comparison or acquisition-route ADR.

Route A remains:

```text
existing projected-support + independent single-frame SAM
```

and MUST remain runnable as a regression baseline and declared fallback.

Routes C and D remain future optional experiments:

```text
C = object-level VOS tracker over ordered/dense rendered views
D = independent Key-View SAM references + tracker propagation
```

No implementation or benchmark of C or D is required to close Ticket 08A.

---

# D1. Route-B production validation

Ticket 08A MUST validate route B using locked fixtures and final downstream outcomes.

Required validation includes:

```text
per-view acceptable-mask rate
neighbour-object contamination
manual correction count
per-view and end-to-end latency
peak VRAM
fallback / failure rate
final Gaussian precision / recall
background Gaussian contamination
Mixed / Uncertain ratio
user Add / Remove burden proxy
```

This validation calibrates and hardens route B. It is not a route-selection tournament.

---

# D2. Backend-neutral acquisition capability contract

The implementation MUST expose a versioned backend-neutral capability contract equivalent to:

```ts
type MaskAcquisitionBackendKind =
    | 'per-view-sam'
    | 'sequence-tracker'
    | 'hybrid';

interface MaskAcquisitionCapabilities {
    schemaVersion: number;
    backendKind: MaskAcquisitionBackendKind;
    backendId: string;
    modelId: string;
    runtimeBuildId: string;

    supportsIndependentViews: boolean;
    supportsSequenceSessions: boolean;
    supportsReferenceUpdates: boolean;
    supportsAuxiliaryFrames: boolean;
    supportsRepropagation: boolean;

    capabilityDigest: string;
}
```

Route B MUST advertise:

```text
backendKind = per-view-sam
supportsIndependentViews = true
supportsSequenceSessions = false
supportsReferenceUpdates = false
supportsAuxiliaryFrames = false
supportsRepropagation = false
```

Capabilities are authoritative. Unsupported methods MUST fail closed before inference or state mutation.

---

# D3. Required per-view acquisition interface

Ticket 08A MUST implement a base provider equivalent to:

```ts
interface MultiViewMaskAcquisitionProvider {
    getCapabilities(): MaskAcquisitionCapabilities;

    acquireView(
        request: PerViewMaskAcquisitionRequest
    ): Promise<PerViewMaskAcquisitionResult>;
}
```

The route-B `acquireView` request MUST bind:

```text
targetContextId + contextRevision
scene / splat dependency identity
Anchor CameraBinding + RGB digest
Anchor Stable Mask digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
Key-View CameraBinding + RGB digest
adapter capability digest
Prompt synthesis policy digest
PromptState digest
backend / model / adapter / runtime identity
attempt identity
```

The result MUST bind the same identity plus:

```text
Mask artifact digest
acquisition backend kind / backend ID
model / runtime identity
assessment / diagnostics identity
fallback identity when used
```

Every Key View remains independently retryable and replayable.

---

# D4. Optional sequence/reference extension interface

The codebase MUST define an optional extension interface sufficient for later route-C and route-D experiments:

```ts
interface SequenceMaskAcquisitionExtension {
    openSequence(
        request: OpenMaskSequenceRequest
    ): Promise<OpenMaskSequenceResult>;

    acquireSequenceRange(
        request: AcquireMaskSequenceRangeRequest
    ): Promise<AcquireMaskSequenceRangeResult>;

    updateReferences(
        request: UpdateMaskSequenceReferencesRequest
    ): Promise<UpdateMaskSequenceReferencesResult>;

    closeSequence(
        request: CloseMaskSequenceRequest
    ): Promise<void>;
}
```

The intended route mapping is:

```text
Route B
→ acquireView only

Route C
→ sequence extension
  + optional acquireView fallback/recovery

Route D
→ acquireView for Key-View references
  + sequence extension between references
```

The route-B backend MUST NOT fabricate a sequence session. It advertises no sequence capability and rejects sequence/reference operations with a structured unsupported-capability result.

Defining this extension contract does not authorize tracker execution, auxiliary frames, correction memory, or propagation in the current product.

---

# D5. Orchestration and implementation seams

Ticket 08A MUST keep these concerns separate:

```text
View RGB rendering
3D-guided Prompt synthesis
per-view acquisition dispatch
optional future sequence-session dispatch
Mask artifact validation
Mask publication
View assessment / Participation
```

At minimum:

- `generated-view-controller.ts` MUST separate render jobs from acquisition jobs;
- `generated-view-service.ts` MUST expose backend-neutral per-view request/result contracts and optional sequence extension contracts;
- Companion state MUST dispatch by advertised backend capability and own bounded scheduling, replay, cancellation, and cleanup;
- `mask-registry.ts` MUST store acquisition provenance without understanding tracker internals;
- readiness/capability negotiation MUST identify route B and expose optional sequence/reference capabilities when present;
- Gallery MUST consume generic acquisition status rather than route-specific tracker state.

---

# D6. Future C/D adoption

Routes C and D MAY be evaluated after route B is implemented.

A future experiment MUST use authoritative RGBs and the same downstream P/N/V quality metrics. A separate ADR is required before any C/D backend becomes a production capability.

That ADR MUST define:

- supported scene classes and measurable downstream benefit;
- ordered auxiliary-frame contract;
- transition and resource envelope;
- sequence-session identity and lifecycle;
- reference-memory semantics;
- auxiliary / Bridge role and Participation separation;
- identity-drift fail-closed behavior;
- propagation atomicity;
- fallback to independent per-view acquisition;
- retry, cancellation, teardown, and migration behavior.

Future C/D experimentation MUST reuse the common acquisition identity/result envelope and per-view Stable Mask publication path where applicable.

---

# D7. Correction and dirty-state behavior

For route B, correction remains per View:

```text
Prompt / Paint correction
→ Editing Mask
→ Confirm
→ new Stable Mask revision
→ that View Evidence dirty
→ Lift dirty
```

Route B has no correction-reference or propagation-dirty state.

`Use as Tracking Reference`, `propagationDirty`, and `Update Multi-view Masks` remain absent or disabled unless a later C/D ADR enables the corresponding capability.

---

# D8. Ticket ownership

```text
08
= TargetBootstrapArtifact
  + adaptive sparse Key-View plan segments

08A
= backend-neutral acquisition contracts
  + route-B 3D-guided Prompt synthesis
  + route-B independent per-Key-View SAM implementation
  + route-A regression fallback
  + C/D extension interfaces without C/D implementation

09
= Gallery / frustum / generic acquisition-status presentation

12
= explicit route-B per-view Mask refresh
  + optional future propagation lifecycle only when capability exists

14 / 20
= final P/N/V Gaussian ownership
```

---

# D9. Acceptance rules

Ticket 08A MUST NOT claim closure unless:

- route-B Prompt synthesis is deterministic and artifact-bound;
- every Key View has independent attempt/retry identity;
- route-B capability advertisement is truthful;
- unsupported sequence/reference operations fail closed;
- per-view success/failure publication preserves Stable authority and stale-result rules;
- route A remains a declared baseline/fallback;
- the base acquisition provider and optional sequence extension contracts have protocol validators and golden identity tests;
- route-B production metrics are recorded;
- no C/D implementation is required.

---

# D10. Non-goals

This amendment does not:

- require an A/B/C/D comparison before route B;
- choose or implement a tracker;
- require a route-selection ADR for route B;
- require Bridge Views or dense trajectories;
- create sequence sessions for a backend that advertises none;
- make correction references automatic;
- replace P/N/V with acquisition confidence;
- change final Gaussian ownership or Native Selection semantics.
