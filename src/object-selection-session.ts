import {
    assertSceneSnapshot,
    isStableGaussianId,
    type SceneSnapshot,
    type SceneSnapshotBinding,
    type StableGaussianId
} from './scene-snapshot';

type ObjectSelectionMode = 'New' | 'Add' | 'Remove' | 'Refine';
type ObjectSelectionPromptPolarity = 'include' | 'exclude';

// One session permits at most this many successful Correction Rounds after
// the initial New result. Prompt staging, local rejection, service failure,
// and cancelled updates never consume the budget.
const MAX_CORRECTION_ROUNDS = 5;

interface ObjectSelectionConfirmOptions {
  // Confirming while Uncertain Gaussians remain requires the user to
  // acknowledge that only selected Stable Gaussian IDs will commit.
  acknowledgeUncertain?: boolean;
}

interface ObjectSelectionTarget {
  targetSplatId: string;
}

interface ObjectSelectionPrompt {
  promptId: string;
  viewId: string;
  frameDigest: string;
  frameWidth: number;
  frameHeight: number;
  xPx: number;
  yPx: number;
  polarity: ObjectSelectionPromptPolarity;
}

interface ObjectSelectionFrame {
  viewId: string;
  frameDigest: string;
  width: number;
  height: number;
  imagePngBase64?: string;
}

interface ObjectSelectionFrameSet {
  frameSetId: string;
  frameSetVersion: string;
  orderedViews: readonly ObjectSelectionFrame[];
}

interface ObjectSelectionSessionStart {
  target: ObjectSelectionTarget;
  prompt: ObjectSelectionPrompt;
  scene: SceneSnapshotBinding;
  requestContext: ObjectSelectionRequestContext;
}

interface ObjectSelectionServiceSessionStart {
  target: ObjectSelectionTarget;
  prompt: ObjectSelectionPrompt;
  snapshot: SceneSnapshot;
  requestContext: ObjectSelectionRequestContext;
}

// These values are fixed for one session before the first service request.
// Keeping them in the editor-owned start input makes every later preview
// independently checkable without granting the service editor authority.
interface ObjectSelectionRequestContext {
  deterministicSeed: string;
  frameSetVersion: string;
  frameSet: ObjectSelectionFrameSet;
  modelManifestDigest: string;
}

interface ObjectSelectionPromptLogEntry {
  operation: ObjectSelectionMode;
  prompt: ObjectSelectionPrompt;
}

interface SelectionResultIds {
  selectedIds: readonly StableGaussianId[];
  uncertainIds: readonly StableGaussianId[];
  rejectedIds: readonly StableGaussianId[];
}

interface CandidateObjectSelection extends SelectionResultIds {
  lockedIdsFiltered: number;
}

// A single versioned identity tuple crosses the editor/Companion boundary.
// Requests and every terminal/cache response use this exact structure.
interface ObjectSelectionPreviewBindings {
  sessionId: string;
  requestId: string;
  targetSplatId: string;
  sceneId: string;
  sceneVersion: string;
  operation: ObjectSelectionMode;
  correctionRound: number;
  deterministicSeed: string;
  promptLogRevision: number;
  frameSetVersion: string;
  renderConfigVersion: string;
  modelManifestDigest: string;
}

interface ObjectSelectionPreviewRequest extends ObjectSelectionPreviewBindings {
  target: ObjectSelectionTarget;
  promptLog: readonly ObjectSelectionPromptLogEntry[];
  frameSet: ObjectSelectionFrameSet;
  snapshot: SceneSnapshot;
}

type SelectionServiceMaskFrameStatus =
  'accepted' | 'not_found' | 'rejected' | 'error';

interface SelectionServiceMaskFrame {
  viewId: string;
  status: SelectionServiceMaskFrameStatus;
  binaryMask?: Record<string, unknown>;
  rejectionReason?: string;
}

interface SelectionServiceMaskTrack {
  trackId: string;
  role: 'include' | 'exclude';
  frames: readonly SelectionServiceMaskFrame[];
}

interface SelectionServiceMaskSet {
  status: 'complete';
  requestId: string;
  sessionId: string;
  promptLogRevision: number;
  frameSetVersion: string;
  modelManifestDigest: string;
  threshold: number;
  tracks: readonly SelectionServiceMaskTrack[];
}

type SelectionEvidenceClassification = 'selected' | 'rejected' | 'uncertain';
type SelectionEvidenceUncertaintyReason =
  'unobserved' | 'insufficient_observation' | 'undecided_or_conflicting';

interface SelectionEvidencePolicy {
  id: 'selection-evidence-policy/v1';
  renderConfigVersion: string;
  contributorSemantics: 'alpha-times-transmittance/v1';
  evidenceScale: 'contributor-mass/v1';
  betaPrior: {
    alpha: number;
    beta: number;
  };
  minimumEffectiveObservation: number;
  selectedPosteriorThreshold: number;
  rejectedPosteriorThreshold: number;
}

interface SelectionEvidenceRecord {
  stableId: StableGaussianId;
  positiveEvidence: number;
  negativeEvidence: number;
  effectiveObservation: number;
  posterior: number;
  uncertaintyReason: SelectionEvidenceUncertaintyReason | null;
  classification: SelectionEvidenceClassification;
}

interface SelectionServiceEvidenceSnapshot extends ObjectSelectionPreviewBindings {
  frameSetId: string;
  policy: SelectionEvidencePolicy;
  records: readonly SelectionEvidenceRecord[];
}

type SelectionCoverageStatus = 'sufficient' | 'insufficient_coverage';

// Deliberately limited to user-actionable facts. The Companion retains camera,
// mask, and quality diagnostics in its run artifact rather than displaying
// them in the editor.
interface SelectionServiceCoverageReport {
  frameSetVersion: string;
  renderConfigVersion: string;
  attemptedViews: number;
  acceptedViews: number;
  rejectedViewCount: number;
  status: SelectionCoverageStatus;
}

interface SelectionServicePreviewResponse
  extends ObjectSelectionPreviewBindings, SelectionResultIds {
  status: 'complete';
  frameSet: ObjectSelectionFrameSet;
  maskSet: SelectionServiceMaskSet;
  evidenceSnapshot: SelectionServiceEvidenceSnapshot;
  coverageReport: SelectionServiceCoverageReport;
}

