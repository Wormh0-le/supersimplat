import type { AnchorAIView } from './anchor-controller';
import type { CameraBinding } from './camera-binding';
import type { EvidenceStatus, ViewEvidenceState } from './evidence-state';
import type { ViewMaskState } from './mask-registry';

export type AIViewRenderStatus = 'pending' | 'rendering' | 'ready' | 'failed';

export type AIViewSource =
    'anchor' | 'auto-generated' | 'user-added' | 'replacement';

export type AIViewParticipation = 'included' | 'excluded';

/**
 * The Final Spec v1.1 §7 per-view domain record. Render, Mask, and Evidence
 * are independently versioned: RGB Ready never implies Mask Ready or
 * Evidence Ready, and Evidence stale/failed never demotes a ready render.
 */
export interface AIView {
    readonly viewId: string;
    readonly source: AIViewSource;
    readonly camera: CameraBinding;
    readonly renderStatus: AIViewRenderStatus;
    readonly rgbDigest?: string;
    readonly participation: AIViewParticipation;
    readonly stableMaskId?: string;
    readonly editingMaskId?: string;
    readonly evidenceStatus: EvidenceStatus;
}

/**
 * Compose the Anchor's render record with its independent Mask and Evidence
 * state into the §7 AIView surface. The Anchor's Participation stays
 * `included` until Ticket 07 introduces user-controlled Participation.
 */
export const composeAnchorAIView = (
    anchor: AnchorAIView,
    masks: ViewMaskState,
    evidence: ViewEvidenceState
): AIView => {
    return Object.freeze({
        viewId: anchor.viewId,
        source: anchor.source,
        camera: anchor.cameraBinding,
        renderStatus: anchor.renderStatus,
        ...(anchor.rgb === undefined ? {} : { rgbDigest: anchor.rgb.digest }),
        participation: 'included',
        ...(masks.stableMask === null
            ? {}
            : { stableMaskId: masks.stableMask.maskId }),
        ...(masks.editingMask === null
            ? {}
            : { editingMaskId: masks.editingMask.maskId }),
        evidenceStatus: evidence.status
    });
};
