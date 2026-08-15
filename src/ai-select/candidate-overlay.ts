import type { CandidatePresentation } from './candidate-presentation';

export interface CandidateOverlayPresentationSource {
    readonly state: Pick<
        CandidatePresentation,
        'inspectable' | 'overlay' | 'statusBar'
    >;
    subscribe(
        listener: (state: CandidateOverlayPresentationSource['state']) => void
    ): () => void;
}

export interface CandidateOverlayState {
    readonly revision: string | null;
    readonly membership: CandidatePresentation['overlay']['membership'];
    readonly treatment: CandidatePresentation['overlay']['treatment'];
    readonly selectedVisible: boolean;
    readonly uncertainVisible: boolean;
}

type CandidateOverlayListener = (state: CandidateOverlayState) => void;

const isAppliedLifecycle = (
    lifecycle: CandidatePresentation['statusBar']['lifecycle']
): boolean => lifecycle?.startsWith('applied-') ?? false;

const copyMembership = (
    membership: CandidatePresentation['overlay']['membership']
): CandidatePresentation['overlay']['membership'] =>
    membership === null
        ? null
        : Object.freeze({
              selectedStableGaussianIds: Object.freeze([
                  ...membership.selectedStableGaussianIds
              ]),
              uncertainStableGaussianIds: Object.freeze([
                  ...membership.uncertainStableGaussianIds
              ])
          });

/** Revision-scoped, Target-local overlay visibility and diagnostic preference. */
export class CandidateOverlayController {
    private readonly presentation: CandidateOverlayPresentationSource;
    private readonly getCandidateRevision: () => string | null;
    private readonly listeners = new Set<CandidateOverlayListener>();
    private revision: string | null = null;
    private membership: CandidatePresentation['overlay']['membership'] = null;
    private treatment: CandidatePresentation['overlay']['treatment'] = null;
    private selectedVisible = false;
    private uncertainVisible = false;

    constructor(options: {
        readonly presentation: CandidateOverlayPresentationSource;
        readonly getCandidateRevision: () => string | null;
    }) {
        this.presentation = options.presentation;
        this.getCandidateRevision = options.getCandidateRevision;
        this.presentation.subscribe((state) => this.update(state));
    }

    get state(): CandidateOverlayState {
        return Object.freeze({
            revision: this.revision,
            membership: copyMembership(this.membership),
            treatment: this.treatment,
            selectedVisible: this.selectedVisible,
            uncertainVisible: this.uncertainVisible
        });
    }

    subscribe(listener: CandidateOverlayListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    toggleSelected(): void {
        if (this.membership === null) {
            return;
        }
        this.selectedVisible = !this.selectedVisible;
        this.publish();
    }

    setUncertainVisible(visible: boolean): void {
        if (this.membership === null && visible) {
            return;
        }
        this.uncertainVisible = visible;
        this.publish();
    }

    reset(): void {
        this.revision = null;
        this.membership = null;
        this.treatment = null;
        this.selectedVisible = false;
        this.uncertainVisible = false;
        this.publish();
    }

    private update(
        presentation: CandidateOverlayPresentationSource['state']
    ): void {
        if (
            !presentation.inspectable ||
            presentation.overlay.membership === null
        ) {
            this.revision = null;
            this.membership = null;
            this.treatment = null;
            this.selectedVisible = false;
            this.publish();
            return;
        }

        const revision = this.getCandidateRevision();
        if (revision === null) {
            this.reset();
            return;
        }
        const revisionChanged = revision !== this.revision;
        this.revision = revision;
        this.membership = copyMembership(presentation.overlay.membership);
        this.treatment = presentation.overlay.treatment;
        if (revisionChanged) {
            this.selectedVisible = !isAppliedLifecycle(
                presentation.statusBar.lifecycle
            );
        } else if (isAppliedLifecycle(presentation.statusBar.lifecycle)) {
            this.selectedVisible = false;
        }
        this.publish();
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                console.error(error);
            }
        });
    }
}

/**
 * Builds the dedicated GPU membership plane. Values are presentation-only:
 * 0 none, 1 Candidate Selected, 2 Uncertain; Selected wins overlap.
 */
export const candidateOverlayMembershipBytes = (
    gaussianCount: number,
    selectedIndices: Uint32Array,
    uncertainIndices: Uint32Array
): Uint8Array => {
    const result = new Uint8Array(gaussianCount);
    uncertainIndices.forEach((index) => {
        if (index >= gaussianCount) {
            throw new Error(
                'Uncertain overlay index is outside the Target Splat.'
            );
        }
        result[index] = 2;
    });
    selectedIndices.forEach((index) => {
        if (index >= gaussianCount) {
            throw new Error(
                'Candidate overlay index is outside the Target Splat.'
            );
        }
        result[index] = 1;
    });
    return result;
};
