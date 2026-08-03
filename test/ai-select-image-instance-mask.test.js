const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const {
    createCompanionRgbArtifactRef,
    createImageInstancePromptArtifact,
    createImageInstanceMaskResult,
    createImageInstanceMaskPublicationCommand,
    inferImageInstanceMask,
    isImageInstanceMaskRequest,
    isImageInstanceMaskResult,
    isImageInstanceRgbInput,
    isImageInstancePromptArtifact,
    isImageInstanceMaskRequestIdentity,
    imageInstanceMaskRequestIdentityDigest,
    imageInstanceMaskResultMatchesRequest,
    imageInstanceMaskPublicationCommandMatchesArtifacts,
    resolveImageInstanceMaskRefinementRef,
    previousLogitsRefMatchesImageInstanceMaskRequest
} = require('../.test-dist/src/ai-select/image-instance-mask.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    isPreviousPredictionLogitsRef,
    previousPredictionLogitsRefDigest
} = require('../.test-dist/src/ai-select/previous-logits-ref.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;
const contractVectors = JSON.parse(
    readFileSync(
        'test/fixtures/ai-select-image-instance-mask-contract-vectors.json',
        'utf8'
    )
);

test('a pixel-bound Image Instance Prompt artifact is canonical and digest-bound', () => {
    const artifact = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: 'target-1',
        contextRevision: 4,
        viewId: 'view-1',
        rgbDigest: digest('a'),
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [{ xPx: 2, yPx: 3 }],
        negativePoints: [],
        positiveBox: { x0Px: 1, y0Px: 1, x1Px: 6, y1Px: 5 },
        multimaskOutput: false
    });

    assert.ok(isImageInstancePromptArtifact(artifact));
    assert.equal(
        artifact.artifactDigest,
        'sha256:c86a598d516d70eacc12049d4cadd5dfacd8ff5adae8de9bb76f6d2223d87b7d'
    );
});

test('shared golden vectors distinguish valid, stale, and Companion-replacement identities', () => {
    const { artifactDigest, ...promptInput } = contractVectors.prompt;
    const { artifactDigest: unicodeArtifactDigest, ...unicodePromptInput } =
        contractVectors.unicodePrompt;
    const { refDigest, ...refInput } = contractVectors.previousLogitsRef;

    assert.ok(isImageInstancePromptArtifact(contractVectors.prompt));
    assert.equal(
        createImageInstancePromptArtifact(promptInput).artifactDigest,
        artifactDigest
    );
    assert.ok(isImageInstancePromptArtifact(contractVectors.unicodePrompt));
    assert.equal(
        createImageInstancePromptArtifact(unicodePromptInput).artifactDigest,
        unicodeArtifactDigest
    );
    assert.ok(isImageInstanceMaskRequestIdentity(contractVectors.identity));
    assert.ok(
        isImageInstanceMaskRequestIdentity(contractVectors.staleIdentity)
    );
    assert.ok(
        isImageInstanceMaskRequestIdentity(contractVectors.replacementIdentity)
    );
    assert.equal(
        imageInstanceMaskRequestIdentityDigest(contractVectors.identity),
        contractVectors.identityDigest
    );
    assert.equal(
        imageInstanceMaskRequestIdentityDigest(contractVectors.staleIdentity),
        contractVectors.staleIdentityDigest
    );
    assert.equal(
        imageInstanceMaskRequestIdentityDigest(
            contractVectors.replacementIdentity
        ),
        contractVectors.replacementIdentityDigest
    );
    assert.ok(isPreviousPredictionLogitsRef(contractVectors.previousLogitsRef));
    assert.equal(previousPredictionLogitsRefDigest(refInput), refDigest);
    const { resultDigest, ...resultInput } = contractVectors.result;
    assert.ok(isImageInstanceMaskResult(contractVectors.result));
    assert.equal(
        createImageInstanceMaskResult(resultInput).resultDigest,
        resultDigest
    );
});

test('shared numeric bounds reject values that cannot cross the browser boundary', () => {
    const { artifactDigest: _artifactDigest, ...promptInput } =
        contractVectors.unicodePrompt;
    const { largestSafeInteger, firstUnsafeInteger } =
        contractVectors.numericBoundaries;

    assert.ok(
        isImageInstancePromptArtifact(
            createImageInstancePromptArtifact({
                ...promptInput,
                contextRevision: largestSafeInteger
            })
        )
    );
    assert.throws(() =>
        createImageInstancePromptArtifact({
            ...promptInput,
            contextRevision: firstUnsafeInteger
        })
    );
    assert.throws(() =>
        createImageInstancePromptArtifact({
            ...promptInput,
            targetContextId: contractVectors.invalidStrings.loneHighSurrogate
        })
    );
});

const pngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC';
const pngBytes = Uint8Array.from(Buffer.from(pngBase64, 'base64'));
const rgbDigest = sha256Digest(pngBytes);

const request = (overrides = {}) => {
    const identity = {
        targetContextId: 'target-1',
        contextRevision: 4,
        viewId: 'view-1',
        rgbDigest,
        promptArtifactDigest: digest('d'),
        adapterId: 'sam3-image-instance/v1',
        modelManifestDigest: 'sam3-image-manifest-v1',
        runtimeDigest: digest('e'),
        companionInstanceId: 'companion-1',
        inferenceAttemptId: 'attempt-1'
    };
    const prompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: identity.targetContextId,
        contextRevision: identity.contextRevision,
        viewId: identity.viewId,
        rgbDigest: identity.rgbDigest,
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [{ xPx: 0, yPx: 0 }],
        negativePoints: [],
        multimaskOutput: true
    });
    return {
        schemaVersion: 1,
        identity: {
            ...identity,
            promptArtifactDigest: prompt.artifactDigest
        },
        rgb: {
            rgbDigest,
            width: 1,
            height: 1,
            artifact: {
                pngBase64,
                digest: rgbDigest,
                width: 1,
                height: 1
            }
        },
        prompt,
        ...overrides
    };
};

test('the provider boundary admits only a resolvable RGB artifact or Companion reference', async () => {
    const artifactRequest = request();
    assert.ok(isImageInstanceMaskRequest(artifactRequest));

    const companionRequest = request({
        rgb: {
            rgbDigest,
            width: 1,
            height: 1,
            companionRgbRef: createCompanionRgbArtifactRef({
                schemaVersion: 1,
                companionInstanceId: 'companion-1',
                stateId: 'rgb-state-1',
                rgbDigest,
                width: 1,
                height: 1
            })
        }
    });
    assert.ok(isImageInstanceMaskRequest(companionRequest));

    const provider = {
        calls: 0,
        async infer() {
            this.calls += 1;
            throw new Error('The provider must not run for invalid RGB input.');
        }
    };
    const digestOnly = request({
        rgb: { rgbDigest, width: 1, height: 1 }
    });
    const mismatched = request({
        rgb: {
            ...artifactRequest.rgb,
            artifact: { ...artifactRequest.rgb.artifact, width: 2 }
        }
    });

    assert.ok(!isImageInstanceMaskRequest(digestOnly));
    assert.ok(!isImageInstanceMaskRequest(mismatched));
    assert.ok(
        !isImageInstanceRgbInput({
            rgbDigest: contractVectors.invalidRgb.missingImageDataDigest,
            width: 1,
            height: 1,
            artifact: {
                pngBase64: contractVectors.invalidRgb.missingImageDataPngBase64,
                digest: contractVectors.invalidRgb.missingImageDataDigest,
                width: 1,
                height: 1
            }
        })
    );
    await assert.rejects(() => inferImageInstanceMask(provider, digestOnly));
    await assert.rejects(() => inferImageInstanceMask(provider, mismatched));
    assert.equal(provider.calls, 0);
});

const maskArtifact = () => {
    const bytes = new Uint8Array([1]);
    return {
        encoding: maskBitsetEncoding,
        width: 1,
        height: 1,
        data: btoa(String.fromCharCode(...bytes)),
        digest: sha256Digest(bytes)
    };
};

const previousLogitsRef = (identity) => {
    const payload = {
        schemaVersion: 1,
        companionInstanceId: identity.companionInstanceId,
        stateId: 'logits-state-1',
        targetContextId: identity.targetContextId,
        viewId: identity.viewId,
        rgbDigest: identity.rgbDigest,
        sourceInferenceAttemptId: 'source-attempt-1',
        sourceCandidateId: 'source-candidate-1',
        adapterRuntimeDigest: identity.runtimeDigest,
        shape: [1, 288, 288],
        dtype: 'float32',
        dataDigest: digest('f')
    };
    return {
        ...payload,
        refDigest: previousPredictionLogitsRefDigest(payload)
    };
};

const requestWithPrompt = (prompt) => {
    const base = request();
    return {
        ...base,
        identity: {
            ...base.identity,
            promptArtifactDigest: prompt.artifactDigest
        },
        prompt
    };
};

