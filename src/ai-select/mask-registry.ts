import { sha256Digest } from '../scene-snapshot-binary';
import {
    applyBrushStroke,
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
        const artifact = applyBrushStroke(baseArtifact, input.stroke);
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
