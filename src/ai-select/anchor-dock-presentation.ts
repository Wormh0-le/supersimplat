import type { AISelectAnchorState } from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import type { EvidenceStatus } from './evidence-state';
import type { AISelectMaskState } from './mask-controller';
import { hasSemanticEditingMaskChange } from './mask-registry';

export type AnchorDockStatus =
    'idle' | 'ready' | 'previewing' | 'rendering' | 'failed';

/**
 * The Dock's Mask surface. `pending` and `failed` describe the single-frame
 * SAM request; `draft`/`confirmed` describe Editing versus Stable Mask
 * currency. Render, Mask, and Evidence statuses stay distinct.
 */
export type AnchorDockMaskStatus =
    'none' | 'pending' | 'draft' | 'confirmed' | 'failed';
export type MaskResultFeedback =
    'none' | 'pending' | 'editing' | 'unavailable' | 'failed';

export interface AnchorDockMaskPresentation {
    readonly status: AnchorDockMaskStatus;
    readonly promptCount: number;
    readonly positivePointCount: number;
    readonly negativePointCount: number;
    readonly boxCount: number;
    readonly promptRevision: number;
    readonly resultFeedback: MaskResultFeedback;
    readonly evidenceStatus: EvidenceStatus;
    readonly automaticMaskStatus: AISelectMaskState['automaticMaskStatus'];
    /** A current Editing Mask exists and can be atomically published. */
    readonly showConfirm: boolean;
    readonly errorMessage?: string;
}

export interface AnchorDockPresentation {
    readonly status: AnchorDockStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly mask: AnchorDockMaskPresentation;
}

const presentation = (
    status: AnchorDockStatus,
    rgb: AnchorRgbArtifact | undefined,
    mask: AnchorDockMaskPresentation
): AnchorDockPresentation => {
    return Object.freeze({
        status,
        ...(rgb === undefined ? {} : { rgb }),
        mask
    });
};

const emptyMaskPresentation = (
    status: AnchorDockMaskStatus = 'none'
): AnchorDockMaskPresentation => {
    return Object.freeze({
        status,
        promptCount: 0,
        positivePointCount: 0,
        negativePointCount: 0,
        boxCount: 0,
        promptRevision: 0,
        resultFeedback: 'none',
        evidenceStatus: 'not-requested',
        automaticMaskStatus: 'none',
        showConfirm: false
    });
};

/**
 * The Mask surface of any one View's Mask state (Anchor or user-added
 * AIView): request currency, draft/confirmed Mask currency, prompt summary,
 * and the Confirm affordance. View source never determines trust.
 */
export const getViewMaskPresentation = (
    maskState: AISelectMaskState
): AnchorDockMaskPresentation => {
    const editingMaskChanged = hasSemanticEditingMaskChange(
        maskState.editingMask,
        maskState.stableMask
    );
    let status: AnchorDockMaskStatus = 'none';
    if (maskState.requestStatus === 'failed') {
        status = 'failed';
    } else if (maskState.requestStatus === 'pending') {
        status = 'pending';
    } else if (editingMaskChanged) {
        status = 'draft';
    } else if (maskState.stableMask !== null) {
        status = 'confirmed';
    }
    const promptState = maskState.promptState;
    const promptCount =
        (promptState?.points.length ?? 0) + (promptState?.boxes.length ?? 0);
    const resultFeedback: MaskResultFeedback =
        maskState.requestStatus === 'pending'
            ? 'pending'
            : maskState.requestStatus === 'failed'
              ? 'failed'
              : maskState.automaticMaskStatus;
    return Object.freeze({
        status,
        promptCount,
        positivePointCount:
            promptState?.points.filter((point) => point.polarity === 'include')
                .length ?? 0,
        negativePointCount:
            promptState?.points.filter((point) => point.polarity === 'exclude')
                .length ?? 0,
        boxCount: promptState?.boxes.length ?? 0,
        promptRevision: promptState?.revision ?? 0,
        resultFeedback,
        evidenceStatus: maskState.evidence.status,
        automaticMaskStatus: maskState.automaticMaskStatus,
        showConfirm:
            maskState.editingMask !== null &&
            (editingMaskChanged ||
                maskState.hasUnconfirmedPromptChanges === true),
        ...(maskState.errorMessage === undefined
            ? {}
            : { errorMessage: maskState.errorMessage })
    });
};

/** Derive the Mask surface independently from render presentation. */
export const getAnchorDockMaskPresentation = (
    state: AISelectAnchorState,
    maskState?: AISelectMaskState
): AnchorDockMaskPresentation => {
    if (state.context === null || state.anchor === null || !maskState) {
        return emptyMaskPresentation();
    }
    return getViewMaskPresentation(maskState);
};

/**
 * Decide presentation separately from inference state. In particular, a
 * transient interactive failure remains visible even when a prior formal
 * Anchor image from the same binding is still displayable.
 */
export const getAnchorDockPresentation = (
    state: AISelectAnchorState,
    maskState?: AISelectMaskState
): AnchorDockPresentation => {
    const mask = getAnchorDockMaskPresentation(state, maskState);
    const { context, anchor } = state;
    if (context === null || anchor === null) {
        return presentation('idle', undefined, mask);
    }

    const preview = anchor.preview;
    const fallbackRgb = anchor.rgb ?? anchor.lastValidPreview?.rgb;
    if (
        preview?.renderStatus === 'failed' ||
        anchor.renderStatus === 'failed'
    ) {
        return presentation('failed', fallbackRgb, mask);
    }
    if (preview?.renderStatus === 'rendering') {
        return presentation(
            preview.kind === 'interactive' ? 'previewing' : 'rendering',
            fallbackRgb,
            mask
        );
    }
    if (preview?.kind === 'interactive' && preview.renderStatus === 'ready') {
        return presentation('previewing', preview.rgb ?? fallbackRgb, mask);
    }
    if (anchor.renderStatus === 'ready' && anchor.rgb !== undefined) {
        return presentation('ready', anchor.rgb, mask);
    }
    if (anchor.renderStatus === 'rendering') {
        return presentation('rendering', fallbackRgb, mask);
    }
    return presentation('failed', fallbackRgb, mask);
};