interface SelectionServiceAdapter {
  openSession(start: ObjectSelectionServiceSessionStart): Promise<string>;
  updatePreview(
    request: ObjectSelectionPreviewRequest
  ): Promise<SelectionServicePreviewResponse>;
  cancelUpdate(sessionId: string, requestId: string): Promise<void>;
  closeSession(sessionId: string): Promise<void>;
}

interface ObjectSelectionSessionEditor {
  captureSelection(): readonly StableGaussianId[];

  // This is the only path that may create an editor selection-history entry.
  // Its editor adapter must use the existing SelectOp transition.
  commitSelection(selectedIds: readonly StableGaussianId[]): Promise<void>;

  // Restoring an entry selection is presentation recovery, not a commit.
  // It must not create a selection-history entry.
  restoreSelection(entrySelection: readonly StableGaussianId[]): Promise<void>;
}

type ObjectSelectionSessionStatus =
  | 'idle'
  | 'opening'
  | 'ready'
  | 'previewing'
  | 'cancellingUpdate'
  | 'preview'
  | 'confirming'
  | 'cancelling'
  | 'closing'
  | 'closeFailed';

interface ObjectSelectionSessionState {
  status: ObjectSelectionSessionStatus;
  candidate: CandidateObjectSelection | null;
  coverage: SelectionServiceCoverageReport | null;
  mode: ObjectSelectionMode;
  promptCount: number;
  pendingPrompts: readonly ObjectSelectionPromptLogEntry[];
  lockedIdsFiltered: number;
  correctionRoundsUsed: number;
  correctionRoundsLimit: number;
}

type ObjectSelectionSessionListener = (
  state: ObjectSelectionSessionState
) => void;

// The toolbar, panel, and workflow tests cross this interface. The service and
// editor adapters remain implementation dependencies of the session module.
interface ObjectSelectionSessionInterface {
  readonly state: ObjectSelectionSessionState;

  subscribe(listener: ObjectSelectionSessionListener): () => void;
  startNew(start: ObjectSelectionSessionStart): Promise<void>;
  setMode(mode: ObjectSelectionMode): void;
  stagePrompt(prompt: ObjectSelectionPrompt): void;
  undoLastPendingPrompt(): boolean;
  clearPendingPrompts(): void;
  updatePreview(): Promise<void>;
  cancelUpdate(): Promise<void>;
  confirm(options?: ObjectSelectionConfirmOptions): Promise<void>;
  cancel(): Promise<void>;
  retryCleanup(): Promise<void>;
}

interface ExpectedMaskTrack {
  trackId: string;
  role: 'include' | 'exclude';
}

// The chronological independent Mask Track plan a complete Mask Set must
// replay. New and Refine prompts update the primary include track; each
// consecutive run of Add or Remove entries forms its own include or exclude
// track. Composition order follows each track's latest Prompt Log entry, so
// a later Add can restore a region an earlier Remove excluded and a later
// Remove can exclude it again. Both runtimes derive and enforce this same
// plan from the authoritative Prompt Log.
const deriveMaskTrackPlan = (
    promptLog: readonly ObjectSelectionPromptLogEntry[]
): ExpectedMaskTrack[] => {
  interface PlannedMaskTrack extends ExpectedMaskTrack {
    lastEntryIndex: number;
  }
  const invalidLog = () => new Error(
      'An Object Selection Prompt Log starts with exactly one New operation.'
  );
  const primary: PlannedMaskTrack = {
      trackId: 'primary',
      role: 'include',
      lastEntryIndex: -1
  };
  const independent: PlannedMaskTrack[] = [];
  let addCount = 0;
  let removeCount = 0;
  let openRun: PlannedMaskTrack | null = null;
  let sawNew = false;
  promptLog.forEach((entry, index) => {
      switch (entry.operation) {
          case 'New':
              if (index !== 0) {
                  throw invalidLog();
              }
              sawNew = true;
              primary.lastEntryIndex = index;
              openRun = null;
              break;
          case 'Refine':
              primary.lastEntryIndex = index;
              openRun = null;
              break;
          case 'Add':
              if (openRun === null || openRun.role !== 'include') {
                  addCount += 1;
                  openRun = {
                      trackId: `add-${addCount}`,
                      role: 'include',
                      lastEntryIndex: index
                  };
                  independent.push(openRun);
              }
              openRun.lastEntryIndex = index;
              break;
          case 'Remove':
              if (openRun === null || openRun.role !== 'exclude') {
                  removeCount += 1;
                  openRun = {
                      trackId: `remove-${removeCount}`,
                      role: 'exclude',
                      lastEntryIndex: index
                  };
                  independent.push(openRun);
              }
              openRun.lastEntryIndex = index;
              break;
          default:
              throw new Error(
                  'An Object Selection Prompt Log supports New, Add, Remove, and Refine operations only.'
              );
      }
  });
  if (!sawNew) {
      throw invalidLog();
  }
  return [...independent, primary]
  .sort((left, right) => left.lastEntryIndex - right.lastEntryIndex)
  .map(({ trackId, role }) => ({ trackId, role }));
};

interface ActivePreview {
  requestId: string;
  previousStatus: 'ready' | 'preview';
  cancelled: boolean;
  submittedPrompts: ObjectSelectionPromptLogEntry[];
}

const copyTarget = (target: ObjectSelectionTarget): ObjectSelectionTarget => {
    return {
        targetSplatId: target.targetSplatId
    };
};

const copyPreviewBindings = (
    bindings: ObjectSelectionPreviewBindings
): ObjectSelectionPreviewBindings => {
    return {
        sessionId: bindings.sessionId,
        requestId: bindings.requestId,
        targetSplatId: bindings.targetSplatId,
        sceneId: bindings.sceneId,
        sceneVersion: bindings.sceneVersion,
        operation: bindings.operation,
        correctionRound: bindings.correctionRound,
        deterministicSeed: bindings.deterministicSeed,
        promptLogRevision: bindings.promptLogRevision,
        frameSetVersion: bindings.frameSetVersion,
        renderConfigVersion: bindings.renderConfigVersion,
        modelManifestDigest: bindings.modelManifestDigest
    };
};

const previewBindingsFromRequest = (
    request: ObjectSelectionPreviewRequest
): ObjectSelectionPreviewBindings => copyPreviewBindings(request);

const anchorFrameSetId = (targetSplatId: string) => `${targetSplatId}:anchor`;

const anchorFrameSetVersion = (targetSplatId: string, frameDigest: string) => {
    return `${anchorFrameSetId(targetSplatId)}:${frameDigest}`;
};

