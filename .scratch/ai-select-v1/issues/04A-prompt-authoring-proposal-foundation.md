# 04A — Prompt Authoring Layer + Multi-Prompt Proposal Foundation

Status: implemented — 2026-07-28

Blocked by: 03, 04, 05

Required before: 07A

Affected completed consumers: 05, 07

Future consumers: 07A, 11, 12

## Final Spec mapping

- Final Spec v1.1 §§4, 7, 10–12, 24
- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- DG-09 Independent Mask Authoring & Versioning
- DG-12 Anchor Validation & Confirm Gate
- MVP Phase 2 quality hardening

## Purpose

Ticket 04 established the independent Editing Mask / Stable Mask / Evidence lifecycle. Ticket 05 added mask-local Undo/Redo, Restore Auto, Anchor validation, and Confirm Anchor. The current browser/model path remains intentionally narrow:

```text
click / Shift-click
→ point prompts only
→ adapter selects one SAM candidate
→ Editing Mask
```

Pointer drag is also overloaded as direct bitmap painting, preventing a clean Box gesture and conflating:

```text
Prompt Authoring
= constraints sent to the model

Pixel Editing
= direct mutation of the Editing Mask bitmap
```

This ticket builds the generic Prompt Authoring and bounded proposal foundation. Ticket 07A remains the completion owner for 2D-first ranking, ambiguity handling, proposal acceptance, and production Anchor quality.

The data model and toolbar SHOULD be reusable by Anchor, Generated, and User-added Views. Closure of this ticket is evaluated on the Anchor path; it does not change the existing Generated View automatic publication contract.

## Inputs / preconditions

- RGB-ready AIView with exact RGB digest
- Ticket 04 MaskAnnotation / MaskRegistry / MaskController lifecycle
- Ticket 05 mask-local Undo/Redo, Restore Auto, validation, and Confirm seams
- CurrentTargetContext and stale-result rejection
- Existing SAM 3.1 point adapter and manifest/readiness boundary
- AI View Dock selected-view image surface

## Outputs / handoff artifacts

- Versioned per-view `PromptState`
- Explicit Prompt and Edit tool modes
- Point, Box, mask-constraint, and capability-gated Text prompt protocol
- Versioned prompt digest and request identity
- Bounded `AutoMaskProposalSet`
- Explicit model-adapter capability contract
- Proposal preview/selection seam for Ticket 07A
- Compatibility path for the current point-only adapter
- Frozen interaction/protocol fixtures

## 1. Separate Prompt Authoring from Pixel Editing

Prompt tools:

