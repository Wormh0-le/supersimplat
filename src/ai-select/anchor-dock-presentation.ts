import type { AISelectAnchorState } from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';

export type AnchorDockStatus =
    'idle' | 'ready' | 'previewing' | 'rendering' | 'failed';

export interface AnchorDockPresentation {
    readonly status: AnchorDockStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly showFailureActions: boolean;
}

const presentation = (
    status: AnchorDockStatus,
    rgb?: AnchorRgbArtifact
): AnchorDockPresentation => {
    return Object.freeze({
        status,
        ...(rgb === undefined ? {} : { rgb }),
        showFailureActions: status === 'failed'
    });
};

/**
 * Decide presentation separately from inference state. In particular, a
 * transient interactive failure remains retryable even when a formal Anchor
 * image from the same binding is still displayable.
 */
export const getAnchorDockPresentation = (
    state: AISelectAnchorState
): AnchorDockPresentation => {
    const { context, anchor } = state;
    if (context === null || anchor === null) {
        return presentation('idle');
    }

    const preview = anchor.preview;
    const fallbackRgb = anchor.rgb ?? anchor.lastValidPreview?.rgb;
    if (
        preview?.renderStatus === 'failed' ||
        anchor.renderStatus === 'failed'
    ) {
        return presentation('failed', fallbackRgb);
    }
    if (preview?.renderStatus === 'rendering') {
        return presentation(
            preview.kind === 'interactive' ? 'previewing' : 'rendering',
            fallbackRgb
        );
    }
    if (preview?.kind === 'interactive' && preview.renderStatus === 'ready') {
        return presentation('previewing', preview.rgb ?? fallbackRgb);
    }
    if (anchor.renderStatus === 'ready' && anchor.rgb !== undefined) {
        return presentation('ready', anchor.rgb);
    }
    if (anchor.renderStatus === 'rendering') {
        return presentation('rendering', fallbackRgb);
    }
    return presentation('failed', fallbackRgb);
};