test('a positive Box can seed single-mask inference without a Point', () => {
    const boxOnlyPrompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: 'target-1',
        contextRevision: 4,
        viewId: 'view-1',
        rgbDigest,
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [],
        negativePoints: [],
        positiveBox: { x0Px: 0, y0Px: 0, x1Px: 1, y1Px: 1 },
        multimaskOutput: false
    });
    const negativeOnlyPrompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: 'target-1',
        contextRevision: 4,
        viewId: 'view-1',
        rgbDigest,
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [],
        negativePoints: [{ xPx: 0, yPx: 0 }],
        multimaskOutput: false
    });

    assert.ok(isImageInstanceMaskRequest(requestWithPrompt(boxOnlyPrompt)));
    assert.ok(
        !isImageInstanceMaskRequest(requestWithPrompt(negativeOnlyPrompt))
    );
});

test('a completed result is cardinality-bound, semantically unavailable, and inference-only', async () => {
    const imageRequest = request();
    const available = createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: imageRequest.identity,
        masks: [maskArtifact()],
        modelScores: [0.75],
        previousLogitsRefs: [previousLogitsRef(imageRequest.identity)],
        diagnostics: { outcome: 'available' }
    });
    assert.ok(isImageInstanceMaskResult(available));
    assert.ok(imageInstanceMaskResultMatchesRequest(available, imageRequest));

    const unavailable = createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: imageRequest.identity,
        masks: [],
        modelScores: [],
        diagnostics: { outcome: 'unavailable' }
    });
    assert.ok(isImageInstanceMaskResult(unavailable));
    assert.ok(imageInstanceMaskResultMatchesRequest(unavailable, imageRequest));

    const invalidTechnicalPartial = {
        ...available,
        diagnostics: { outcome: 'unavailable' },
        resultDigest: available.resultDigest
    };
    assert.ok(!isImageInstanceMaskResult(invalidTechnicalPartial));
    assert.ok(!isImageInstanceMaskResult({ ...available, assessment: {} }));
    assert.ok(!isImageInstanceMaskResult({ ...available, candidate: {} }));

    const failedProvider = {
        async infer() {
            throw new Error('out of memory');
        }
    };
    await assert.rejects(() =>
        inferImageInstanceMask(failedProvider, imageRequest)
    );
});

test('the contracts reject removed prompt fields and preserve exact opaque logits lineage', async () => {
    const baseRequest = request();
    const ref = previousLogitsRef(baseRequest.identity);
    const refinementPrompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: baseRequest.identity.targetContextId,
        contextRevision: baseRequest.identity.contextRevision,
        viewId: baseRequest.identity.viewId,
        rgbDigest: baseRequest.identity.rgbDigest,
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [{ xPx: 0, yPx: 0 }],
        negativePoints: [],
        previousLogitsRefDigest: ref.refDigest,
        multimaskOutput: false
    });
    const refinementRequest = requestWithPrompt(refinementPrompt);

    assert.ok(isImageInstanceMaskRequest(refinementRequest));
    assert.ok(
        previousLogitsRefMatchesImageInstanceMaskRequest(ref, refinementRequest)
    );
    assert.deepEqual(
        resolveImageInstanceMaskRefinementRef(
            refinementRequest,
            'companion-1',
            (refDigest) => (refDigest === ref.refDigest ? ref : undefined)
        ),
        ref
    );
    assert.equal(
        resolveImageInstanceMaskRefinementRef(
            refinementRequest,
            'companion-1',
            () => undefined
        ),
        undefined
    );
    let staleResolverCalled = false;
    assert.throws(() =>
        resolveImageInstanceMaskRefinementRef(
            refinementRequest,
            'companion-2',
            () => {
                staleResolverCalled = true;
                return ref;
            }
        )
    );
    assert.equal(staleResolverCalled, false);
    let providerRequest;
    await inferImageInstanceMask(
        {
            async infer(inferenceRequest) {
                providerRequest = inferenceRequest;
                return createImageInstanceMaskResult({
                    schemaVersion: 1,
                    requestIdentity: inferenceRequest.identity,
                    masks: [maskArtifact()],
                    modelScores: [0.8],
                    diagnostics: {
                        outcome: 'available',
                        refinementFallback: true
                    }
                });
            }
        },
        refinementRequest
    );
    assert.equal(providerRequest.prompt.previousLogitsRefDigest, ref.refDigest);
    assert.equal(Object.hasOwn(providerRequest, 'previousLogitsRef'), false);
    assert.ok(
        !previousLogitsRefMatchesImageInstanceMaskRequest(ref, {
            ...refinementRequest,
            identity: {
                ...refinementRequest.identity,
                companionInstanceId: 'companion-2'
            }
        })
    );
    assert.ok(
        !isImageInstancePromptArtifact({
            ...refinementPrompt,
            negativeBox: { x0Px: 0, y0Px: 0, x1Px: 1, y1Px: 1 }
        })
    );
    assert.ok(
        !isImageInstancePromptArtifact({
            ...refinementPrompt,
            previousLogitsRef: { logitsBase64: 'raw-tensor-data' }
        })
    );
    assert.ok(
        !isImageInstanceMaskRequest({
            ...refinementRequest,
            previousLogitsRef: ref
        })
    );
});

