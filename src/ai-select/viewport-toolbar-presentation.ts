import type { AnchorAdjustmentStatus } from './anchor-adjustment';
import type {
    CameraInspectionManipulation,
    CameraInspectionTarget
} from './camera-inspection';
import type { CandidateUndoAndFixBlockReason } from './candidate-application';
import type {
    CandidateOperationDisabledReason,
    CandidatePresentation
} from './candidate-presentation';

export type AISelectViewportToolbarMode =
    | 'hidden'
    | 'current'
    | 'anchor-adjustment'
    | 'user-view-adjustment'
    | 'candidate';

export type AISelectViewportToolbarControl =
    | 'anchor-adjust'
    | 'add-current-view'
    | 'add-new-pose'
    | 'move'
    | 'rotate'
    | 'reset'
    | 'confirm-view'
    | 'cancel'
    | 'overlay'
    | 'set'
    | 'add'
    | 'remove'
    | 'intersect'
    | 'undo-and-fix';

export type AISelectViewportToolbarDisabledReason =
    CandidateOperationDisabledReason | CandidateUndoAndFixBlockReason;

export interface AISelectViewportToolbarControlPresentation {
    readonly control: AISelectViewportToolbarControl;
    readonly enabled: boolean;
    readonly pressed: boolean;
    readonly disabledReason: AISelectViewportToolbarDisabledReason | null;
}

export interface AISelectViewportToolbarPresentation {
    readonly mode: AISelectViewportToolbarMode;
    readonly controls: readonly AISelectViewportToolbarControlPresentation[];
}

export interface AISelectViewportToolbarPresentationInput {
    readonly hasContext: boolean;
    readonly contextActive: boolean;
    readonly hasConfirmedAnchor: boolean;
    readonly inspectionTarget: CameraInspectionTarget | null;
    readonly manipulation: CameraInspectionManipulation;
    readonly adjustmentStatus: AnchorAdjustmentStatus;
    readonly candidate: CandidatePresentation['toolbar'];
}

const control = (
    name: AISelectViewportToolbarControl,
    enabled = true,
    pressed = false,
    disabledReason: AISelectViewportToolbarDisabledReason | null = null
): AISelectViewportToolbarControlPresentation => {
    return Object.freeze({ control: name, enabled, pressed, disabledReason });
};

/**
 * Projects domain state into the only controls allowed on the spatial
 * toolbar. Stable array order is the visible keyboard and layout order.
 */
export const mapAISelectViewportToolbar = (
    input: AISelectViewportToolbarPresentationInput
): AISelectViewportToolbarPresentation => {
    if (!input.hasContext) {
        return Object.freeze({ mode: 'hidden', controls: Object.freeze([]) });
    }

    if (input.inspectionTarget?.kind === 'anchor-adjustment-draft') {
        return Object.freeze({
            mode: 'anchor-adjustment',
            controls: Object.freeze([
                control('anchor-adjust', true, true),
                control('move', true, input.manipulation === 'move'),
                control('rotate', true, input.manipulation === 'rotate'),
                control('reset'),
                control('cancel')
            ])
        });
    }

    if (input.inspectionTarget?.kind === 'user-view-draft') {
        return Object.freeze({
            mode: 'user-view-adjustment',
            controls: Object.freeze([
                control('move', true, input.manipulation === 'move'),
                control('rotate', true, input.manipulation === 'rotate'),
                control('confirm-view'),
                control('cancel')
            ])
        });
    }

    if (input.candidate.visible) {
        const enabled = input.candidate.operationsEnabled;
        const reason = input.candidate.disabledReason;
        return Object.freeze({
            mode: 'candidate',
            controls: Object.freeze([
                control('overlay'),
                control('set', enabled, false, reason),
                control('add', enabled, false, reason),
                control('remove', enabled, false, reason),
                control('intersect', enabled, false, reason),
                control(
                    'undo-and-fix',
                    input.candidate.undoAndFixEnabled,
                    false,
                    input.candidate.undoAndFixDisabledReason
                )
            ])
        });
    }

    const enabled =
        input.contextActive &&
        input.hasConfirmedAnchor &&
        input.adjustmentStatus === 'current';
    return Object.freeze({
        mode: 'current',
        controls: Object.freeze([
            control('anchor-adjust', enabled),
            control('add-current-view', enabled),
            control('add-new-pose', enabled)
        ])
    });
};