```text
Positive Point
Negative Point
Positive Box
Negative Box — only when supported
Positive Prompt Brush / Mask Constraint
Negative Prompt Brush / Mask Constraint
Positive Text Prompt — only when supported
Negative Text Prompt — only when supported
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

Pointer behavior MUST depend only on the active tool:

```text
Point tool       click                 → point prompt
Box tool         drag                  → box prompt
Prompt Brush     drag                  → prompt-mask constraint
Paint / Erase    drag                  → Editing Mask bitmap edit
Pan / Inspect    existing editor rules → no Prompt/Mask mutation
```

There is no implicit “long press means Brush” behavior.

## 2. Versioned PromptState

Suggested domain:

```ts
type PromptTool =
    | 'positive-point'
    | 'negative-point'
    | 'positive-box'
    | 'negative-box'
    | 'positive-mask-constraint'
    | 'negative-mask-constraint'
    | 'positive-text'
    | 'negative-text';

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
    polarity: 'include' | 'exclude';
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
adapter capability digest
proposal policy version
attempt identity
```

## 3. Explicit adapter capabilities

The frontend MUST NOT infer prompt support from the model name.

```ts
interface PromptAdapterCapabilities {
    points: boolean;
    negativePoints: boolean;
    boxes: boolean;
    negativeBoxes: boolean;
    maskInput: boolean;
    negativeMaskConstraints: boolean;
    text: boolean;
    negativeText: boolean;
    multiCandidateOutput: boolean;
    capabilityDigest: string;
}
```

Unsupported tools MUST be disabled or rejected with an explicit reason. They MUST NOT accept input and silently ignore it.

The current point-only adapter remains valid through this contract. A single-candidate adapter may return a one-element proposal set, but that compatibility mode is not sufficient by itself to close Ticket 07A's multi-candidate quality gate.

## 4. Generic proposal request

```ts
interface MaskProposalRequest {
    requestBinding: AIRequestBinding;
    viewId: string;
    cameraBindingDigest: string;
    rgb: AuthoritativeRgbArtifact;
    promptState: PromptState;
    modelManifestDigest: string;
    adapterCapabilityDigest: string;
    proposalPolicyVersion: string;
    proposalAttemptId: string;
}
```

Same-attempt replay is idempotent. Explicit Retry creates a new attempt for the exact same semantic inputs.

## 5. Preserve bounded model proposals

The Companion MUST return all bounded, structurally valid candidates required by the selected adapter/policy rather than collapsing immediately to one mask by model score.

```ts
interface AutoMaskProposal {
    proposalId: string;
    mask: BinaryMaskArtifact;
    sourceIndex: number;
    modelScore?: number;
    modelScoreSemantics?: string;
    promptConsistency: {
        positivePointsSatisfied: boolean;
        negativePointsSatisfied: boolean;
        positiveBoxesSatisfied?: boolean;
        negativeBoxesSatisfied?: boolean;
        maskConstraintsSatisfied?: boolean;
        textConstraintsSatisfied?: boolean;
    };
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
    truncation?: {
        originalCount: number;
        retainedCount: number;
        policy: string;
    };
}
```

Candidate bounds and truncation MUST be deterministic and versioned. Raw model score semantics MUST be preserved; the UI must not relabel the score as calibrated correctness confidence.

## 6. Preserve the Ticket 04/05 lifecycle

```text
PromptState
→ AutoMaskProposalSet
→ proposal preview / later Ticket 07A decision
→ Editing Mask
→ Confirm Mask
→ Stable Mask
```

Prompt/proposal output is never Stable by itself.

Prompt changes MUST NOT:

- mutate the current Stable Mask;
- stale Evidence/Candidate before a new Stable Mask is confirmed;
- overwrite local Paint/Erase edits without an explicit replace/discard action;
- attach a late result to a newer RGB or Prompt revision.

Paint/Erase MUST NOT silently mutate PromptState. Prompt Brush MUST NOT directly mutate Editing Mask pixels.

## 7. Toolbar shell

Add a compact screenshot-tool-style toolbar adjacent to the selected AI View image.

Required behavior:

- selected tool is visually unambiguous;
- Prompt and Edit groups are visually separated;
- brush size applies only to the active brush tool;
- Box drag shows a live rectangle and never paints pixels;
- Text has an explicit Apply action;
- unsupported tools expose capability status;
- Prompt history and Mask edit history are independent and focus-routed;
- switching View/tool with uncommitted state follows the existing discard-warning policy.

## Acceptance criteria

### Domain and protocol

- [x] PromptState is per-view, immutable-by-revision, RGB-bound, digest-bound, and stale-result safe.
- [x] Point, Box, mask-constraint, and Text prompts have distinct validated payloads.
- [x] Positive/negative capability is explicit for each prompt family.
- [x] Adapter capabilities participate in request/result identity.
- [x] Unsupported prompt types are disabled/rejected, never silently dropped.
- [x] Same-attempt replay and new-attempt Retry match existing RGB/Mask semantics.
- [x] Proposal output preserves a bounded candidate set and declared score semantics.

### Interaction

- [x] Click/drag behavior is determined only by selected tool.
- [x] Default image drag does not implicitly paint the Mask.
- [x] Box drag cannot produce Paint/Erase edits.
- [x] Prompt Brush does not directly edit the bitmap.
- [x] Paint/Erase does not rewrite PromptState.
- [x] Prompt and Mask Undo/Redo are independent and focus-routed.
- [x] Restore Accepted Auto refers to an explicitly accepted proposal, not the current highest raw score.

### Lifecycle

- [x] Prompt revisions update proposal state only.
- [x] A proposal may seed Editing Mask but cannot become Stable without Confirm.
- [x] Existing Stable Mask and dependent Evidence remain current during unconfirmed work.
- [x] RGB/context/restart changes dispose incompatible Prompt/proposal state.
- [x] Local pixel edits supersede late inference unless the user explicitly applies the late proposal.

### Compatibility

- [x] Existing point-only SAM remains usable through the generic capability contract.
- [x] Text and negative Box/Text remain capability-gated.
- [x] No complete Contributor or formal P/N/V Evidence is required.
- [x] Existing Generated View automatic Stable Mask publication remains unchanged by this ticket.

## Failure / recovery criteria

- [x] Model/runtime failure preserves RGB, PromptState, prior Stable Mask, and local Editing Mask.
- [x] No-candidate output is proposal-unavailable, not View Render Failed.
- [x] Capability/protocol mismatch publishes no partial proposal set.
- [x] Cancellation/OOM publishes no partial proposal set.
- [x] Every failure permits Retry, prompt revision, or manual Empty → Paint recovery.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- Browser walkthrough: Point+/Point-, Box, Prompt Brush+/-, Paint/Erase, independent Undo/Redo
- Capability matrix and unsupported-tool fixtures
- Stale Prompt/RGB/context response tests
- Multi-candidate structural/truncation tests
- Existing point-only adapter regression
- Ticket 05 Confirm/Undo/Restore regression
- Ticket 07 assessment/publication regression

## Non-goals

- No final ranking or automatic ambiguity decision; Ticket 07A owns it.
- No claim that model score is correctness probability.
- No production Gaussian Evidence.
- No Generated View camera planning changes.
- No requirement to enable Text in Phase A.
- No direct Candidate or Native Selection mutation.

## Implementation record

Implemented on 2026-07-28:

- Added immutable, revisioned, exact-RGB-bound `PromptState` for positive/negative points, boxes, mask constraints, and text prompts, with a digest-bound adapter capability declaration.
- Replaced the Anchor point-mask transport with a generic, fully bound Mask proposal request/response contract and `POST /ai-select/mask-proposals`. Same-attempt replay remains idempotent; Retry mints a new attempt.
- Added deterministic `AutoMaskProposalSet` validation, a four-proposal bound, source-order truncation records, raw score-semantics preservation, explicit no-candidate state, and atomic fail-closed publication.
- Kept the installed point-only SAM adapter operational through an explicit singleton capability declaration. Its one proposal may seed Editing Mask for compatibility but cannot become Stable without Confirm Mask. Generated View automatic Mask publication was not changed.
- Split Prompt and Edit interactions in the AI View Dock. Point, Box, Prompt Brush / Mask Constraint, capability-gated Text, Paint, and Erase have selected-tool-only routing; Prompt and Mask histories remain independent.
- Preserved Stable Mask, Evidence, and Candidate currency until Confirm Mask. RGB/context/restart changes dispose incompatible Prompt/proposal state, and late or logically cancelled results cannot replace newer local work.
- Updated `CONTEXT.md`, Companion capability/route documentation, all nine locale sources, and editor/Companion protocol fixtures. Final Spec, ADRs, runtime lock, Evidence/Assessment policy, calibration, Generated View planning, and Ticket 07A behavior were not changed.

Validation on 2026-07-28:

- Clean baseline before implementation: 277 editor tests and 240 Companion tests passed; lint, locales, and build passed.
- `npm test`: 292 editor tests and 242 Companion tests passed.
- `npm run test:companion`: 242 tests passed.
- `npm run lint`: passed, including Prettier/ESLint compatibility for 184 TypeScript source files.
- `npm run lint:locales`: all eight translated locales match the 439-key English source.
- `npm run build`: passed with the pre-existing Sass deprecation and `mediabunny` warnings.
- Headless Chrome loaded the development build, rendered the editor, exposed the complete Prompt/Edit toolbar, and verified that unavailable adapter capabilities disable Prompt tools with an explicit reason. A live model/scene walkthrough was not possible without an installed locked Companion model and target scene; selected-tool pointer behavior and independent histories are covered by deterministic interaction/controller tests.

This is editor/Companion protocol and UI foundation work, not Ticket 07A ranking or production quality calibration. No production GPU/SAM quality validation ran, and no same-decision P/N/V Evidence or Complete Contributor path changed.

## Handoff to Ticket 07A

Ticket 04A is complete when Ticket 07A can consume:

```text
authoritative RGB
+ exact PromptState
+ bounded AutoMaskProposalSet
+ explicit adapter/model/policy/attempt identity
```

Ticket 07A completes the Three-Stage Anchor Mask Pipeline through ranking, ambiguity handling, acceptance/editing integration, and locked-runtime quality validation.
