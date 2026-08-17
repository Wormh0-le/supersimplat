import type { AISelectAnchorController } from './anchor-controller';
import { cameraBindingDigest } from './camera-binding';
import {
    AISelectCandidateCorrectionController,
    type CandidateCorrectionProductionInput,
    type CandidateCorrectionView
} from './candidate-correction';
import type { CandidatePublicationStore } from './candidate-publication';
import {
    productionEvidencePolicyDigest,
    type AISelectCandidateReLiftProvider,
    type CandidateReLiftViewInput
} from './candidate-re-lift';
import {
    directEvidenceBackendId,
    directEvidenceRasterImplementationId,
    directEvidenceRuntimeBuildId,
    type AISelectDirectEvidenceProvider
} from './direct-evidence-service';
import {
    createEvidenceWorkingSet,
    isCurrentGaussianEvidenceArtifact,
    rebindGaussianEvidenceArtifactForExactRestoration
} from './gaussian-evidence-contract';
import type { AISelectGeneratedViewController } from './generated-view-controller';
import {
    liftReadinessBindingFromArtifact,
    type LiftReadinessStore
} from './lift-readiness';
import type { AISelectMaskController } from './mask-controller';

export interface AISelectCandidateCorrectionCompositionOptions {
    readonly anchor: AISelectAnchorController;
    readonly masks: AISelectMaskController;
    readonly generatedViews: AISelectGeneratedViewController;
    readonly candidatePublications: CandidatePublicationStore;
    readonly liftReadiness: LiftReadinessStore;
    readonly getProductionIdentityDigest: () => string | null;
    readonly provider: AISelectCandidateReLiftProvider &
        AISelectDirectEvidenceProvider;
}

type CandidateCorrectionEvidencePayload = CandidateReLiftViewInput;

