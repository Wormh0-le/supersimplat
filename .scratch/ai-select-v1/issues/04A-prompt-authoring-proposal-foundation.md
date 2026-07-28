# 04A — Prompt Authoring Layer + Multi-Prompt Anchor Mask Proposal Foundation

Status: proposed — ready-for-agent after DG-21 / Final Spec v1.1 Amendment 002 approval

Blocked by: 03, 04

Required before: 07A

Retrofitted consumers: 05, 07, 12

## Final Spec mapping

- Final Spec v1.1 §§4, 7, 10–12, 24
- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- DG-09 Independent Mask Authoring & Versioning
- DG-12 Anchor Validation & Confirm Gate
- MVP Phase 2 quality hardening

## Context

Ticket 04 established the independent Editing Mask / Stable Mask / Evidence lifecycle. Its current SAM 3.1 adapter and browser interaction are intentionally narrow:

```text
click / Shift-click
→ point prompts only
→ one selected SAM candidate
→ Editing Mask
```

The current browser also overloads pointer-drag as direct Mask painting. This prevents a normal drag gesture from becoming a Box prompt and conflates two different operations:

```text
Prompt Authoring
= input constraints sent to the model

Pixel Editing
= direct mutation of the current Editing Mask bitmap
```

This ticket introduces the missing Prompt Authoring and proposal-generation foundation. It does not complete proposal ranking, ambiguity policy, or the end-to-end Three-Stage pipeline; Ticket 07A owns those.

## Inputs / preconditions

- RGB-ready Anchor AIView with exact RGB digest
- Ticket 04 MaskAnnotation / MaskRegistry / MaskController lifecycle
- CurrentTargetContext and stale-result gate
- Existing SAM 3.1 point adapter and model manifest/readiness boundary
- AI View Dock selected-view image surface
- Existing mask-local Undo/Redo and Stable Mask confirmation

## Outputs / handoff artifacts

- Versioned per-view `PromptState`
- Explicit Prompt and Edit tool modes
- Point, Box, Mask-constraint, and capability-gated Text prompt protocol
- Versioned prompt digest and request identity
- Multi-candidate `AutoMaskProposalSet`
- Generic model-adapter capability contract
- Candidate preview/selection seam consumed by Ticket 07A
- Compatibility path for the existing point-only adapter
- Frozen interaction and protocol fixtures

## What to build

### 1. Separate Prompt Authoring from Pixel Editing

Introduce two explicit tool groups.

Prompt tools:

```text
Positive Point
Negative Point
Box
Positive Prompt Brush
Negative Prompt Brush
Text Prompt — only when the selected adapter advertises support
```

Edit tools:

```text
Paint
Erase
Brush Size
Mask Undo
Mask Redo
Clear
Restore Accepted Auto
```

Pointer behavior MUST depend on the selected tool. There is no implicit “long press means Brush” rule.

Minimum pointer semantics:

```text
Point tool       click                 → point prompt
Box tool         drag                  → box prompt
Prompt Brush     drag                  → prompt-mask constraint
Paint / Erase    drag                  → Editing Mask bitmap edit
Pan/Inspect      existing editor rules → no Prompt/Mask mutation
```

### 2. Add a versioned PromptState

Suggested domain shape:

```ts
type PromptTool =
    | 'positive-point'
    | 'negative-point'
    | 'box'
    | 'positive-mask-constraint'
    | 'negative-mask-constraint'
    | 'text';

interface PointPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    xPx: number;
    yPx: number;
}

interface BoxPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    x0Px: number;
    y0Px: number;
    x1Px: number;
    y1Px: number;
}

interface MaskConstraintPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    artifact: BinaryMaskArtifact;
}

interface TextPrompt {
    promptId: string;
    text: string;
    locale?: string;
}

interface PromptState {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    revision: number;
    points: readonly PointPrompt[];
    boxes: readonly BoxPrompt[];
    maskConstraints: readonly MaskConstraintPrompt[];
    textPrompts: readonly TextPrompt[];
    digest: string;
}
```

Prompt identity MUST bind:

```text
targetContextId
contextRevision
TargetDependencyToken
viewId
CameraBinding / RGB digest
Prompt schema version
Prompt revision / digest
model manifest digest
adapter capability/version identity
proposal policy version
attempt identity
```

### 3. Define model-adapter capabilities

The frontend MUST NOT infer model features from the model name.

Suggested capability payload:

```ts
interface PromptAdapterCapabilities {
    points: boolean;
    negativePoints: boolean;
    boxes: boolean;
    maskInput: boolean;
    negativeMaskConstraints: boolean;
    text: boolean;
    multiCandidateOutput: boolean;
}
```

The currently installed SAM 3.1 point adapter may advertise only its implemented point capabilities until its runtime integration is extended.

Unsupported tools MUST be disabled with an explicit reason. They MUST NOT accept input and silently ignore it.

### 4. Generalize the request protocol

Replace the point-only semantic contract with a generic prompt request.

Suggested request:

```ts
interface AnchorMaskProposalRequest {
    requestBinding: AIRequestBinding;
    viewId: string;
    cameraBindingDigest: string;
    rgb: AnchorRgbArtifact;
    promptState: PromptState;
    modelManifestDigest: string;
    adapterCapabilityDigest: string;
    proposalPolicyVersion: string;
    proposalAttemptId: string;
}
```

Same-attempt replay remains idempotent. An explicit Retry creates a new attempt for the exact same inputs.