const previewBindingsMatch = (
    bindings: ObjectSelectionPreviewBindings,
    request: ObjectSelectionPreviewRequest
) => {
    const expected = previewBindingsFromRequest(request);
    return (
        bindings.sessionId === expected.sessionId &&
    bindings.requestId === expected.requestId &&
    bindings.targetSplatId === expected.targetSplatId &&
    bindings.sceneId === expected.sceneId &&
    bindings.sceneVersion === expected.sceneVersion &&
    bindings.operation === expected.operation &&
    bindings.correctionRound === expected.correctionRound &&
    bindings.deterministicSeed === expected.deterministicSeed &&
    bindings.promptLogRevision === expected.promptLogRevision &&
    bindings.frameSetVersion === expected.frameSetVersion &&
    bindings.renderConfigVersion === expected.renderConfigVersion &&
    bindings.modelManifestDigest === expected.modelManifestDigest
    );
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonNegativeInteger = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isInteger(value) && value >= 0;
};

const isFrameDigest = (value: unknown): value is string => {
    return (
        typeof value === 'string' && value.startsWith('sha256:') && value.length > 7
    );
};

const incompleteFrameSet = () => {
    return new Error(
        'The Selection Service Companion returned an incomplete, version-bound Frame Set.'
    );
};

function assertPreviewFrameSet(
    value: unknown,
    request: ObjectSelectionPreviewRequest
): asserts value is ObjectSelectionFrameSet {
    if (
        !isRecord(value) ||
    typeof value.frameSetId !== 'string' ||
    !value.frameSetId ||
    typeof value.frameSetVersion !== 'string' ||
    !value.frameSetVersion ||
    !Array.isArray(value.orderedViews) ||
    value.orderedViews.length === 0
    ) {
        throw incompleteFrameSet();
    }
    const viewIds = new Set<string>();
    value.orderedViews.forEach((view) => {
        if (
            !isRecord(view) ||
      typeof view.viewId !== 'string' ||
      !view.viewId ||
      viewIds.has(view.viewId) ||
      !isFrameDigest(view.frameDigest) ||
      !isNonNegativeInteger(view.width) ||
      view.width === 0 ||
      !isNonNegativeInteger(view.height) ||
      view.height === 0
        ) {
            throw incompleteFrameSet();
        }
        viewIds.add(view.viewId);
    });
    const anchor = request.promptLog.find(
        entry => entry.operation === 'New'
    )?.prompt;
    const returnedAnchor =
    anchor === undefined ? undefined : value.orderedViews[0];
    if (
        anchor === undefined ||
    !isRecord(returnedAnchor) ||
    returnedAnchor.viewId !== anchor.viewId ||
    returnedAnchor.frameDigest !== anchor.frameDigest ||
    returnedAnchor.width !== anchor.frameWidth ||
    returnedAnchor.height !== anchor.frameHeight
    ) {
        throw incompleteFrameSet();
    }
}

const copyCoverageReport = (
    coverage: SelectionServiceCoverageReport
): SelectionServiceCoverageReport => ({
    frameSetVersion: coverage.frameSetVersion,
    renderConfigVersion: coverage.renderConfigVersion,
    attemptedViews: coverage.attemptedViews,
    acceptedViews: coverage.acceptedViews,
    rejectedViewCount: coverage.rejectedViewCount,
    status: coverage.status
});

function assertCoverageReport(
    value: unknown,
    request: ObjectSelectionPreviewRequest
): asserts value is SelectionServiceCoverageReport {
    if (
        !isRecord(value) ||
    value.frameSetVersion !== request.frameSetVersion ||
    value.renderConfigVersion !== request.renderConfigVersion ||
    !isNonNegativeInteger(value.attemptedViews) ||
    !isNonNegativeInteger(value.acceptedViews) ||
    !isNonNegativeInteger(value.rejectedViewCount) ||
    value.acceptedViews > value.attemptedViews ||
    value.rejectedViewCount > value.attemptedViews ||
    (value.status !== 'sufficient' && value.status !== 'insufficient_coverage')
    ) {
        throw new Error(
            'The Selection Service Companion returned an incomplete, version-bound Coverage Report.'
        );
    }
}

const incompleteMaskSet = () => {
    return new Error(
        'The Selection Service Companion returned an incomplete, version-bound Mask Set.'
    );
};

const selectionEvidencePolicyV1 = {
    id: 'selection-evidence-policy/v1',
    contributorSemantics: 'alpha-times-transmittance/v1',
    evidenceScale: 'contributor-mass/v1',
    betaPrior: {
        alpha: 1,
        beta: 1
    },
    minimumEffectiveObservation: 0.1,
    selectedPosteriorThreshold: 0.8,
    rejectedPosteriorThreshold: 0.2
} as const;

const incompleteEvidenceSnapshot = () => {
    return new Error(
        'The Selection Service Companion returned an incomplete, version-bound Evidence Snapshot.'
    );
};

const sameFiniteNumber = (actual: unknown, expected: number) => {
    return (
        typeof actual === 'number' &&
    Number.isFinite(actual) &&
    Math.abs(actual - expected) <= 1e-12
    );
};

const evidenceClassification = (
    positiveEvidence: number,
    negativeEvidence: number
): SelectionEvidenceClassification => {
    const effectiveObservation = positiveEvidence + negativeEvidence;
    const posterior =
    (1 + positiveEvidence) / (2 + positiveEvidence + negativeEvidence);
    if (
        effectiveObservation >=
      selectionEvidencePolicyV1.minimumEffectiveObservation &&
    posterior >= selectionEvidencePolicyV1.selectedPosteriorThreshold
    ) {
        return 'selected';
    }
    if (
        effectiveObservation >=
      selectionEvidencePolicyV1.minimumEffectiveObservation &&
    posterior <= selectionEvidencePolicyV1.rejectedPosteriorThreshold
    ) {
        return 'rejected';
    }
    return 'uncertain';
};

const evidenceUncertaintyReason = (
    positiveEvidence: number,
    negativeEvidence: number,
    classification: SelectionEvidenceClassification
): SelectionEvidenceUncertaintyReason | null => {
    if (classification !== 'uncertain') {
        return null;
    }
    const effectiveObservation = positiveEvidence + negativeEvidence;
    if (effectiveObservation === 0) {
        return 'unobserved';
    }
    if (
        effectiveObservation < selectionEvidencePolicyV1.minimumEffectiveObservation
    ) {
        return 'insufficient_observation';
    }
    return 'undecided_or_conflicting';
};

