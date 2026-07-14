import {
    assertSceneSnapshot,
    isStableGaussianId,
    type SceneSnapshot,
    type SceneSnapshotBinding,
    type StableGaussianId
} from './scene-snapshot';

type ObjectSelectionMode = 'New' | 'Add' | 'Remove' | 'Refine';
type ObjectSelectionPromptPolarity = 'include' | 'exclude';

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

interface SelectionServicePreviewResponse
  extends ObjectSelectionPreviewBindings, SelectionResultIds {
  status: 'complete';
  maskSet: SelectionServiceMaskSet;
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
  mode: ObjectSelectionMode;
  promptCount: number;
  lockedIdsFiltered: number;
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
  updatePreview(): Promise<void>;
  cancelUpdate(): Promise<void>;
  confirm(): Promise<void>;
  cancel(): Promise<void>;
  retryCleanup(): Promise<void>;
}

interface ActivePreview {
  requestId: string;
  previousStatus: 'ready' | 'preview';
  cancelled: boolean;
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

const incompleteMaskSet = () => {
    return new Error(
        'The Selection Service Companion returned an incomplete, version-bound Mask Set.'
    );
};

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
    const trackIds = new Set<string>();
    let primaryFrames: Record<string, unknown>[] | null = null;
    value.tracks.forEach((track) => {
        if (
            !isRecord(track) ||
      typeof track.trackId !== 'string' ||
      !track.trackId ||
      (track.role !== 'include' && track.role !== 'exclude') ||
      !Array.isArray(track.frames) ||
      track.frames.length !== expectedFrames.length ||
      trackIds.has(track.trackId)
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
    private candidateSelection: CandidateObjectSelection | null = null;
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
            mode: this.mode,
            promptCount: this.promptLog.length,
            lockedIdsFiltered: this.candidateSelection?.lockedIdsFiltered ?? 0
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
        this.assertPromptFrame(prompt, this.requireRequestContext());
        this.promptLog.push({
            operation: this.mode,
            prompt: copyPrompt(prompt)
        });
        this.publishState();
    }

    async updatePreview() {
        const previousStatus = this.requirePreviewStatus();
        this.requireCurrentSnapshot();

        const activePreview: ActivePreview = {
            requestId: `request-${++this.requestCount}`,
            previousStatus,
            cancelled: false
        };
        this.activePreview = activePreview;
        this.setStatus('previewing');

        const request: ObjectSelectionPreviewRequest = {
            sessionId: this.requireSessionId(),
            requestId: activePreview.requestId,
            target: copyTarget(this.requireTarget()),
            targetSplatId: this.requireTarget().targetSplatId,
            sceneId: this.requireSnapshot().sceneId,
            sceneVersion: this.requireSnapshot().sceneVersion,
            operation: this.mode,
            correctionRound: this.successfulPreviewCount,
            deterministicSeed: this.requireRequestContext().deterministicSeed,
            promptLogRevision: this.promptLog.length,
            frameSetVersion: this.requireRequestContext().frameSetVersion,
            renderConfigVersion: this.requireSnapshot().renderConfiguration.version,
            modelManifestDigest: this.requireRequestContext().modelManifestDigest,
            promptLog: this.promptLog.map(copyPromptLogEntry),
            frameSet: copyFrameSet(this.requireRequestContext().frameSet),
            snapshot: this.requireSnapshot()
        };

        try {
            const response = await this.selectionService.updatePreview(request);
            if (this.activePreview !== activePreview || activePreview.cancelled) {
                return;
            }

            this.requireCurrentSnapshot();
            this.validatePreviewResponse(response, request);
            this.candidateSelection = copyCandidate(this.filterLockedIds(response));
            this.successfulPreviewCount += 1;
            this.setStatus('preview');
        } catch (error) {
            if (!activePreview.cancelled) {
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
        if (this.sessionStatus === 'cancellingUpdate') {
            this.setStatus(activePreview.previousStatus);
        }
    }

    async confirm() {
        this.requireStatus('preview');

        const candidate = this.requireCandidate();
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
        this.candidateSelection = null;
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
    ) {
        if (response.status !== 'complete') {
            throw new Error(
                'The Selection Service Companion did not return a complete preview result.'
            );
        }
        if (!previewBindingsMatch(response, request)) {
            throw new Error(
                'The Selection Service Companion returned stale Object Selection request bindings.'
            );
        }
        assertCompleteMaskSet(response.maskSet, request);

        const knownIds = new Set(
            request.snapshot.gaussians.map(gaussian => gaussian.stableId)
        );
        const returnedIds = new Set<StableGaussianId>();
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
            });
        });
        if (returnedIds.size !== knownIds.size) {
            throw new Error(
                'The Selection Service Companion returned an incomplete Candidate Object Selection.'
            );
        }
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
    copyPreviewBindings,
    previewBindingsFromRequest,
    previewBindingsMatch
};

export type {
    CandidateObjectSelection,
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
    SelectionServiceMaskFrame,
    SelectionServiceMaskFrameStatus,
    SelectionServiceMaskSet,
    SelectionServiceMaskTrack,
    SelectionServicePreviewResponse,
    SelectionResultIds,
    StableGaussianId
};