### 5. Preserve multiple model candidates

The Companion MUST return all bounded, structurally valid candidates required by the selected adapter/policy rather than collapsing immediately to one mask by model score.

Suggested output:

```ts
interface AutoMaskProposal {
    proposalId: string;
    mask: BinaryMaskArtifact;
    modelScore?: number;
    modelScoreSemantics?: string;
    promptConsistency: {
        positivePointsSatisfied: boolean;
        negativePointsSatisfied: boolean;
        boxConstraintsSatisfied?: boolean;
        maskConstraintsSatisfied?: boolean;
    };
    sourceIndex: number;
}

interface AutoMaskProposalSet {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    promptStateDigest: string;
    modelManifestDigest: string;
    adapterCapabilityDigest: string;
    proposalPolicyVersion: string;
    proposals: readonly AutoMaskProposal[];
}
```

The proposal bound MUST be explicit and versioned. Truncation MUST be deterministic and recorded.

### 6. Preserve the Ticket 04 lifecycle

Proposal output is not a Stable Mask.

Until Ticket 07A completes ranking and acceptance:

```text
PromptState
→ AutoMaskProposalSet
→ proposal preview / compatibility choice
→ Editing Mask
```

The previous Stable Mask remains current until Confirm Mask publishes a new Stable revision.

Prompt changes MUST NOT:

- mutate the current Stable Mask;
- stale Evidence/Candidate before a new Stable Mask is confirmed;
- overwrite local pixel edits without an explicit discard/replace action.

### 7. Toolbar and interaction shell

Add a compact screenshot-tool-style toolbar adjacent to the selected AI View image.

Required UI properties:

- selected tool is visually unambiguous;
- Prompt and Edit groups are visually separated;
- brush size applies only to the relevant brush tool;
- Box drag displays a live rectangle and never paints pixels;
- Text input has an explicit Apply action;
- unsupported tools expose capability status;
- keyboard focus and Mask Undo/Redo routing remain explicit;
- switching away with uncommitted Prompt or Editing changes follows the existing discard-warning policy.

## Acceptance criteria

### Domain and protocol

- [ ] `PromptState` is per-view, immutable-by-revision, RGB-bound, digest-bound, and stale-result safe.
- [ ] Points, boxes, mask constraints, and text prompts have distinct validated payload types.
- [ ] Adapter capabilities are explicit and included in request/result identity.
- [ ] Unsupported prompt types fail at the UI/protocol boundary; they are never silently dropped.
- [ ] Same-attempt replay and new-attempt Retry semantics match existing RGB/Mask contracts.
- [ ] Proposal output preserves a bounded candidate set and model score semantics without calling it calibrated correctness confidence.

### Interaction

- [ ] Click and drag behavior is determined only by the selected tool.
- [ ] Default image drag does not implicitly paint the Mask.
- [ ] Box drag cannot produce Paint/Erase edits.
- [ ] Prompt Brush does not directly mutate the Editing Mask bitmap.
- [ ] Paint/Erase does not silently mutate PromptState.
- [ ] Prompt and mask-local Undo/Redo histories are independent and focus-routed.
- [ ] Restore Accepted Auto refers to the latest explicitly accepted auto proposal, not merely the highest raw model score.

### Lifecycle

- [ ] Prompt revisions update proposal state only.
- [ ] A proposal may seed an Editing Mask but cannot become Stable without Confirm Mask.
- [ ] Existing Stable Mask and dependent Evidence remain current while Prompt/proposal/edit work is unconfirmed.
- [ ] RGB/context/restart changes dispose incompatible Prompt and proposal state.
- [ ] Late proposal responses cannot attach to a newer Prompt revision or RGB digest.

### Compatibility

- [ ] The existing point-only SAM adapter remains usable through the generic capability contract.
- [ ] Text Prompt is capability-gated and is not a Phase A production requirement.
- [ ] No complete Contributor or formal P/N/V Evidence is required.

## Failure / recovery criteria

- [ ] Model/runtime failure preserves RGB, PromptState, prior Stable Mask, and local Editing Mask.
- [ ] No-candidate output is represented as proposal-unavailable, not View Render Failed.
- [ ] Protocol/capability mismatch is actionable and publishes no partial proposal set.
- [ ] Cancellation/OOM publishes no partial candidate set.
- [ ] A local Paint/Erase edit made while inference is in flight supersedes the late inference result unless the user explicitly applies it.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- Browser interaction walkthrough:
  - Point+ / Point-
  - Box drag
  - Prompt Brush+ / Prompt Brush-
  - Paint / Erase
  - independent Undo/Redo
- Protocol fixtures for every capability combination
- Stale Prompt/RGB/context response tests
- Multi-candidate structural and truncation tests
- Existing point-only adapter regression

## Non-goals

- No final proposal ranking or automatic ambiguity decision; Ticket 07A owns it.
- No claim that model score is correctness probability.
- No production Gaussian Evidence.
- No Generated View camera planning changes.
- No automatic text/concept support when the installed adapter lacks it.
- No direct Candidate or Native Selection mutation.

## Handoff to Ticket 07A

Ticket 04A is complete only when Ticket 07A can consume:

```text
authoritative RGB
+ exact PromptState
+ bounded AutoMaskProposalSet
+ explicit adapter/model/policy identity
```

Ticket 07A is the owner that completes the Three-Stage Anchor Mask Pipeline by implementing proposal ranking, ambiguity handling, acceptance/editing integration, and production quality validation.