function assertEvidenceSnapshot(
    value: unknown,
    request: ObjectSelectionPreviewRequest
): asserts value is SelectionServiceEvidenceSnapshot {
    if (
        !isRecord(value) ||
    value.frameSetId !== request.frameSet.frameSetId ||
    !previewBindingsMatch(
      value as unknown as ObjectSelectionPreviewBindings,
      request
    ) ||
    !isRecord(value.policy) ||
    value.policy.id !== selectionEvidencePolicyV1.id ||
    value.policy.renderConfigVersion !== request.renderConfigVersion ||
    value.policy.contributorSemantics !==
      selectionEvidencePolicyV1.contributorSemantics ||
    value.policy.evidenceScale !== selectionEvidencePolicyV1.evidenceScale ||
    !isRecord(value.policy.betaPrior) ||
    !sameFiniteNumber(
        value.policy.betaPrior.alpha,
        selectionEvidencePolicyV1.betaPrior.alpha
    ) ||
    !sameFiniteNumber(
        value.policy.betaPrior.beta,
        selectionEvidencePolicyV1.betaPrior.beta
    ) ||
    !sameFiniteNumber(
        value.policy.minimumEffectiveObservation,
        selectionEvidencePolicyV1.minimumEffectiveObservation
    ) ||
    !sameFiniteNumber(
        value.policy.selectedPosteriorThreshold,
        selectionEvidencePolicyV1.selectedPosteriorThreshold
    ) ||
    !sameFiniteNumber(
        value.policy.rejectedPosteriorThreshold,
        selectionEvidencePolicyV1.rejectedPosteriorThreshold
    ) ||
    !Array.isArray(value.records)
    ) {
        throw incompleteEvidenceSnapshot();
    }

    const knownIds = new Set(
        request.snapshot.gaussians.map(gaussian => gaussian.stableId)
    );
    if (value.records.length !== knownIds.size) {
        throw incompleteEvidenceSnapshot();
    }
    let previousId = -1;
    value.records.forEach((record) => {
        if (
            !isRecord(record) ||
      !isStableGaussianId(record.stableId) ||
      !knownIds.has(record.stableId) ||
      record.stableId <= previousId ||
      typeof record.positiveEvidence !== 'number' ||
      !Number.isFinite(record.positiveEvidence) ||
      record.positiveEvidence < 0 ||
      typeof record.negativeEvidence !== 'number' ||
      !Number.isFinite(record.negativeEvidence) ||
      record.negativeEvidence < 0 ||
      typeof record.effectiveObservation !== 'number' ||
      !Number.isFinite(record.effectiveObservation) ||
      typeof record.posterior !== 'number' ||
      !Number.isFinite(record.posterior) ||
      !['selected', 'rejected', 'uncertain'].includes(
          String(record.classification)
      )
        ) {
            throw incompleteEvidenceSnapshot();
        }
        const positiveEvidence = record.positiveEvidence;
        const negativeEvidence = record.negativeEvidence;
        const effectiveObservation = positiveEvidence + negativeEvidence;
        const posterior =
      (1 + positiveEvidence) / (2 + positiveEvidence + negativeEvidence);
        const classification = evidenceClassification(
            positiveEvidence,
            negativeEvidence
        );
        const uncertaintyReason = evidenceUncertaintyReason(
            positiveEvidence,
            negativeEvidence,
            classification
        );
        if (
            !sameFiniteNumber(record.effectiveObservation, effectiveObservation) ||
      !sameFiniteNumber(record.posterior, posterior) ||
      record.classification !== classification ||
      record.uncertaintyReason !== uncertaintyReason
        ) {
            throw incompleteEvidenceSnapshot();
        }
        previousId = record.stableId;
    });
}

const assertSparsePointMask = (
    value: Record<string, unknown>,
    frame: ObjectSelectionFrame
) => {
    if (
        value.width !== frame.width ||
    value.height !== frame.height ||
    !Array.isArray(value.foregroundPixels) ||
    value.foregroundPixels.length === 0
    ) {
        throw incompleteMaskSet();
    }
    let previousPixel = -1;
    value.foregroundPixels.forEach((pixel) => {
        if (
            !Array.isArray(pixel) ||
      pixel.length !== 2 ||
      !isNonNegativeInteger(pixel[0]) ||
      !isNonNegativeInteger(pixel[1])
        ) {
            throw incompleteMaskSet();
        }
        const [xPx, yPx] = pixel;
        if (xPx >= frame.width || yPx >= frame.height) {
            throw incompleteMaskSet();
        }
        const currentPixel = yPx * frame.width + xPx;
        if (currentPixel <= previousPixel) {
            throw incompleteMaskSet();
        }
        previousPixel = currentPixel;
    });
};

const assertBitsetMask = (
    value: Record<string, unknown>,
    frame: ObjectSelectionFrame
) => {
    if (
        value.width !== frame.width ||
    value.height !== frame.height ||
    typeof value.data !== 'string' ||
    !/^(?:[a-z0-9+/]{4})*(?:[a-z0-9+/]{2}==|[a-z0-9+/]{3}=)?$/i.test(value.data)
    ) {
        throw incompleteMaskSet();
    }
    let data: Uint8Array;
    try {
        data = Uint8Array.from(atob(value.data), character => character.charCodeAt(0)
        );
    } catch (error) {
        throw incompleteMaskSet();
    }
    const pixelCount = frame.width * frame.height;
    if (
        data.length !== Math.ceil(pixelCount / 8) ||
    !data.some(byte => byte !== 0)
    ) {
        throw incompleteMaskSet();
    }
    const trailingBits = pixelCount % 8;
    if (
        trailingBits !== 0 &&
    ((data.at(-1) ?? 0) & ~((1 << trailingBits) - 1)) !== 0
    ) {
        throw incompleteMaskSet();
    }
};

const assertBinaryMask = (value: unknown, frame: ObjectSelectionFrame) => {
    if (!isRecord(value)) {
        throw incompleteMaskSet();
    }
    if (value.encoding === 'sparse-points-v1') {
        assertSparsePointMask(value, frame);
        return;
    }
    if (value.encoding === 'bitset-lsb-v1') {
        assertBitsetMask(value, frame);
        return;
    }
    throw incompleteMaskSet();
};

