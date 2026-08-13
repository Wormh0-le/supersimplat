import type {
    CandidatePublicationState,
    CandidatePublicationStore,
    CandidatePublicationBinding,
    ReferenceCandidateArtifact
} from './candidate-publication';
import type { AISelectDirtyStateTracker } from './dirty-state';
import {
    areEvidenceIdentitiesEqual,
    type EvidenceDependencyIdentity
} from './evidence-state';
import type { GaussianEvidenceArtifact } from './gaussian-evidence-contract';

export interface CandidateCorrectionView {
    readonly viewId: string;
    readonly participation: 'included' | 'excluded';
    readonly stableMaskDigest: string | null;
    readonly evidenceIdentity: EvidenceDependencyIdentity | null;
    readonly payload?: unknown;
}

export interface CachedCandidateEvidence {
    readonly identity: EvidenceDependencyIdentity;
    readonly artifactDigest: string;
    readonly artifact?: GaussianEvidenceArtifact;
}

export interface CandidateCorrectionProductionInput {
    readonly views: readonly CandidateCorrectionView[];
    readonly includedViewIds: readonly string[];
    readonly reuseViewIds: readonly string[];
    readonly recomputeViewIds: readonly string[];
    readonly cachedEvidence: ReadonlyMap<string, CachedCandidateEvidence>;
}

export interface CandidateCorrectionProductionResult {
    readonly candidate: ReferenceCandidateArtifact;
    readonly publicationBinding: CandidatePublicationBinding;
    readonly evidence: Readonly<
        Record<string, CachedCandidateEvidence>
    >;
}

export interface CandidateCorrectionState {
    readonly mode: 'candidate' | 'correcting';
    readonly status: 'idle' | 'updating' | 'failed';
    readonly candidate: CandidatePublicationState;
    readonly errorMessage?: string;
}

export type CandidateCorrectionListener = (
    state: CandidateCorrectionState
) => void;

export interface AISelectCandidateCorrectionControllerOptions {
    readonly dirtyState: AISelectDirtyStateTracker;
    readonly candidatePublications: CandidatePublicationStore;
    readonly resolveCurrentViews: () => readonly CandidateCorrectionView[];
    readonly produceCandidate: (
        input: CandidateCorrectionProductionInput
    ) => Promise<CandidateCorrectionProductionResult>;
}

const copyEvidence = (
    value: CachedCandidateEvidence
): CachedCandidateEvidence =>
    Object.freeze({
        identity: Object.freeze({ ...value.identity }),
        artifactDigest: value.artifactDigest,
        ...(value.artifact === undefined ? {} : { artifact: value.artifact })
    });

const messageFor = (error: unknown): string =>
    error instanceof Error && error.message.length > 0
        ? error.message
        : 'AI Select could not update the 3D Candidate.';

/**
 * Owns the Ticket 15 pre-apply correction and explicit Re-Lift lifecycle.
 * It plans exact per-view Evidence reuse before delegating production, then
 * publishes only the complete returned Candidate transaction. Correction is
 * presentation state: entering it never changes Stable inputs or Candidate.
 */
export class AISelectCandidateCorrectionController {
    private readonly dirtyState: AISelectDirtyStateTracker;
    private readonly candidatePublications: CandidatePublicationStore;
    private readonly resolveCurrentViews: () => readonly CandidateCorrectionView[];
    private readonly produceCandidate: (
        input: CandidateCorrectionProductionInput
    ) => Promise<CandidateCorrectionProductionResult>;
    private readonly cachedEvidence = new Map<
        string,
        CachedCandidateEvidence
    >();
    private readonly listeners = new Set<CandidateCorrectionListener>();
    private mode: CandidateCorrectionState['mode'] = 'candidate';
    private status: CandidateCorrectionState['status'] = 'idle';
    private errorMessage: string | undefined;
    private updateOrdinal = 0;

    constructor(options: AISelectCandidateCorrectionControllerOptions) {
        this.dirtyState = options.dirtyState;
        this.candidatePublications = options.candidatePublications;
        this.resolveCurrentViews = options.resolveCurrentViews;
        this.produceCandidate = options.produceCandidate;
        this.candidatePublications.subscribe(() => this.publish());
    }

