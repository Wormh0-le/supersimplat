import type { AISelectAnchorState } from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import type { EvidenceStatus } from './evidence-state';
import type { AISelectMaskState } from './mask-controller';
import { promptStateHasConstraints } from './prompt-state';

export type AnchorDockStatus =
    'idle' | 'ready' | 'previewing' | 'rendering' | 'failed';

/**
 * The Dock's Mask surface. `pending` and `failed` describe the single-frame
 * SAM request; `draft`/`confirmed` describe Editing versus Stable Mask
 * currency. Render, Mask, and Evidence statuses stay distinct.
 */
export type AnchorDockMaskStatus =
    'none' | 'pending' | 'draft' | 'confirmed' | 'failed';

export interface AnchorDockMaskPresentation {
    readonly status: AnchorDockMaskStatus;
    readonly promptCount: number;
    readonly evidenceStatus: EvidenceStatus;
    readonly proposalStatus: AISelectMaskState['proposalStatus'];
    /** A current Editing Mask exists and can be atomically published. */
    readonly showConfirm: boolean;
    /** The failed SAM request can be retried with its prompt set. */
    readonly showRetry: boolean;
    readonly errorMessage?: string;
}

export interface AnchorDockPresentation {
    readonly status: AnchorDockStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly showFailureActions: boolean;
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
        showFailureActions: status === 'failed',
        mask
    });
};

const emptyMaskPresentation = (
    status: AnchorDockMaskStatus = 'none'
): AnchorDockMaskPresentation => {
    return Object.freeze({
        status,
        promptCount: 0,
        evidenceStatus: 'not-requested',
        proposalStatus: 'none',
        showConfirm: false,
        showRetry: false
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
    let status: AnchorDockMaskStatus = 'none';
    if (maskState.requestStatus === 'failed') {
        status = 'failed';
    } else if (maskState.requestStatus === 'pending') {
        status = 'pending';
    } else if (maskState.editingMask !== null) {
        status = 'draft';
    } else if (maskState.stableMask !== null) {
        status = 'confirmed';
    }
    return Object.freeze({
        status,
        promptCount:
            (maskState.promptState?.points.length ?? 0) +
            (maskState.promptState?.boxes.length ?? 0) +
            (maskState.promptState?.maskConstraints.length ?? 0) +
            (maskState.promptState?.textPrompts.length ?? 0),
        evidenceStatus: maskState.evidence.status,
        proposalStatus: maskState.proposalStatus ?? 'none',
        showConfirm: maskState.editingMask !== null,
        showRetry:
            maskState.requestStatus === 'failed' &&
            maskState.promptState != null &&
            promptStateHasConstraints(maskState.promptState),
        ...(maskState.errorMessage === undefined
            ? {}
            : { errorMessage: maskState.errorMessage })
    });
};

/**
 * Decide presentation separately from inference state. In particular, a
 * transient interactive failure remains retryable even when a formal Anchor
 * image from the same binding is still displayable.
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
