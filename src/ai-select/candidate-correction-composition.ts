import type { AISelectAnchorController } from './anchor-controller';
import { cameraBindingDigest } from './camera-binding';
import {
    AISelectCandidateCorrectionController,
    type CandidateCorrectionProductionInput,
    type CandidateCorrectionView
} from './candidate-correction';
import type { CandidatePublicationStore } from './candidate-publication';
import {
    referenceContributorEvidenceBackendId,
    referenceEvidencePolicyDigest,
    referenceEvidenceRasterImplementationId,
    referenceEvidenceRuntimeBuildId,
    type AISelectCandidateReLiftProvider,
    type CandidateReLiftViewInput
} from './candidate-re-lift';
import {
    createEvidenceWorkingSet,
    rebindGaussianEvidenceArtifactForExactRestoration
} from './gaussian-evidence-contract';
import type { AISelectGeneratedViewController } from './generated-view-controller';
import type { AISelectMaskController } from './mask-controller';

export interface AISelectCandidateCorrectionCompositionOptions {
    readonly anchor: AISelectAnchorController;
    readonly masks: AISelectMaskController;
    readonly generatedViews: AISelectGeneratedViewController;
    readonly candidatePublications: CandidatePublicationStore;
    readonly provider: AISelectCandidateReLiftProvider;
}