    get state(): CandidateCorrectionState {
        return Object.freeze({
            mode: this.mode,
            status: this.status,
            candidate: this.candidatePublications.presentationState,
            ...(this.errorMessage === undefined
                ? {}
                : { errorMessage: this.errorMessage })
        });
    }

    get cachedEvidenceViewIds(): readonly string[] {
        return Object.freeze([...this.cachedEvidence.keys()].sort());
    }

    subscribe(listener: CandidateCorrectionListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    rememberPublishedEvidence(
        values: Readonly<Record<string, CachedCandidateEvidence>>
    ): void {
        for (const [viewId, value] of Object.entries(values)) {
            this.cachedEvidence.set(viewId, copyEvidence(value));
        }
    }

    beginCorrection(): void {
        if (this.candidatePublications.presentationState.status !== 'current') {
            throw new Error(
                'AI Select can fix only a current 3D Candidate.'
            );
        }
        this.mode = 'correcting';
        this.status = 'idle';
        this.errorMessage = undefined;
        this.publish();
    }

    noteEditingMaskChanged(_viewId: string): void {
        this.dirtyState.markEditingMaskChanged();
    }

    async updateCandidate(): Promise<void> {
        if (this.status === 'updating') {
            throw new Error('AI Select is already updating the 3D Candidate.');
        }
        const views = this.resolveCurrentViews();
        const included = views
            .filter(
                (view) =>
                    view.participation === 'included' &&
                    view.stableMaskDigest !== null &&
                    view.evidenceIdentity !== null
            )
            .sort((left, right) => left.viewId.localeCompare(right.viewId));
        if (included.length === 0) {
            throw new Error(
                'AI Select requires at least one Included Stable View before updating the 3D Candidate.'
            );
        }
        const reuseViewIds: string[] = [];
        const recomputeViewIds: string[] = [];
        for (const view of included) {
            const cached = this.cachedEvidence.get(view.viewId);
            if (
                cached !== undefined &&
                areEvidenceIdentitiesEqual(
                    cached.identity,
                    view.evidenceIdentity
                )
            ) {
                reuseViewIds.push(view.viewId);
            } else {
                recomputeViewIds.push(view.viewId);
            }
        }
        const ordinal = ++this.updateOrdinal;
        this.status = 'updating';
        this.errorMessage = undefined;
        this.publish();
        try {
            const result = await this.produceCandidate({
                views: Object.freeze([...views]),
                includedViewIds: Object.freeze(
                    included.map((view) => view.viewId)
                ),
                reuseViewIds: Object.freeze(reuseViewIds),
                recomputeViewIds: Object.freeze(recomputeViewIds),
                cachedEvidence: new Map(this.cachedEvidence)
            });
            if (ordinal !== this.updateOrdinal) {
                return;
            }
            const currentIncluded = this.resolveCurrentViews()
                .filter(
                    (view) =>
                        view.participation === 'included' &&
                        view.stableMaskDigest !== null &&
                        view.evidenceIdentity !== null
                )
                .sort((left, right) =>
                    left.viewId.localeCompare(right.viewId)
                );
            if (
                currentIncluded.length !== included.length ||
                currentIncluded.some(
                    (view, index) =>
                        view.viewId !== included[index].viewId ||
                        !areEvidenceIdentitiesEqual(
                            view.evidenceIdentity,
                            included[index].evidenceIdentity
                        )
                )
            ) {
                throw new Error(
                    'AI Select inputs changed while the 3D Candidate was updating.'
                );
            }
            this.candidatePublications.publish(
                result.candidate,
                result.publicationBinding
            );
            this.rememberPublishedEvidence(result.evidence);
            this.mode = 'candidate';
            this.status = 'idle';
            this.errorMessage = undefined;
            this.publish();
        } catch (error) {
            if (ordinal === this.updateOrdinal) {
                this.status = 'failed';
                this.errorMessage = messageFor(error);
                this.publish();
            }
            throw error;
        }
    }

    reset(): void {
        this.updateOrdinal += 1;
        this.cachedEvidence.clear();
        this.mode = 'candidate';
        this.status = 'idle';
        this.errorMessage = undefined;
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