function assertCompleteMaskSet(
    value: unknown,
    request: ObjectSelectionPreviewRequest
): asserts value is SelectionServiceMaskSet {
    if (
        !isRecord(value) ||
    value.status !== 'complete' ||
    value.requestId !== request.requestId ||
    value.sessionId !== request.sessionId ||
    value.promptLogRevision !== request.promptLogRevision ||
    value.frameSetVersion !== request.frameSetVersion ||
    value.modelManifestDigest !== request.modelManifestDigest ||
    typeof value.threshold !== 'number' ||
    !Number.isFinite(value.threshold) ||
    value.threshold < 0 ||
    value.threshold > 1 ||
    !Array.isArray(value.tracks) ||
    value.tracks.length === 0
    ) {
        throw incompleteMaskSet();
    }

    const expectedFrames = request.frameSet.orderedViews;
    const expectedTracks = deriveMaskTrackPlan(request.promptLog);
    if (value.tracks.length !== expectedTracks.length) {
        throw incompleteMaskSet();
    }
    const trackIds = new Set<string>();
    let primaryFrames: Record<string, unknown>[] | null = null;
    value.tracks.forEach((track, trackIndex) => {
        const expectedTrack = expectedTracks[trackIndex];
        if (
            !isRecord(track) ||
      typeof track.trackId !== 'string' ||
      !track.trackId ||
      (track.role !== 'include' && track.role !== 'exclude') ||
      !Array.isArray(track.frames) ||
      track.frames.length !== expectedFrames.length ||
      trackIds.has(track.trackId) ||
      track.trackId !== expectedTrack.trackId ||
      track.role !== expectedTrack.role
        ) {
            throw incompleteMaskSet();
        }
        trackIds.add(track.trackId);
        const frames: Record<string, unknown>[] = [];
        track.frames.forEach((maskFrame, index) => {
            const expectedFrame = expectedFrames[index];
            if (
                !isRecord(maskFrame) ||
        maskFrame.viewId !== expectedFrame.viewId ||
        !['accepted', 'not_found', 'rejected', 'error'].includes(
            String(maskFrame.status)
        )
            ) {
                throw incompleteMaskSet();
            }
            if (maskFrame.status === 'accepted') {
                assertBinaryMask(maskFrame.binaryMask, expectedFrame);
            } else if (
                'binaryMask' in maskFrame ||
        typeof maskFrame.rejectionReason !== 'string' ||
        !maskFrame.rejectionReason.trim()
            ) {
                throw incompleteMaskSet();
            }
            frames.push(maskFrame);
        });
        if (track.trackId === 'primary') {
            if (track.role !== 'include' || primaryFrames !== null) {
                throw incompleteMaskSet();
            }
            primaryFrames = frames;
        }
    });

    const anchorViewId = request.promptLog.find(
        entry => entry.operation === 'New'
    )?.prompt.viewId;
    const anchorFrame = primaryFrames?.find(
        frame => frame.viewId === anchorViewId
    );
    if (anchorViewId === undefined || anchorFrame?.status !== 'accepted') {
        throw incompleteMaskSet();
    }
}

const copyPrompt = (prompt: ObjectSelectionPrompt): ObjectSelectionPrompt => {
    return {
        promptId: prompt.promptId,
        viewId: prompt.viewId,
        frameDigest: prompt.frameDigest,
        frameWidth: prompt.frameWidth,
        frameHeight: prompt.frameHeight,
        xPx: prompt.xPx,
        yPx: prompt.yPx,
        polarity: prompt.polarity
    };
};

const copyFrameSet = (
    frameSet: ObjectSelectionFrameSet
): ObjectSelectionFrameSet => {
    return {
        frameSetId: frameSet.frameSetId,
        frameSetVersion: frameSet.frameSetVersion,
        orderedViews: frameSet.orderedViews.map(view => ({
            viewId: view.viewId,
            frameDigest: view.frameDigest,
            width: view.width,
            height: view.height,
            ...(view.imagePngBase64 === undefined ?
                {} :
                {
                    imagePngBase64: view.imagePngBase64
                })
        }))
    };
};

const requestWithFrameSet = (
    request: ObjectSelectionPreviewRequest,
    frameSet: ObjectSelectionFrameSet
): ObjectSelectionPreviewRequest => {
    const copiedFrameSet = copyFrameSet(frameSet);
    return {
        ...request,
        frameSetVersion: copiedFrameSet.frameSetVersion,
        frameSet: copiedFrameSet
    };
};

const copyRequestContext = (
    requestContext: ObjectSelectionRequestContext
): ObjectSelectionRequestContext => {
    return {
        deterministicSeed: requestContext.deterministicSeed,
        frameSetVersion: requestContext.frameSetVersion,
        frameSet: copyFrameSet(requestContext.frameSet),
        modelManifestDigest: requestContext.modelManifestDigest
    };
};

const copyStart = (
    start: ObjectSelectionSessionStart
): ObjectSelectionSessionStart => {
    return {
        target: copyTarget(start.target),
        prompt: copyPrompt(start.prompt),
        scene: start.scene,
        requestContext: copyRequestContext(start.requestContext)
    };
};

const copyServiceStart = (
    start: ObjectSelectionServiceSessionStart
): ObjectSelectionServiceSessionStart => {
    return {
        target: copyTarget(start.target),
        prompt: copyPrompt(start.prompt),
        snapshot: start.snapshot,
        requestContext: copyRequestContext(start.requestContext)
    };
};

const copyPromptLogEntry = (
    entry: ObjectSelectionPromptLogEntry
): ObjectSelectionPromptLogEntry => {
    return {
        operation: entry.operation,
        prompt: copyPrompt(entry.prompt)
    };
};

const copyCandidate = (
    candidate: CandidateObjectSelection
): CandidateObjectSelection => {
    return {
        selectedIds: [...candidate.selectedIds],
        uncertainIds: [...candidate.uncertainIds],
        rejectedIds: [...candidate.rejectedIds],
        lockedIdsFiltered: candidate.lockedIdsFiltered
    };
};

class ObjectSelectionSession implements ObjectSelectionSessionInterface {
    private selectionService: SelectionServiceAdapter;
    private editor: ObjectSelectionSessionEditor;
    private sessionId: string | null = null;
    private entrySelection: StableGaussianId[] | null = null;
    private target: ObjectSelectionTarget | null = null;
    private scene: SceneSnapshotBinding | null = null;
    private snapshot: SceneSnapshot | null = null;
    private requestContext: ObjectSelectionRequestContext | null = null;
    private promptLog: ObjectSelectionPromptLogEntry[] = [];
    private pendingPrompts: ObjectSelectionPromptLogEntry[] = [];
    private candidateSelection: CandidateObjectSelection | null = null;
    private coverageReport: SelectionServiceCoverageReport | null = null;
    private sessionStatus: ObjectSelectionSessionStatus = 'idle';
    private mode: ObjectSelectionMode = 'New';
    private requestCount = 0;
    private successfulPreviewCount = 0;
    private activePreview: ActivePreview | null = null;
    private listeners = new Set<ObjectSelectionSessionListener>();