/** Compose the browser side of Ticket 15 outside the editor composition root. */
export const createAISelectCandidateCorrectionController = (
    options: AISelectCandidateCorrectionCompositionOptions
): AISelectCandidateCorrectionController<CandidateReLiftViewInput> => {
    const resolveViews =
        (): readonly CandidateCorrectionView<CandidateReLiftViewInput>[] => {
            const anchorState = options.anchor.state;
            const context = anchorState.context;
            const anchor = anchorState.anchor;
            const snapshot = options.anchor.getAnchorSnapshot();
            if (
                context === null ||
                context.lifecycle !== 'active' ||
                anchor === null ||
                snapshot === null
            ) {
                return [];
            }
            const stableGaussianIds = [...snapshot.stableIds].sort(
                (left, right) => left - right
            );
            const evidenceWorkingSet = createEvidenceWorkingSet({
                targetSplatId: context.target.splatId,
                // This reference slice conservatively classifies the complete
                // Active Splat. It deliberately withholds formal Coverage until
                // a true target-local Core Target builder exists.
                coreTargetStableIds: stableGaussianIds,
                contextStableGaussianIds: []
            });
            const requestBinding = Object.freeze({
                targetContextId: context.targetContextId,
                contextRevision: context.revision,
                dependencyToken: context.dependencyToken
            });
            const createView = (input: {
                readonly viewId: string;
                readonly cameraBinding: CandidateReLiftViewInput['cameraBinding'];
                readonly rgbDigest: string;
                readonly participation: 'included' | 'excluded';
                readonly stableMask: CandidateReLiftViewInput['stableMask'];
            }): CandidateCorrectionView<CandidateReLiftViewInput> => {
                const bindingDigest = cameraBindingDigest(input.cameraBinding);
                const currentInput = Object.freeze({
                    requestBinding,
                    targetSplatId: context.target.splatId,
                    view: Object.freeze({
                        viewId: input.viewId,
                        renderStatus: 'ready' as const,
                        participation: input.participation,
                        cameraBindingDigest: bindingDigest,
                        rgbDigest: input.rgbDigest,
                        stableMaskDigest: input.stableMask.digest
                    }),
                    evidencePolicyDigest: referenceEvidencePolicyDigest,
                    renderWorkingSet: Object.freeze({
                        targetSplatId: context.target.splatId,
                        dependencyToken: context.dependencyToken,
                        cameraBindingDigest: bindingDigest,
                        renderWorkingSetToken: snapshot.contentDigest,
                        stableGaussianIds,
                        completeness: 'complete' as const
                    }),
                    evidenceWorkingSet,
                    rasterImplementationId:
                        referenceEvidenceRasterImplementationId,
                    evidenceBackendKind: 'reference-contributor' as const,
                    evidenceBackendId: referenceContributorEvidenceBackendId,
                    runtimeBuildId: referenceEvidenceRuntimeBuildId
                });
                return Object.freeze({
                    viewId: input.viewId,
                    participation: input.participation,
                    stableMaskDigest: input.stableMask.digest,
                    evidenceIdentity: Object.freeze({
                        viewId: input.viewId,
                        cameraBindingDigest: bindingDigest,
                        rgbDigest: input.rgbDigest,
                        stableMaskDigest: input.stableMask.digest,
                        evidencePolicyDigest: referenceEvidencePolicyDigest,
                        renderWorkingSetToken: snapshot.contentDigest,
                        evidenceWorkingSetToken:
                            evidenceWorkingSet.evidenceWorkingSetToken,
                        rasterImplementationId:
                            referenceEvidenceRasterImplementationId,
                        evidenceBackendKind: 'reference-contributor',
                        evidenceBackendId:
                            referenceContributorEvidenceBackendId,
                        runtimeBuildId: referenceEvidenceRuntimeBuildId
                    }),
                    payload: Object.freeze({
                        currentInput,
                        cameraBinding: input.cameraBinding,
                        stableMask: input.stableMask
                    })
                });
            };
            const views: CandidateCorrectionView<CandidateReLiftViewInput>[] =
                [];
            const anchorMask = options.masks.state.stableMask;
            if (
                anchor.renderStatus === 'ready' &&
                anchor.rgb !== undefined &&
                anchorMask !== null
            ) {
                views.push(
                    createView({
                        viewId: anchor.viewId,
                        cameraBinding: anchor.cameraBinding,
                        rgbDigest: anchor.rgb.digest,
                        participation: 'included',
                        stableMask: anchorMask.artifact
                    })
                );
            }
            for (const view of options.generatedViews.state.views) {
                if (
                    view.renderStatus !== 'ready' ||
                    view.rgb === undefined ||
                    view.stableMaskDigest === undefined
                ) {
                    continue;
                }
                const stableMask = options.masks.maskRegistry.viewState(
                    view.viewId,
                    view.rgb.digest
                ).stableMask;
                if (stableMask !== null) {
                    views.push(
                        createView({
                            viewId: view.viewId,
                            cameraBinding: view.cameraBinding,
                            rgbDigest: view.rgb.digest,
                            participation: view.participation,
                            stableMask: stableMask.artifact
                        })
                    );
                }
            }
            return Object.freeze(
                views.sort((left, right) =>
                    left.viewId.localeCompare(right.viewId)
                )
            );
        };

    let nextAttempt = 0;
    const controller = new AISelectCandidateCorrectionController({
        dirtyState: options.masks.dirtyState,
        candidatePublications: options.candidatePublications,
        isTargetActive: () => options.anchor.isTargetActive(),
        resolveCurrentViews: resolveViews,
        produceCandidate: async (
            input: CandidateCorrectionProductionInput<CandidateReLiftViewInput>
        ) => {
            const views = input.views.map((view) => {
                const cachedArtifact = input.cachedEvidence.get(
                    view.viewId
                )?.artifact;
                const currentCachedArtifact =
                    cachedArtifact === undefined
                        ? undefined
                        : rebindGaussianEvidenceArtifactForExactRestoration(
                              cachedArtifact,
                              view.payload.currentInput.requestBinding
                          );
                return Object.freeze({
                    ...view.payload,
                    ...(currentCachedArtifact === undefined
                        ? {}
                        : { cachedArtifact: currentCachedArtifact })
                });
            });
            const first = views[0];
            const snapshot = options.anchor.getAnchorSnapshot();
            if (first === undefined || snapshot === null) {
                throw new Error(
                    'AI Select requires an active Scene Snapshot before Candidate Re-Lift.'
                );
            }
            nextAttempt += 1;
            for (const viewId of input.recomputeViewIds) {
                const identity = input.views.find(
                    (view) => view.viewId === viewId
                )?.evidenceIdentity;
                if (identity !== null && identity !== undefined) {
                    options.masks.evidenceRegistry.markPending(identity);
                }
            }
            let response;
            try {
                response = await options.provider.produceCandidateReLift({
                    liftAttemptId: `candidate-re-lift-${nextAttempt}`,
                    snapshot,
                    requestBinding: first.currentInput.requestBinding,
                    targetSplatId: first.currentInput.targetSplatId,
                    classificationUniverseStableGaussianIds: Object.freeze(
                        [...snapshot.stableIds].sort(
                            (left, right) => left - right
                        )
                    ),
                    classificationScopeStableGaussianIds:
                        first.currentInput.evidenceWorkingSet.stableGaussianIds,
                    evidenceWorkingSet: first.currentInput.evidenceWorkingSet,
                    views: Object.freeze(views)
                });
            } catch (error) {
                for (const viewId of input.recomputeViewIds) {
                    const identity = input.views.find(
                        (view) => view.viewId === viewId
                    )?.evidenceIdentity;
                    if (identity !== null && identity !== undefined) {
                        options.masks.evidenceRegistry.markFailed(
                            identity,
                            error instanceof Error
                                ? error.message
                                : 'AI Select Evidence production failed.'
                        );
                    }
                }
                throw error;
            }
            if (!options.anchor.acceptsTargetBinding(response.requestBinding)) {
                throw new Error(
                    'AI Select discarded a stale Candidate Re-Lift result.'
                );
            }
            return {
                candidate: response.candidate,
                publicationBinding: response.candidate.publicationBinding,
                evidence: Object.fromEntries(
                    response.evidence.map((entry) => [
                        entry.viewId,
                        {
                            identity: {
                                viewId: entry.viewId,
                                cameraBindingDigest:
                                    entry.artifact.cameraBindingDigest,
                                rgbDigest: entry.artifact.rgbDigest,
                                stableMaskDigest:
                                    entry.artifact.stableMaskDigest,
                                evidencePolicyDigest:
                                    entry.artifact.evidencePolicyDigest,
                                renderWorkingSetToken:
                                    entry.artifact.renderWorkingSetToken,
                                evidenceWorkingSetToken:
                                    entry.artifact.evidenceWorkingSetToken,
                                rasterImplementationId:
                                    entry.artifact.rasterImplementationId,
                                evidenceBackendKind:
                                    entry.artifact.evidenceBackendKind,
                                evidenceBackendId:
                                    entry.artifact.evidenceBackendId,
                                runtimeBuildId: entry.artifact.runtimeBuildId
                            },
                            artifactDigest: entry.artifact.artifactDigest,
                            artifact: entry.artifact
                        }
                    ])
                ),
                publishRelatedProducts: () => {
                    for (const entry of response.evidence) {
                        options.masks.evidenceRegistry.markReady({
                            viewId: entry.viewId,
                            rgbDigest: entry.artifact.rgbDigest,
                            stableMaskDigest: entry.artifact.stableMaskDigest,
                            evidencePolicyDigest:
                                entry.artifact.evidencePolicyDigest
                        });
                    }
                }
            };
        }
    });
    let targetContextId: string | null = null;
    options.anchor.subscribe((state) => {
        const currentId = state.context?.targetContextId ?? null;
        if (currentId !== targetContextId) {
            targetContextId = currentId;
            controller.reset();
        }
    });
    return controller;
};
