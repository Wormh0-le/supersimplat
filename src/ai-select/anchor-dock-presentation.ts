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
export type ProposalFeedback =
    | 'none'
    | 'accepted'
    | 'pending'
    | 'selected'
    | 'ambiguous'
    | 'editing'
    | 'unavailable'
    | 'failed';

export interface AnchorDockMaskPresentation {
    readonly status: AnchorDockMaskStatus;
    readonly promptCount: number;
    readonly positivePointCount: number;
    readonly negativePointCount: number;
    readonly boxCount: number;
    readonly promptRevision: number;
    readonly proposalFeedback: ProposalFeedback;
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
        proposalFeedback: 'none',
        evidenceStatus: 'not-requested',
        proposalStatus: 'none',
        showConfirm: false,
        showRetry: false
    });
};

/**
 * The Mask surface of any one View's Mask state (Anchor or user-added
 * AIView): request currency, draft/confirmed Mask currency, prompt summary,
 * and the Confirm/Retry affordances. View source never determines trust.
 */
export const getViewMaskPresentation = (
    maskState: AISelectMaskState
): AnchorDockMaskPresentation => {
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
    const promptState = maskState.promptState;
    const promptCount =
        (promptState?.points.length ?? 0) + (promptState?.boxes.length ?? 0);
    const proposalFeedback: ProposalFeedback =
        maskState.requestStatus === 'pending'
            ? 'pending'
            : maskState.requestStatus === 'failed'
              ? 'failed'
              : maskState.proposalStatus === 'selected'
                ? 'selected'
                : maskState.proposalStatus === 'ambiguous'
                  ? 'ambiguous'
                  : maskState.proposalStatus === 'editing'
                    ? 'editing'
                    : maskState.proposalStatus === 'unavailable'
                      ? 'unavailable'
                      : promptCount > 0
                        ? 'accepted'
                        : 'none';
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
        proposalFeedback,
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
