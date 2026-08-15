import {
    ADDRESS_CLAMP_TO_EDGE,
    FILTER_NEAREST,
    PIXELFORMAT_R8,
    GSplatResource,
    Texture
} from 'playcanvas';

import {
    candidateOverlayMembershipBytes,
    type CandidateOverlayController,
    type CandidateOverlayState
} from './ai-select/candidate-overlay';
import type { Splat } from './splat';
import type { SplatSceneSnapshotBinding } from './splat-scene-snapshot';

interface CandidateViewportTarget {
    readonly splat: Splat;
    readonly stableIds: SplatSceneSnapshotBinding;
}

/** Owns and disposes the Candidate-only GPU membership texture. */
export class CandidateViewportOverlay {
    private readonly getTarget: () => CandidateViewportTarget | null;
    private readonly onFailure: (error: unknown) => void;
    private readonly onRecovered: () => void;
    private readonly createTextureForState: (
        target: CandidateViewportTarget,
        state: CandidateOverlayState
    ) => Texture;
    private texture: Texture | null = null;
    private attachedSplat: Splat | null = null;
    private revision: string | null = null;
    private failed = false;

    constructor(
        overlay: CandidateOverlayController,
        options: {
            readonly getTarget: () => CandidateViewportTarget | null;
            readonly onFailure?: (error: unknown) => void;
            readonly onRecovered?: () => void;
            /** Test seam for locked-runtime allocation and disposal checks. */
            readonly createTexture?: (
                target: CandidateViewportTarget,
                state: CandidateOverlayState
            ) => Texture;
        }
    ) {
        this.getTarget = options.getTarget;
        this.onFailure = options.onFailure ?? ((error) => console.error(error));
        this.onRecovered = options.onRecovered ?? (() => undefined);
        this.createTextureForState =
            options.createTexture ??
            ((target, state) => this.createTexture(target, state));
        overlay.subscribe((state) => this.render(state));
    }

    destroy(): void {
        this.release();
    }

    private render(state: CandidateOverlayState): void {
        const target = this.getTarget();
        if (
            target === null ||
            state.revision === null ||
            state.membership === null
        ) {
            this.release();
            return;
        }

        try {
            if (
                this.texture === null ||
                this.attachedSplat !== target.splat ||
                this.revision !== state.revision
            ) {
                this.release();
                this.texture = this.createTextureForState(target, state);
                this.attachedSplat = target.splat;
                this.revision = state.revision;
            }
            target.splat.setCandidateOverlay(this.texture, {
                selectedVisible: state.selectedVisible,
                uncertainVisible: state.uncertainVisible,
                stale: state.treatment === 'stale'
            });
            if (this.failed) {
                this.failed = false;
                this.onRecovered();
            }
        } catch (error) {
            this.release();
            this.failed = true;
            this.onFailure(error);
        }
    }

    private createTexture(
        target: CandidateViewportTarget,
        state: CandidateOverlayState
    ): Texture {
        const membership = state.membership;
        if (membership === null) {
            throw new Error('Candidate Overlay has no inspectable membership.');
        }
        const selected = target.stableIds.toSplatIndices(
            membership.selectedStableGaussianIds
        );
        const uncertain = target.stableIds.toSplatIndices(
            membership.uncertainStableGaussianIds
        );
        const bytes = candidateOverlayMembershipBytes(
            target.splat.splatData.numSplats,
            selected,
            uncertain
        );
        const resource = target.splat.asset.resource as GSplatResource;
        const texture = new Texture(resource.device, {
            name: 'aiCandidateState',
            width: target.splat.stateTexture.width,
            height: target.splat.stateTexture.height,
            format: PIXELFORMAT_R8,
            mipmaps: false,
            minFilter: FILTER_NEAREST,
            magFilter: FILTER_NEAREST,
            addressU: ADDRESS_CLAMP_TO_EDGE,
            addressV: ADDRESS_CLAMP_TO_EDGE
        });
        try {
            const destination = texture.lock() as Uint8Array;
            destination.fill(0);
            destination.set(bytes);
            texture.unlock();
            return texture;
        } catch (error) {
            texture.destroy();
            throw error;
        }
    }

    private release(): void {
        this.attachedSplat?.clearCandidateOverlay();
        this.texture?.destroy();
        this.texture = null;
        this.attachedSplat = null;
        this.revision = null;
    }
}
