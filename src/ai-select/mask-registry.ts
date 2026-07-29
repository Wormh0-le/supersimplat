import { sha256Digest } from '../scene-snapshot-binary';
import {
    applyBrushStrokes,
    createEmptyMaskArtifact,
    decodeMaskArtifact,
    isMaskAnnotation,
    isMaskArtifact,
    isMaskPrompt,
    type BrushStroke,
    type MaskAnnotation,
    type MaskArtifact,
    type MaskPrompt
} from './mask-annotation';

export interface RegisterSamMaskInput {
    readonly viewId: string;
    /** The authoritative RGB digest this SAM output was produced from. */
    readonly rgbDigest: string;
    readonly artifact: MaskArtifact;
    readonly prompts: readonly MaskPrompt[];
}

export interface ApplyBrushInput {
    readonly viewId: string;
    /** The current authoritative RGB digest; stale chains never attach. */
    readonly rgbDigest: string;
    readonly stroke: BrushStroke;
    readonly width: number;
    readonly height: number;
}

export interface ApplyBrushGestureInput {
    readonly viewId: string;
    /** The current authoritative RGB digest; stale chains never attach. */
    readonly rgbDigest: string;
    readonly strokes: readonly BrushStroke[];
    readonly width: number;
    readonly height: number;
}

export interface PublishAutoStableMaskInput {
    readonly viewId: string;
    /** The authoritative RGB digest this automatic Mask was produced from. */
    readonly rgbDigest: string;
    readonly artifact: MaskArtifact;
    readonly source: 'propagated';
    readonly status: 'auto-good' | 'auto-review';
}

/**
 * The derived per-view mask surface: only annotations bound to the current
 * authoritative RGB digest are current; older versions stay retained for
 * inspection but can never attach to changed RGB/CameraBinding.
 */
export interface ViewMaskState {
    readonly viewId: string;
    readonly editingMask: MaskAnnotation | null;
    readonly stableMask: MaskAnnotation | null;
}

interface MutableViewMasks {
    versions: Map<string, MaskAnnotation>;
    editingMaskId: string | null;
    stableMaskId: string | null;
}

const copyPrompts = (prompts: readonly MaskPrompt[]): readonly MaskPrompt[] => {
    return Object.freeze(
        prompts.map((prompt) =>
            Object.freeze({
                promptId: prompt.promptId,
                xPx: prompt.xPx,
                yPx: prompt.yPx,
                polarity: prompt.polarity
            })
        )
    );
};

const copyArtifact = (artifact: MaskArtifact): MaskArtifact => {
    return Object.freeze({
        encoding: artifact.encoding,
        width: artifact.width,
        height: artifact.height,
        data: artifact.data,
        digest: artifact.digest
    });
};

const copyAnnotation = (annotation: MaskAnnotation): MaskAnnotation => {
    return Object.freeze({
        maskId: annotation.maskId,
        viewId: annotation.viewId,
        source: annotation.source,
        status: annotation.status,
        artifact: copyArtifact(annotation.artifact),
        ...(annotation.prompts === undefined
            ? {}
            : { prompts: copyPrompts(annotation.prompts) }),
        ...(annotation.parentMaskId === undefined
            ? {}
            : { parentMaskId: annotation.parentMaskId }),
        createdFromRgbDigest: annotation.createdFromRgbDigest
    });
};

const assertDigestBoundArtifact = (artifact: MaskArtifact): void => {
    if (!isMaskArtifact(artifact)) {
        throw new Error(
            'AI Select requires a structurally valid Mask artifact.'
        );
    }
    if (sha256Digest(decodeMaskArtifact(artifact)) !== artifact.digest) {
        throw new Error(
            'AI Select Mask artifact bytes do not match their digest.'
        );
    }
};

/**
 * Owns the versioned Mask annotations of every AI View in one Current Target
 * Context. Editing and Stable Masks are independent version chains: SAM and
 * brush work only ever replace the Editing Mask, and Confirm Mask atomically
 * publishes it as a new Stable revision. The registry is synchronous; async
 * stale-result protection lives in the driving controller.
 */
export class MaskAnnotationRegistry {
    private readonly views = new Map<string, MutableViewMasks>();
    private nextMaskOrdinal = 0;

