import type {
    AISelectAnchorConfirmationController,
    ConfirmedAnchor
} from './anchor-confirmation';
import type {
    AISelectAnchorController,
    AnchorAdjustmentRenderArtifact
} from './anchor-controller';
import type { MaskAnnotation } from './mask-annotation';
import type { AISelectMaskController } from './mask-controller';

export interface AISelectAnchorCutoverCoordinatorOptions {
    readonly anchor: AISelectAnchorController;
    readonly mask: AISelectMaskController;
    readonly confirmation: AISelectAnchorConfirmationController;
    /** Release old Candidate/readiness products after confirmation rotates. */
    readonly releaseDependentProducts: () => void;
}

/**
 * The synchronous changed-Anchor cutover boundary. Every fallible provider
 * operation has completed before this method runs. Confirmation publication
 * is intentionally last: its observers release the old Generated View run
 * only after the new live Anchor and Stable Mask are both complete.
 */
export class AISelectAnchorCutoverCoordinator {
    constructor(
        private readonly options: AISelectAnchorCutoverCoordinatorOptions
    ) {}

    commit(input: {
        readonly render: AnchorAdjustmentRenderArtifact;
        readonly stableMask: MaskAnnotation;
    }): ConfirmedAnchor {
        this.options.anchor.commitAnchorAdjustmentDraft(input.render);
        this.options.mask.replaceStableFromAdjustment(input.stableMask);
        const confirmed =
            this.options.confirmation.replaceConfirmedAnchorFromAdjustment();
        this.options.mask.releasePreviousAnchorProductsAfterAdjustment();
        this.options.releaseDependentProducts();
        return confirmed;
    }
}