/** Compose the browser side of Ticket 15 outside the editor composition root. */
export const createAISelectCandidateCorrectionController = (
    options: AISelectCandidateCorrectionCompositionOptions
): AISelectCandidateCorrectionController<CandidateCorrectionEvidencePayload> => {
    const resolveViews =
        (): readonly CandidateCorrectionView<CandidateCorrectionEvidencePayload>[] => {
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
            const renderStableGaussianIds = [...snapshot.stableIds].sort(
                (left, right) => left - right
            );
            const targetScope = snapshot.authoritativeRenderScope?.entries.find(
                (entry) => entry.role === 'target'
            );
            if (
                targetScope === undefined ||
                snapshot.authoritativeRenderScope?.targetSplatId !==
                    context.target.splatId
            ) {
                return [];
            }
            const targetStableGaussianIds = [...snapshot.stableIds]
                .slice(
                    targetScope.rowOffset,
                    targetScope.rowOffset + targetScope.rowCount
                )
                .sort((left, right) => left - right);
            const evidenceWorkingSet = createEvidenceWorkingSet({
                targetSplatId: context.target.splatId,
                // Every target row is initially eligible for Evidence writes;
                // visible non-target Splats remain render-only occluders. A
                // narrower hint-seeded set may use the same boundary expansion
                // contract without changing global render identity.
                coreTargetStableIds: targetStableGaussianIds,
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
                readonly renderWorkingSetToken: string;
                readonly renderStableGaussianIds: readonly number[];
            }): CandidateCorrectionView<CandidateCorrectionEvidencePayload> => {
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
                    evidencePolicyDigest: productionEvidencePolicyDigest,
                    renderWorkingSet: Object.freeze({
                        targetSplatId: context.target.splatId,
                        dependencyToken: context.dependencyToken,
                        cameraBindingDigest: bindingDigest,
                        renderWorkingSetToken: input.renderWorkingSetToken,
                        stableGaussianIds: input.renderStableGaussianIds,
                        completeness: 'complete' as const
                    }),
                    evidenceWorkingSet,
                    rasterImplementationId:
                        directEvidenceRasterImplementationId,
                    evidenceBackendKind: 'production-direct' as const,
                    evidenceBackendId: directEvidenceBackendId,
                    runtimeBuildId: directEvidenceRuntimeBuildId
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
                        evidencePolicyDigest: productionEvidencePolicyDigest,
                        renderWorkingSetToken: input.renderWorkingSetToken,
                        evidenceWorkingSetToken:
                            evidenceWorkingSet.evidenceWorkingSetToken,
                        rasterImplementationId:
                            directEvidenceRasterImplementationId,
                        evidenceBackendKind: 'production-direct',
                        evidenceBackendId: directEvidenceBackendId,
                        runtimeBuildId: directEvidenceRuntimeBuildId
                    }),
                    payload: Object.freeze({
                        currentInput,
                        cameraBinding: input.cameraBinding,
                        stableMask: input.stableMask
                    })
                });
            };
            const views: CandidateCorrectionView<CandidateCorrectionEvidencePayload>[] =
                [];
            const anchorMask = options.masks.state.stableMask;
            if (
                anchor.renderStatus === 'ready' &&
                anchor.rgb !== undefined &&
                anchor.renderWorkingSetToken !== undefined &&
                anchor.renderStableGaussianIds !== undefined &&
                anchorMask !== null
            ) {
                views.push(
                    createView({
                        viewId: anchor.viewId,
                        cameraBinding: anchor.cameraBinding,
                        rgbDigest: anchor.rgb.digest,
                        participation: 'included',
                        stableMask: anchorMask.artifact,
                        renderWorkingSetToken: anchor.renderWorkingSetToken,
                        renderStableGaussianIds: anchor.renderStableGaussianIds
                    })
                );
            }
            for (const view of options.generatedViews.state.views) {
                if (
                    view.renderStatus !== 'ready' ||
                    view.rgb === undefined ||
                    view.renderWorkingSetToken === undefined ||
                    view.renderStableGaussianIds === undefined ||
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
                            stableMask: stableMask.artifact,
                            renderWorkingSetToken: view.renderWorkingSetToken,
                            renderStableGaussianIds:
                                view.renderStableGaussianIds
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
            input: CandidateCorrectionProductionInput<CandidateCorrectionEvidencePayload>
        ) => {
            const first = input.views[0]?.payload;
            const snapshot = options.anchor.getAnchorSnapshot();
            if (first === undefined || snapshot === null) {
                throw new Error(
                    'AI Select requires an active Scene Snapshot before Candidate Re-Lift.'
                );
            }
            const productionIdentityDigest =
                options.getProductionIdentityDigest();
            if (productionIdentityDigest === null) {
                throw new Error(
                    'AI Select requires the accepted production identity before Candidate Re-Lift.'
                );
            }
            const generatedState = options.generatedViews.state;
            const generationState =
                generatedState.plannerStatus === 'failed'
                    ? 'unavailable'
                    : generatedState.views.some(
                            (view) =>
                                view.renderStatus === 'pending' ||
                                view.renderStatus === 'rendering' ||
                                view.promptStatus === 'synthesizing' ||
                                view.maskStatus === 'generating'
                        )
                      ? 'active'
                      : 'complete';
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
            const directEvidence = new Map<
                string,
                NonNullable<CandidateReLiftViewInput['cachedArtifact']>
            >();
            try {
                for (const view of input.views) {
                    if (view.participation !== 'included') {
                        continue;
                    }
                    const directInput = view.payload.currentInput;
                    const retained = input.cachedEvidence.get(
                        directInput.view.viewId
                    )?.artifact;
                    const rebound =
                        retained === undefined
                            ? undefined
                            : rebindGaussianEvidenceArtifactForExactRestoration(
                                  retained,
                                  directInput.requestBinding
                              );
                    const cachedArtifact =
                        rebound !== undefined &&
                        isCurrentGaussianEvidenceArtifact(rebound, directInput)
                            ? rebound
                            : undefined;
                    const direct = await options.provider.produceDirectEvidence(
                        {
                            evidenceAttemptId: `direct-evidence-${nextAttempt}-${view.viewId}`,
                            snapshot,
                            currentInput: directInput,
                            cameraBinding: view.payload.cameraBinding,
                            stableMask: view.payload.stableMask,
                            ...(cachedArtifact === undefined
                                ? {}
                                : { cachedArtifact })
                        }
                    );
                    directEvidence.set(
                        directInput.view.viewId,
                        direct.artifact
                    );
                }
                const candidateViews = input.views.map((view) => {
                    const artifact = directEvidence.get(view.viewId);
                    return Object.freeze({
                        currentInput: view.payload.currentInput,
                        cameraBinding: view.payload.cameraBinding,
                        stableMask: view.payload.stableMask,
                        ...(artifact === undefined
                            ? {}
                            : { cachedArtifact: artifact })
                    });
                });
                response = await options.provider.produceCandidateReLift({
                    liftAttemptId: `candidate-re-lift-${nextAttempt}`,
                    productionIdentityDigest,
                    generationState,
                    snapshot,
                    requestBinding: first.currentInput.requestBinding,
                    targetSplatId: first.currentInput.targetSplatId,
                    classificationUniverseStableGaussianIds: Object.freeze([
                        ...first.currentInput.evidenceWorkingSet
                            .stableGaussianIds
                    ]),
                    classificationScopeStableGaussianIds:
                        first.currentInput.evidenceWorkingSet.stableGaussianIds,
                    evidenceWorkingSet: first.currentInput.evidenceWorkingSet,
                    views: Object.freeze(candidateViews)
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
            const evidence = Object.fromEntries(
                [...directEvidence].map(([viewId, artifact]) => [
                    viewId,
                    {
                        identity: {
                            viewId,
                            cameraBindingDigest: artifact.cameraBindingDigest,
                            rgbDigest: artifact.rgbDigest,
                            stableMaskDigest: artifact.stableMaskDigest,
                            evidencePolicyDigest: artifact.evidencePolicyDigest,
                            renderWorkingSetToken:
                                artifact.renderWorkingSetToken,
                            evidenceWorkingSetToken:
                                artifact.evidenceWorkingSetToken,
                            rasterImplementationId:
                                artifact.rasterImplementationId,
                            evidenceBackendKind: artifact.evidenceBackendKind,
                            evidenceBackendId: artifact.evidenceBackendId,
                            runtimeBuildId: artifact.runtimeBuildId
                        },
                        artifactDigest: artifact.artifactDigest,
                        artifact
                    }
                ])
            );
            const publishReadiness = () => {
                const binding = liftReadinessBindingFromArtifact(
                    response.liftReadiness
                );
                options.masks.dirtyState.markLiftReadinessEvaluated();
                options.liftReadiness.publish(response.liftReadiness, binding);
            };
            if (response.status === 'not-ready') {
                return {
                    status: 'not-ready' as const,
                    evidence,
                    errorMessage:
                        'AI Select Lift Readiness is Not Ready for Candidate publication.',
                    publishPrerequisiteProducts: publishReadiness,
                    publishRelatedProducts: () => {
                        for (const [viewId, artifact] of directEvidence) {
                            options.masks.evidenceRegistry.markReady({
                                viewId,
                                rgbDigest: artifact.rgbDigest,
                                stableMaskDigest: artifact.stableMaskDigest,
                                evidencePolicyDigest:
                                    artifact.evidencePolicyDigest
                            });
                        }
                    }
                };
            }
            return {
                status: 'complete' as const,
                candidate: response.candidate,
                publicationBinding: response.candidate.publicationBinding,
                evidence,
                publishPrerequisiteProducts: publishReadiness,
                publishRelatedProducts: () => {
                    for (const [viewId, artifact] of directEvidence) {
                        options.masks.evidenceRegistry.markReady({
                            viewId,
                            rgbDigest: artifact.rgbDigest,
                            stableMaskDigest: artifact.stableMaskDigest,
                            evidencePolicyDigest: artifact.evidencePolicyDigest
                        });
                    }
                }
            };
        }
    });
    let targetRevisionKey: string | null = null;
    options.anchor.subscribe((state) => {
        const currentKey =
            state.context === null
                ? null
                : `${state.context.targetContextId}:${state.context.revision}`;
        if (currentKey !== targetRevisionKey) {
            targetRevisionKey = currentKey;
            controller.reset();
        }
    });
    let generatedViewIds = new Set<string>();
    options.generatedViews.subscribe((state) => {
        const currentViewIds = new Set(state.views.map((view) => view.viewId));
        for (const viewId of generatedViewIds) {
            if (!currentViewIds.has(viewId)) {
                controller.disposeCachedEvidence(viewId);
            }
        }
        generatedViewIds = currentViewIds;
    });
    return controller;
};