    constructor(options: {
    selectionService: SelectionServiceAdapter;
    editor: ObjectSelectionSessionEditor;
  }) {
        this.selectionService = options.selectionService;
        this.editor = options.editor;
    }

    get state(): ObjectSelectionSessionState {
        return {
            status: this.sessionStatus,
            candidate: this.candidateSelection ?
                copyCandidate(this.candidateSelection) :
                null,
            coverage: this.coverageReport ?
                copyCoverageReport(this.coverageReport) :
                null,
            mode: this.mode,
            promptCount: this.promptLog.length + this.pendingPrompts.length,
            pendingPrompts: this.pendingPrompts.map(copyPromptLogEntry),
            lockedIdsFiltered: this.candidateSelection?.lockedIdsFiltered ?? 0,
            correctionRoundsUsed: this.correctionRoundsUsed(),
            correctionRoundsLimit: MAX_CORRECTION_ROUNDS
        };
    }

    subscribe(listener: ObjectSelectionSessionListener) {
        this.listeners.add(listener);
        listener(this.state);

        return () => {
            this.listeners.delete(listener);
        };
    }

    async startNew(start: ObjectSelectionSessionStart) {
        this.requireStatus('idle');

        const copiedStart = copyStart(start);
        const snapshot = copiedStart.scene.getSnapshot();
        assertSceneSnapshot(snapshot);
        this.assertRequestContext(copiedStart.requestContext);
        this.assertPromptFrame(copiedStart.prompt, copiedStart.requestContext);
        this.entrySelection = [...this.editor.captureSelection()];
        this.target = copiedStart.target;
        this.scene = copiedStart.scene;
        this.snapshot = snapshot;
        this.requestContext = copiedStart.requestContext;
        this.promptLog = [
            {
                operation: 'New',
                prompt: copiedStart.prompt
            }
        ];
        this.pendingPrompts = [];
        this.coverageReport = null;
        this.mode = 'New';
        this.requestCount = 0;
        this.successfulPreviewCount = 0;
        this.setStatus('opening');

        try {
            this.sessionId = await this.selectionService.openSession(
                copyServiceStart({
                    target: copiedStart.target,
                    prompt: copiedStart.prompt,
                    snapshot,
                    requestContext: copiedStart.requestContext
                })
            );
            this.setStatus('ready');
        } catch (error) {
            this.clearSessionState();
            this.setStatus('idle');
            throw error;
        }
    }

    setMode(mode: ObjectSelectionMode) {
        this.requireStatus('ready', 'preview');
        this.mode = mode;
        this.publishState();
    }

    stagePrompt(prompt: ObjectSelectionPrompt) {
        this.requireStatus('ready', 'preview');
        if (this.mode === 'New') {
            throw new Error(
                'Object Selection corrections require Add, Remove, or Refine mode.'
            );
        }
        this.assertPromptFrame(prompt, this.requireRequestContext());
        this.pendingPrompts.push({
            operation: this.mode,
            prompt: copyPrompt(prompt)
        });
        this.publishState();
    }

    undoLastPendingPrompt() {
        this.requireStatus('ready', 'preview');
        if (this.pendingPrompts.length === 0) {
            return false;
        }
        this.pendingPrompts.pop();
        this.publishState();
        return true;
    }

    clearPendingPrompts() {
        this.requireStatus('ready', 'preview');
        if (this.pendingPrompts.length === 0) {
            return;
        }
        this.pendingPrompts = [];
        this.publishState();
    }

    async updatePreview() {
        const previousStatus = this.requirePreviewStatus();
        this.requireCurrentSnapshot();
        if (this.correctionRoundsUsed() >= MAX_CORRECTION_ROUNDS) {
            throw new Error(
                'Object Selection Session used all five successful Correction Rounds; Confirm Current or Cancel.'
            );
        }

        const submittedPrompts = this.pendingPrompts.map(copyPromptLogEntry);
        const promptLog = [
            ...this.promptLog.map(copyPromptLogEntry),
            ...submittedPrompts.map(copyPromptLogEntry)
        ];
        const operation = promptLog[promptLog.length - 1].operation;
        const activePreview: ActivePreview = {
            requestId: `request-${++this.requestCount}`,
            previousStatus,
            cancelled: false,
            submittedPrompts
        };
        this.pendingPrompts = [];
        this.activePreview = activePreview;
        this.setStatus('previewing');

        const request: ObjectSelectionPreviewRequest = {
            sessionId: this.requireSessionId(),
            requestId: activePreview.requestId,
            target: copyTarget(this.requireTarget()),
            targetSplatId: this.requireTarget().targetSplatId,
            sceneId: this.requireSnapshot().sceneId,
            sceneVersion: this.requireSnapshot().sceneVersion,
            operation,
            correctionRound: this.successfulPreviewCount,
            deterministicSeed: this.requireRequestContext().deterministicSeed,
            promptLogRevision: promptLog.length,
            frameSetVersion: this.requireRequestContext().frameSetVersion,
            renderConfigVersion: this.requireSnapshot().renderConfiguration.version,
            modelManifestDigest: this.requireRequestContext().modelManifestDigest,
            promptLog,
            frameSet: copyFrameSet(this.requireRequestContext().frameSet),
            snapshot: this.requireSnapshot()
        };

        try {
            const response = await this.selectionService.updatePreview(request);
            if (this.activePreview !== activePreview || activePreview.cancelled) {
                return;
            }

            this.requireCurrentSnapshot();
            const effectiveRequest = this.validatePreviewResponse(response, request);
            this.promptLog.push(
                ...activePreview.submittedPrompts.map(copyPromptLogEntry)
            );
            this.candidateSelection = copyCandidate(this.filterLockedIds(response));
            this.requestContext = {
                deterministicSeed: this.requireRequestContext().deterministicSeed,
                frameSetVersion: effectiveRequest.frameSetVersion,
                frameSet: copyFrameSet(effectiveRequest.frameSet),
                modelManifestDigest: this.requireRequestContext().modelManifestDigest
            };
            this.coverageReport = copyCoverageReport(response.coverageReport);
            this.successfulPreviewCount += 1;
            this.setStatus('preview');
        } catch (error) {
            if (!activePreview.cancelled) {
                this.restorePendingPrompts(activePreview);
                this.setStatus(activePreview.previousStatus);
                throw error;
            }
        } finally {
            if (this.activePreview === activePreview) {
                this.activePreview = null;
            }
        }
    }