    registerSamResult(input: RegisterSamMaskInput): MaskAnnotation {
        assertDigestBoundArtifact(input.artifact);
        if (!input.prompts.every(isMaskPrompt)) {
            throw new Error('AI Select SAM masks require valid point prompts.');
        }
        for (const prompt of input.prompts) {
            if (
                prompt.xPx >= input.artifact.width ||
                prompt.yPx >= input.artifact.height
            ) {
                throw new Error(
                    'AI Select SAM prompts must land inside the Mask bounds.'
                );
            }
        }
        const view = this.requireView(input.viewId);
        const currentEditing = this.currentAnnotation(
            view,
            view.editingMaskId,
            input.rgbDigest
        );
        const editing = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId: input.viewId,
            source: 'single-frame-sam',
            status: 'draft',
            artifact: input.artifact,
            prompts: input.prompts,
            ...(currentEditing === null
                ? {}
                : { parentMaskId: currentEditing.maskId }),
            createdFromRgbDigest: input.rgbDigest
        });
        view.versions.set(editing.maskId, editing);
        view.editingMaskId = editing.maskId;
        return editing;
    }

    applyBrush(input: ApplyBrushInput): MaskAnnotation {
        return this.applyBrushGesture({
            ...input,
            strokes: [input.stroke]
        });
    }

    /**
     * Publish a complete pointer gesture as one Editing Mask revision. The
     * artifact is built off-registry, then attached once, so observers and
     * Mask history never see its intermediate stamps.
     */
    applyBrushGesture(input: ApplyBrushGestureInput): MaskAnnotation {
        if (input.strokes.length === 0) {
            throw new Error(
                'AI Select brush gestures require at least one stroke sample.'
            );
        }
        const view = this.requireView(input.viewId);
        const currentEditing = this.currentAnnotation(
            view,
            view.editingMaskId,
            input.rgbDigest
        );
        const baseArtifact =
            currentEditing === null
                ? createEmptyMaskArtifact(input.width, input.height)
                : currentEditing.artifact;
        const artifact = applyBrushStrokes(baseArtifact, input.strokes);
        const editing = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId: input.viewId,
            source:
                currentEditing === null || currentEditing.source === 'manual'
                    ? 'manual'
                    : 'hybrid',
            status: 'draft',
            artifact,
            ...(currentEditing === null
                ? {}
                : { parentMaskId: currentEditing.maskId }),
            createdFromRgbDigest: input.rgbDigest
        });
        view.versions.set(editing.maskId, editing);
        view.editingMaskId = editing.maskId;
        return editing;
    }

    /**
     * Atomically publish the current Editing Mask as the new Stable Mask
     * revision. The swap is one synchronous transition: observers either see
     * the previous Stable Mask with its Evidence/Candidate state intact, or
     * the fully bound replacement — never a partial publication.
     */
    confirm(viewId: string, rgbDigest: string): MaskAnnotation {
        const view = this.requireView(viewId);
        const editing = this.currentAnnotation(
            view,
            view.editingMaskId,
            rgbDigest
        );
        if (editing === null) {
            throw new Error(
                'AI Select Confirm Mask requires a current Editing Mask bound to the current RGB.'
            );
        }
        const stable = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId,
            source: editing.source,
            status: 'user-confirmed',
            artifact: editing.artifact,
            ...(editing.prompts === undefined
                ? {}
                : { prompts: editing.prompts }),
            parentMaskId: editing.maskId,
            createdFromRgbDigest: editing.createdFromRgbDigest
        });
        view.versions.set(stable.maskId, stable);
        view.stableMaskId = stable.maskId;
        return stable;
    }

    /**
     * Atomically publish an automatic cross-view Mask directly as the Stable
     * revision, chained from any previous Stable version. Automatic
     * publication never creates or disturbs the Editing Mask, and it never
     * waits for user confirmation: until Ticket 07's evidence-backed View
     * Assessment binds and supplies the automatic quality label; Review stays
     * the fail-closed default and is Excluded from Lift.
     */
    publishAutoStable(input: PublishAutoStableMaskInput): MaskAnnotation {
        assertDigestBoundArtifact(input.artifact);
        const view = this.requireView(input.viewId);
        const previousStable = view.stableMaskId;
        const stable = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId: input.viewId,
            source: input.source,
            status: input.status,
            artifact: input.artifact,
            ...(previousStable === null
                ? {}
                : { parentMaskId: previousStable }),
            createdFromRgbDigest: input.rgbDigest
        });
        view.versions.set(stable.maskId, stable);
        view.stableMaskId = stable.maskId;
        return stable;
    }

    /**
     * Confirm the current automatic Stable Mask without changing its pixels.
     * The new immutable revision records user authority and stays bound to the
     * same RGB/artifact identity; later automatic assessment cannot overwrite
     * or down-weight it.
     */
    confirmStableAsIs(viewId: string, rgbDigest: string): MaskAnnotation {
        const view = this.requireView(viewId);
        const current = this.currentAnnotation(
            view,
            view.stableMaskId,
            rgbDigest
        );
        if (
            current === null ||
            (current.status !== 'auto-good' && current.status !== 'auto-review')
        ) {
            throw new Error(
                'AI Select Confirm as-is requires a current automatic Stable Mask.'
            );
        }
        const confirmed = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId,
            source: current.source,
            status: 'user-confirmed',
            artifact: current.artifact,
            ...(current.prompts === undefined
                ? {}
                : { prompts: current.prompts }),
            parentMaskId: current.maskId,
            createdFromRgbDigest: rgbDigest
        });
        view.versions.set(confirmed.maskId, confirmed);
        view.stableMaskId = confirmed.maskId;
        return confirmed;
    }

    /**
     * Clear replaces the Editing Mask with an empty manual draft chained from
     * the current one. It never touches the Stable Mask, and the replaced
     * draft stays retained for Undo or Restore Auto.
     */
    clearEditing(
        viewId: string,
        rgbDigest: string,
        width: number,
        height: number
    ): MaskAnnotation {
        const view = this.requireView(viewId);
        const currentEditing = this.currentAnnotation(
            view,
            view.editingMaskId,
            rgbDigest
        );
        const editing = copyAnnotation({
            maskId: this.mintMaskId(),
            viewId,
            source: 'manual',
            status: 'draft',
            artifact: createEmptyMaskArtifact(width, height),
            ...(currentEditing === null
                ? {}
                : { parentMaskId: currentEditing.maskId }),
            createdFromRgbDigest: rgbDigest
        });
        view.versions.set(editing.maskId, editing);
        view.editingMaskId = editing.maskId;
        return editing;
    }

    /**
     * Restore a retained Editing-chain version as the current Editing Mask,
     * or detach it back to the empty start state. Mask-local Undo/Redo and
     * Restore Auto navigate existing versions; they never fabricate new
     * content or touch the Stable Mask.
     */
    restoreEditing(
        viewId: string,
        maskId: string | null,
        rgbDigest: string
    ): MaskAnnotation | null {
        const view = this.views.get(viewId);
        if (view === undefined) {
            throw new Error(
                'AI Select cannot restore a Mask for an unknown AI View.'
            );
        }
        if (maskId === null) {
            view.editingMaskId = null;
            return null;
        }
        const annotation = view.versions.get(maskId);
        if (
            annotation === undefined ||
            annotation.createdFromRgbDigest !== rgbDigest ||
            annotation.status !== 'draft'
        ) {
            throw new Error(
                'AI Select can only restore a current-RGB Editing Mask version.'
            );
        }
        view.editingMaskId = maskId;
        return copyAnnotation(annotation);
    }

    /**
     * The newest retained automatic (single-frame SAM) version bound to the
     * current RGB, for Restore Auto. Manual and hybrid drafts never qualify.
     */
    latestAutoMask(viewId: string, rgbDigest: string): MaskAnnotation | null {
        const view = this.views.get(viewId);
        if (view === undefined) {
            return null;
        }
        let latest: MaskAnnotation | null = null;
        for (const annotation of view.versions.values()) {
            if (
                annotation.source === 'single-frame-sam' &&
                annotation.status === 'draft' &&
                annotation.createdFromRgbDigest === rgbDigest
            ) {
                latest = annotation;
            }
        }
        return latest === null ? null : copyAnnotation(latest);
    }

    viewState(viewId: string, rgbDigest: string): ViewMaskState {
        const view = this.views.get(viewId);
        if (view === undefined) {
            return Object.freeze({
                viewId,
                editingMask: null,
                stableMask: null
            });
        }
        return Object.freeze({
            viewId,
            editingMask: this.currentAnnotation(
                view,
                view.editingMaskId,
                rgbDigest
            ),
            stableMask: this.currentAnnotation(
                view,
                view.stableMaskId,
                rgbDigest
            )
        });
    }

    /** Any retained version, current or superseded, for inspection/chains. */
    version(viewId: string, maskId: string): MaskAnnotation | null {
        const annotation = this.views.get(viewId)?.versions.get(maskId);
        return annotation === undefined ? null : copyAnnotation(annotation);
    }

    disposeView(viewId: string): void {
        this.views.delete(viewId);
    }

    private currentAnnotation(
        view: MutableViewMasks,
        maskId: string | null,
        rgbDigest: string
    ): MaskAnnotation | null {
        if (maskId === null) {
            return null;
        }
        const annotation = view.versions.get(maskId);
        if (annotation === undefined) {
            return null;
        }
        if (annotation.createdFromRgbDigest !== rgbDigest) {
            return null;
        }
        return copyAnnotation(annotation);
    }

    private requireView(viewId: string): MutableViewMasks {
        let view = this.views.get(viewId);
        if (view === undefined) {
            view = {
                versions: new Map(),
                editingMaskId: null,
                stableMaskId: null
            };
            this.views.set(viewId, view);
        }
        return view;
    }

    private mintMaskId(): string {
        if (this.nextMaskOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error('AI Select Mask identity cannot advance safely.');
        }
        this.nextMaskOrdinal += 1;
        return `mask-${this.nextMaskOrdinal}`;
    }
}

export const isMaskAnnotationBoundTo = (
    annotation: MaskAnnotation,
    viewId: string,
    rgbDigest: string
): boolean => {
    return (
        isMaskAnnotation(annotation) &&
        annotation.viewId === viewId &&
        annotation.createdFromRgbDigest === rgbDigest
    );
};