test('result candidate cardinality follows the prompt multimask policy', () => {
    const multimaskRequest = request();
    const threeCandidates = createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: multimaskRequest.identity,
        masks: [maskArtifact(), maskArtifact(), maskArtifact()],
        modelScores: [0.9, 0.8, 0.7],
        diagnostics: { outcome: 'available' }
    });
    assert.ok(
        imageInstanceMaskResultMatchesRequest(threeCandidates, multimaskRequest)
    );
    assert.throws(() =>
        createImageInstanceMaskResult({
            schemaVersion: 1,
            requestIdentity: multimaskRequest.identity,
            masks: [
                maskArtifact(),
                maskArtifact(),
                maskArtifact(),
                maskArtifact()
            ],
            modelScores: [0.9, 0.8, 0.7, 0.6],
            diagnostics: { outcome: 'available' }
        })
    );

    const singleMaskPrompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: multimaskRequest.identity.targetContextId,
        contextRevision: multimaskRequest.identity.contextRevision,
        viewId: multimaskRequest.identity.viewId,
        rgbDigest: multimaskRequest.identity.rgbDigest,
        cameraBindingDigest: digest('b'),
        adapterCapabilityDigest: digest('c'),
        positivePoints: [{ xPx: 0, yPx: 0 }],
        negativePoints: [{ xPx: 0, yPx: 0 }],
        multimaskOutput: false
    });
    const singleMaskRequest = requestWithPrompt(singleMaskPrompt);
    const twoCandidates = createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: singleMaskRequest.identity,
        masks: [maskArtifact(), maskArtifact()],
        modelScores: [0.9, 0.8],
        diagnostics: { outcome: 'available' }
    });

    assert.ok(isImageInstanceMaskResult(twoCandidates));
    assert.ok(
        !imageInstanceMaskResultMatchesRequest(twoCandidates, singleMaskRequest)
    );
});

test('a publication command binds the chosen Mask and Review without putting either in provider output', () => {
    const imageRequest = request();
    const result = createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: imageRequest.identity,
        masks: [maskArtifact()],
        modelScores: [0.75],
        diagnostics: { outcome: 'available' }
    });
    const review = {
        status: 'good',
        reasons: [],
        actionableReasons: [],
        policyVersion: 'local-view-assessment/v2',
        inputIdentity: {
            rgbDigest: imageRequest.rgb.rgbDigest,
            stableMaskDigest: result.masks[0].digest,
            assessmentPolicyVersion: 'local-view-assessment/v2'
        },
        diagnostics: {
            framePixels: 1,
            foregroundPixels: 1,
            boundaryPixels: 1,
            boundaryContactRatio: 1,
            connectedComponents: 1,
            largestComponentRatio: 1,
            promptPointCount: 1,
            promptViolationCount: 0,
            boxSpillPixels: null,
            boxSpillRatio: null
        }
    };
    const command = createImageInstanceMaskPublicationCommand({
        schemaVersion: 1,
        targetContextId: imageRequest.identity.targetContextId,
        contextRevision: imageRequest.identity.contextRevision,
        viewId: imageRequest.identity.viewId,
        rgbDigest: imageRequest.identity.rgbDigest,
        promptArtifactDigest: imageRequest.prompt.artifactDigest,
        inferenceResultDigest: result.resultDigest,
        chosenMaskDigest: result.masks[0].digest,
        review,
        currentStableAuthority: 'automatic',
        publicationPolicyDigest: digest('9'),
        publicationAttemptId: 'publication-attempt-1'
    });

    assert.ok(
        imageInstanceMaskPublicationCommandMatchesArtifacts(command, {
            prompt: imageRequest.prompt,
            result
        })
    );
    assert.ok(
        !imageInstanceMaskPublicationCommandMatchesArtifacts(
            {
                ...command,
                chosenMaskDigest: digest('f')
            },
            { prompt: imageRequest.prompt, result }
        )
    );
});