    async cancelUpdate() {
        this.requireStatus('previewing');

        const activePreview = this.requireActivePreview();
        activePreview.cancelled = true;
        this.setStatus('cancellingUpdate');

        try {
            await this.selectionService.cancelUpdate(
                this.requireSessionId(),
                activePreview.requestId
            );
        } catch (error) {
            // Once cancellation has been requested, never let a racing result
            // replace the preceding usable Candidate Object Selection. A failed
            // abort is recoverable by submitting a fresh preview request.
            activePreview.cancelled = true;
            this.restorePendingPrompts(activePreview);
            if (this.activePreview === activePreview) {
                this.activePreview = null;
            }
            if (this.sessionStatus === 'cancellingUpdate') {
                this.setStatus(activePreview.previousStatus);
            }
            throw error;
        }

        if (this.activePreview === activePreview) {
            this.activePreview = null;
        }
        this.restorePendingPrompts(activePreview);
        if (this.sessionStatus === 'cancellingUpdate') {
            this.setStatus(activePreview.previousStatus);
        }
    }

    async confirm(options?: ObjectSelectionConfirmOptions) {
        this.requireStatus('preview');
        if (this.pendingPrompts.length > 0) {
            throw new Error(
                'Object Selection Session cannot confirm while pending prompts remain. Update Preview or Clear Prompts first.'
            );
        }

        const candidate = this.requireCandidate();
        if (
            candidate.uncertainIds.length > 0 &&
      options?.acknowledgeUncertain !== true
        ) {
            throw new Error(
                'Object Selection Session confirm requires acknowledging that uncertain Gaussians will not be selected.'
            );
        }
        this.requireCurrentSnapshot();
        const selectedIds = this.filterLockedIds(candidate).selectedIds;
        this.setStatus('confirming');

        try {
            await this.editor.commitSelection([...selectedIds]);
        } catch (error) {
            this.setStatus('preview');
            throw error;
        }

        await this.closeSession();
    }

    async cancel() {
        if (this.sessionStatus === 'previewing') {
            await this.cancelUpdate();
        }
        this.requireStatus('ready', 'preview');

        const previousStatus = this.sessionStatus;
        this.setStatus('cancelling');

        try {
            await this.editor.restoreSelection(this.requireEntrySelection());
        } catch (error) {
            this.setStatus(previousStatus);
            throw error;
        }

        await this.closeSession();
    }

    async retryCleanup() {
        this.requireStatus('closeFailed');
        await this.closeSession();
    }

    private requireStatus(...allowed: ObjectSelectionSessionStatus[]) {
        if (!allowed.includes(this.sessionStatus)) {
            throw new Error(
                `Object Selection Session cannot run this command while ${this.sessionStatus}.`
            );
        }
    }

    private requirePreviewStatus(): 'ready' | 'preview' {
        if (this.sessionStatus !== 'ready' && this.sessionStatus !== 'preview') {
            throw new Error(
                `Object Selection Session cannot update preview while ${this.sessionStatus}.`
            );
        }
        return this.sessionStatus;
    }

    private requireSessionId() {
        if (this.sessionId === null) {
            throw new Error(
                'Object Selection Session has no active Selection Service session.'
            );
        }
        return this.sessionId;
    }

    private requireTarget() {
        if (this.target === null) {
            throw new Error('Object Selection Session has no Target Splat.');
        }
        return this.target;
    }

    private requireSnapshot() {
        if (this.snapshot === null) {
            throw new Error('Object Selection Session has no Scene Snapshot.');
        }
        return this.snapshot;
    }

    private requireRequestContext() {
        if (this.requestContext === null) {
            throw new Error(
                'Object Selection Session has no immutable request context.'
            );
        }
        return this.requestContext;
    }

    private requireCurrentSnapshot() {
        const scene = this.requireScene();
        const snapshot = this.requireSnapshot();
        if (!scene.isCurrent(snapshot)) {
            throw new Error(
                'The Target Splat changed while this Object Selection Session was active. Start a new session for its current Scene Snapshot.'
            );
        }
        return snapshot;
    }

    private requireScene() {
        if (this.scene === null) {
            throw new Error(
                'Object Selection Session has no editor Scene Snapshot binding.'
            );
        }
        return this.scene;
    }

    private requireCandidate() {
        if (this.candidateSelection === null) {
            throw new Error(
                'Object Selection Session has no Candidate Object Selection to confirm.'
            );
        }
        return this.candidateSelection;
    }

    private requireEntrySelection() {
        if (this.entrySelection === null) {
            throw new Error(
                'Object Selection Session has no entry Gaussian Selection to restore.'
            );
        }
        return [...this.entrySelection];
    }

    private requireActivePreview() {
        if (this.activePreview === null) {
            throw new Error(
                'Object Selection Session has no active preview update to cancel.'
            );
        }
        return this.activePreview;
    }

    // The initial New result is not a Correction Round; only successful
    // inference-and-preview refreshes after it count against the budget.
    private correctionRoundsUsed() {
        return Math.max(0, this.successfulPreviewCount - 1);
    }

    private async closeSession() {
        const sessionId = this.requireSessionId();
        this.setStatus('closing');

        try {
            await this.selectionService.closeSession(sessionId);
        } catch (error) {
            this.setStatus('closeFailed');
            throw error;
        }

        this.clearSessionState();
        this.setStatus('idle');
    }

    private clearSessionState() {
        this.sessionId = null;
        this.entrySelection = null;
        this.target = null;
        this.scene = null;
        this.snapshot = null;
        this.requestContext = null;
        this.promptLog = [];
        this.pendingPrompts = [];
        this.candidateSelection = null;
        this.coverageReport = null;
        this.mode = 'New';
        this.successfulPreviewCount = 0;
        this.activePreview = null;
    }

    private setStatus(status: ObjectSelectionSessionStatus) {
        this.sessionStatus = status;
        this.publishState();
    }

    private publishState() {
        const state = this.state;
        this.listeners.forEach(listener => listener(state));
    }

    private restorePendingPrompts(activePreview: ActivePreview) {
        if (activePreview.submittedPrompts.length === 0) {
            return;
        }
        this.pendingPrompts = [
            ...activePreview.submittedPrompts.map(copyPromptLogEntry),
            ...this.pendingPrompts
        ];
        activePreview.submittedPrompts = [];
    }

    private assertRequestContext(context: ObjectSelectionRequestContext) {
        if (
            !context.deterministicSeed ||
      !context.frameSetVersion ||
      !context.frameSet ||
      !context.frameSet.frameSetId ||
      context.frameSet.frameSetVersion !== context.frameSetVersion ||
      context.frameSet.orderedViews.length === 0 ||
      !context.modelManifestDigest
        ) {
            throw new Error(
                'Object Selection Session requires deterministic seed, Frame Set, and Model Manifest bindings.'
            );
        }
    }

    private assertPromptFrame(
        prompt: ObjectSelectionPrompt,
        context: ObjectSelectionRequestContext
    ) {
        const frame = context.frameSet.orderedViews.find(
            view => view.viewId === prompt.viewId
        );
        if (
            frame === undefined ||
      frame.frameDigest !== prompt.frameDigest ||
      frame.width !== prompt.frameWidth ||
      frame.height !== prompt.frameHeight
        ) {
            throw new Error(
                'Object Selection point prompts must bind the registered Frame Set view.'
            );
        }
    }

    private validatePreviewResponse(
        response: SelectionServicePreviewResponse,
        request: ObjectSelectionPreviewRequest
    ): ObjectSelectionPreviewRequest {
        if (response.status !== 'complete') {
            throw new Error(
                'The Selection Service Companion did not return a complete preview result.'
            );
        }
        assertPreviewFrameSet(response.frameSet, request);
        const effectiveRequest = requestWithFrameSet(request, response.frameSet);
        if (!previewBindingsMatch(response, effectiveRequest)) {
            throw new Error(
                'The Selection Service Companion returned stale Object Selection request bindings.'
            );
        }
        assertCompleteMaskSet(response.maskSet, effectiveRequest);
        assertEvidenceSnapshot(response.evidenceSnapshot, effectiveRequest);
        assertCoverageReport(response.coverageReport, effectiveRequest);

        const knownIds = new Set(
            effectiveRequest.snapshot.gaussians.map(gaussian => gaussian.stableId)
        );
        const returnedIds = new Set<StableGaussianId>();
        const classifications = new Map<StableGaussianId, string>();
        const sets: Array<[string, readonly StableGaussianId[]]> = [
            ['selected', response.selectedIds],
            ['uncertain', response.uncertainIds],
            ['rejected', response.rejectedIds]
        ];

        sets.forEach(([name, ids]) => {
            let previous = -1;
            ids.forEach((id) => {
                if (!isStableGaussianId(id) || !knownIds.has(id)) {
                    throw new Error(
                        `The Selection Service Companion returned an unknown ${name} Stable Gaussian ID.`
                    );
                }
                if (id <= previous) {
                    throw new Error(
                        `The Selection Service Companion must return sorted unique ${name} Stable Gaussian IDs.`
                    );
                }
                if (returnedIds.has(id)) {
                    throw new Error(
                        'The Selection Service Companion returned overlapping Candidate Object Selection ID sets.'
                    );
                }
                previous = id;
                returnedIds.add(id);
                classifications.set(id, name);
            });
        });
        if (returnedIds.size !== knownIds.size) {
            throw new Error(
                'The Selection Service Companion returned an incomplete Candidate Object Selection.'
            );
        }
        response.evidenceSnapshot.records.forEach((record) => {
            if (classifications.get(record.stableId) !== record.classification) {
                throw new Error(
                    'The Selection Service Companion returned Candidate Object Selection IDs that disagree with its Evidence Snapshot.'
                );
            }
        });
        return effectiveRequest;
    }

    private filterLockedIds(
        candidate: SelectionResultIds &
      Partial<Pick<CandidateObjectSelection, 'lockedIdsFiltered'>>
    ): CandidateObjectSelection {
        const scene = this.requireScene();
        let lockedIdsFiltered = candidate.lockedIdsFiltered ?? 0;
        const filter = (ids: readonly StableGaussianId[]) => ids.filter((id) => {
            const locked = scene.isLocked(id);
            if (locked) {
                lockedIdsFiltered += 1;
            }
            return !locked;
        });
        return {
            selectedIds: filter(candidate.selectedIds),
            uncertainIds: filter(candidate.uncertainIds),
            rejectedIds: filter(candidate.rejectedIds),
            lockedIdsFiltered
        };
    }
}

export {
    ObjectSelectionSession,
    anchorFrameSetId,
    anchorFrameSetVersion,
    assertCompleteMaskSet,
    assertCoverageReport,
    assertEvidenceSnapshot,
    assertPreviewFrameSet,
    copyPreviewBindings,
    deriveMaskTrackPlan,
    previewBindingsFromRequest,
    previewBindingsMatch,
    requestWithFrameSet,
    selectionEvidencePolicyV1
};

export type {
    CandidateObjectSelection,
    ExpectedMaskTrack,
    ObjectSelectionConfirmOptions,
    ObjectSelectionMode,
    ObjectSelectionFrame,
    ObjectSelectionFrameSet,
    ObjectSelectionPreviewBindings,
    ObjectSelectionPreviewRequest,
    ObjectSelectionPrompt,
    ObjectSelectionPromptLogEntry,
    ObjectSelectionPromptPolarity,
    ObjectSelectionRequestContext,
    ObjectSelectionServiceSessionStart,
    ObjectSelectionSessionEditor,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionListener,
    ObjectSelectionSessionStart,
    ObjectSelectionSessionState,
    ObjectSelectionSessionStatus,
    ObjectSelectionTarget,
    SelectionServiceAdapter,
    SelectionEvidenceClassification,
    SelectionEvidencePolicy,
    SelectionEvidenceRecord,
    SelectionEvidenceUncertaintyReason,
    SelectionCoverageStatus,
    SelectionServiceCoverageReport,
    SelectionServiceEvidenceSnapshot,
    SelectionServiceMaskFrame,
    SelectionServiceMaskFrameStatus,
    SelectionServiceMaskSet,
    SelectionServiceMaskTrack,
    SelectionServicePreviewResponse,
    SelectionResultIds,
    StableGaussianId
};
