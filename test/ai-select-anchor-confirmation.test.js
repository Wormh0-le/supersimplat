const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectMaskController
} = require('../.test-dist/src/ai-select/mask-controller.js');
const {
    AISelectAnchorConfirmationController
} = require('../.test-dist/src/ai-select/anchor-confirmation.js');
const {
    aiSelectEvidencePolicyVersion
} = require('../.test-dist/src/ai-select/evidence-state.js');
const {
    aiSelectSupportProbePolicyVersion
} = require('../.test-dist/src/ai-select/support-probe.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    createPromptAdapterCapabilities
} = require('../.test-dist/src/ai-select/prompt-state.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const target = (splatId = 'editor-splat:1') => ({ splatId });

const snapshot = {
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1'
    }
};

const editorCamera = () => ({
    targetSize: { width: 64, height: 48 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
    }
});

const cameraBinding = () => captureEditorCameraBinding(editorCamera());

const pngCrc32 = (bytes) => {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
};

const pngChunk = (type, data) => {
    const typeBytes = Buffer.from(type, 'ascii');
    const payload = Buffer.concat([typeBytes, data]);
    const length = Buffer.alloc(4);
    const checksum = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    checksum.writeUInt32BE(pngCrc32(payload));
    return Buffer.concat([length, payload, checksum]);
};

const pngBase64 = (width, height) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    return Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]).toString('base64');
};

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const input = (overrides = {}) => ({
    target: target(),
    dependencyToken: dependency(),
    getCurrentDependencyToken: () => dependency(),
    snapshot,
    cameraBinding: cameraBinding(),
    ...overrides
});

const bitsetArtifact = (width, height, foreground) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    for (const [x, y] of foreground) {
        const index = y * width + x;
        bytes[index >> 3] |= 1 << (index % 8);
    }
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    });
};

// A centered 16x16 block: valid area, one component, no boundary contact.
const solidForeground = (width, height) => {
    const foreground = [];
    const left = Math.floor(width / 2) - 8;
    const top = Math.floor(height / 2) - 8;
    for (let y = top; y < top + 16; y += 1) {
        for (let x = left; x < left + 16; x += 1) {
            foreground.push([x, y]);
        }
    }
    return foreground;
};

const maskResponseFor = (request, overrides = {}) => {
    const proposalPayload = {
        schemaVersion: 1,
        viewId: request.viewId,
        rgbDigest: request.rgb.digest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposals: [
            {
                proposalId: 'proposal-0',
                sourceIndex: 0,
                mask: bitsetArtifact(
                    request.rgb.width,
                    request.rgb.height,
                    solidForeground(request.rgb.width, request.rgb.height)
                ),
                promptConsistency: {
                    positivePointsSatisfied: true,
                    negativePointsSatisfied: true
                },
                rankingFeatures: {
                    promptConsistency: {
                        positivePointsSatisfied: true,
                        negativePointsSatisfied: true
                    },
                    eligible: true,
                    areaFraction:
                        256 / (request.rgb.width * request.rgb.height),
                    boundingBox: {
                        x0Px: request.rgb.width / 2 - 8,
                        y0Px: request.rgb.height / 2 - 8,
                        x1Px: request.rgb.width / 2 + 7,
                        y1Px: request.rgb.height / 2 + 7
                    },
                    connectedComponentCount: 1,
                    positivePointComponentIds: [0],
                    positivePointBoundaryDistances: [1],
                    pairwiseRelations: [],
                    boundaryContactFraction: 0,
                    compactness: Math.PI / 4,
                    boxFillRatios: [],
                    boxSpillRatios: [],
                    promptMaskOverlap: 1,
                    optionalSupportSanity: {
                        participated: false,
                        changedDecision: false
                    }
                }
            }
        ]
    };
    const proposalSet = {
        ...proposalPayload,
        digest: autoMaskProposalSetDigest(proposalPayload)
    };
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        cameraBindingDigest: request.cameraBindingDigest,
        rgbDigest: request.rgb.digest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        rankingPolicyVersion: request.rankingPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposalSet,
        proposalDecision: {
            schemaVersion: 1,
            viewId: request.viewId,
            rgbDigest: request.rgb.digest,
            promptStateDigest: request.promptState.digest,
            proposalSetDigest: proposalSet.digest,
            rankingPolicyVersion: anchorMaskRankingPolicyVersion,
            status: 'selected',
            selectedProposalId: 'proposal-0',
            alternativeProposalIds: ['proposal-0'],
            reasons: []
        },
        ...overrides
    };
};

const pointCapabilities = createPromptAdapterCapabilities({
    points: true,
    negativePoints: true,
    boxes: false,
    negativeBoxes: false,
    maskInput: false,
    negativeMaskConstraints: false,
    text: false,
    negativeText: false,
    multiCandidateOutput: false
});

const probeResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    viewId: request.viewId,
    supportProbeAttemptId: request.supportProbeAttemptId,
    cameraBinding: request.cameraBinding,
    rgbDigest: request.rgbDigest,
    stableMaskDigest: request.stableMask.digest,
    supportProbePolicyVersion: request.supportProbePolicyVersion,
    support: { computable: true, observedGaussianCount: 500 },
    ...overrides
});

const setup = async (options = {}) => {
    const rgbDigest = options.rgbDigest ?? `sha256:${'a'.repeat(64)}`;
    const renderRequests = [];
    const renderer = {
        renderAnchor: (request) => {
            renderRequests.push(request);
            return Promise.resolve({
                requestBinding: request.requestBinding,
                targetSplatId: request.target.splatId,
                sceneId: request.snapshot.sceneId,
                sceneVersion: request.snapshot.sceneVersion,
                renderConfigVersion: 'supersplat-effective-rgb-v1',
                renderAttemptId: request.renderAttemptId,
                viewId: 'anchor-view',
                cameraBinding: request.cameraBinding,
                rgb: {
                    pngBase64: pngBase64(
                        request.cameraBinding.projection.width,
                        request.cameraBinding.projection.height
                    ),
                    digest: rgbDigest,
                    width: request.cameraBinding.projection.width,
                    height: request.cameraBinding.projection.height
                },
                rgbRendererVersion: 'gsplat-rgb/v1',
                rendererId: 'gsplat'
            });
        }
    };
    const maskRequests = [];
    const maskProvider = {
        produceMaskProposals: (request) => {
            maskRequests.push(request);
            return Promise.resolve(maskResponseFor(request));
        }
    };
    let confirmation = null;
    const anchor = new AISelectAnchorController({
        renderer,
        isAnchorLocked: () => confirmation?.locked ?? false
    });
    await anchor.start(input());
    const mask = new AISelectMaskController({
        anchor,
        maskProvider,
        getModelManifestDigest: () => 'manifest-digest-1',
        getPromptAdapterCapabilities: () => pointCapabilities,
        isAnchorLocked: () => confirmation?.locked ?? false
    });
    const probeRequests = [];
    const supportProbe = {
        probeAnchorSupport:
            options.probeAnchorSupport ??
            ((request) => {
                probeRequests.push(request);
                return Promise.resolve(probeResponseFor(request));
            })
    };
    confirmation = new AISelectAnchorConfirmationController({
        anchor,
        mask,
        supportProbe
    });
    return { anchor, mask, confirmation, probeRequests, renderRequests };
};

const confirmStableMask = async (mask) => {
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const proposalId = mask.state.proposalDecision?.selectedProposalId;
    assert.ok(proposalId);
    mask.acceptProposal(proposalId);
    mask.confirmEditingMask();
    return mask.state.stableMask;
};

test('validation blocks missing Confirm prerequisites before probing', async () => {
    const { confirmation, probeRequests } = await setup();
    const result = await confirmation.validate();
    assert.ok(result.hardBlocks.includes('stable-mask-missing'));
    assert.equal(result.canConfirm, false);
    assert.equal(probeRequests.length, 0);
    assert.equal(confirmation.state.validationStatus, 'idle');
});

test('validation runs the versioned support probe with explicit input identity', async () => {
    const { anchor, mask, confirmation, probeRequests } = await setup();
    const stable = await confirmStableMask(mask);
    const result = await confirmation.validate();
    assert.equal(probeRequests.length, 1);
    const request = probeRequests[0];
    assert.equal(request.rgbDigest, `sha256:${'a'.repeat(64)}`);
    assert.equal(request.stableMask.digest, stable.artifact.digest);
    assert.equal(
        request.supportProbePolicyVersion,
        aiSelectSupportProbePolicyVersion
    );
    assert.equal(request.viewId, 'anchor-view');
    assert.ok(request.supportProbeAttemptId.length > 0);
    assert.equal(
        result.canConfirm,
        true,
        `unexpected hard blocks: ${result.hardBlocks}`
    );
    assert.deepEqual(result.softWarnings, []);
    assert.equal(confirmation.state.validationStatus, 'idle');
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('Confirm Anchor atomically publishes the fully bound record and locks', async () => {
    const { anchor, mask, confirmation, renderRequests } = await setup();
    const stable = await confirmStableMask(mask);
    const confirmed = await confirmation.confirmAnchor();
    const context = anchor.state.context;
    assert.equal(confirmed.targetContextId, context.targetContextId);
    assert.equal(confirmed.contextRevision, context.revision);
    assert.equal(confirmed.rgbDigest, `sha256:${'a'.repeat(64)}`);
    assert.equal(confirmed.stableMask.maskId, stable.maskId);
    assert.equal(confirmed.stableMask.artifact.digest, stable.artifact.digest);
    assert.equal(
        confirmed.maskEvidencePolicyVersion,
        aiSelectEvidencePolicyVersion
    );
    assert.deepEqual(confirmed.dependencyToken, dependency());
    assert.equal(confirmed.sceneId, 'editor-splat:1');
    assert.equal(confirmed.sceneVersion, 'snapshot-v1');
    assert.deepEqual(
        confirmed.cameraBinding,
        anchor.state.anchor.cameraBinding
    );
    assert.ok(Object.isFrozen(confirmed));
    // Complete Contributor identity is not part of the formal Anchor binding.
    for (const key of Object.keys(confirmed)) {
        assert.ok(!/contributor/i.test(key), `unexpected key ${key}`);
    }
    // The confirmed Anchor locks CameraBinding and Mask authoring.
    assert.equal(confirmation.locked, true);
    assert.throws(() =>
        anchor.updateAnchorCameraPose([
            1, 0, 0, 9, 0, 1, 0, 9, 0, 0, 1, 9, 0, 0, 0, 1
        ])
    );
    assert.throws(() =>
        mask.applyBrushStroke({ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' })
    );
    await assert.rejects(
        mask.addPrompt({ xPx: 1, yPx: 1, polarity: 'include' })
    );
    // The normal Confirm path never invokes another render or Contributor op.
    assert.equal(renderRequests.length, 1);
});

test('weak visible support stays a user-overridable soft warning', async () => {
    const probeRequests = [];
    const { mask, confirmation } = await setup({
        probeAnchorSupport: (request) => {
            probeRequests.push(request);
            return Promise.resolve(
                probeResponseFor(request, {
                    support: { computable: true, observedGaussianCount: 3 }
                })
            );
        }
    });
    await confirmStableMask(mask);
    await assert.rejects(confirmation.confirmAnchor(), /soft warning/i);
    assert.equal(confirmation.state.confirmedAnchor, null);
    assert.deepEqual(confirmation.state.validation.softWarnings, [
        'weak-visible-support'
    ]);
    const confirmed = await confirmation.confirmAnchor({
        overrideSoftWarnings: true
    });
    assert.equal(
        confirmation.state.confirmedAnchor?.rgbDigest,
        confirmed.rgbDigest
    );
    assert.equal(confirmation.locked, true);
});

test('Confirm Anchor re-validates against the latest exact revisions', async () => {
    const { mask, confirmation, probeRequests } = await setup();
    await confirmStableMask(mask);
    await confirmation.validate();
    assert.equal(probeRequests.length, 1);
    // Publish a newer Stable Mask revision after the first validation.
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    mask.confirmEditingMask();
    const latest = mask.state.stableMask;
    await confirmation.confirmAnchor();
    assert.equal(probeRequests.length, 2);
    assert.equal(probeRequests[1].stableMask.digest, latest.artifact.digest);
    assert.equal(
        confirmation.state.confirmedAnchor?.stableMask.artifact.digest,
        latest.artifact.digest
    );
});

test('a late probe response for superseded Mask identity is discarded', async () => {
    const gate = deferred();
    const { mask, confirmation } = await setup({
        probeAnchorSupport: (request) => {
            if (request.supportProbeAttemptId.endsWith('-1')) {
                return gate.promise;
            }
            return Promise.resolve(probeResponseFor(request));
        }
    });
    await confirmStableMask(mask);
    const validating = confirmation.validate();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(confirmation.state.validationStatus, 'validating');
    // A newer Stable Mask revision supersedes the in-flight probe.
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    mask.confirmEditingMask();
    gate.reject(new Error('late failure that must be ignored'));
    await validating;
    assert.equal(confirmation.state.validationStatus, 'idle');
    assert.equal(confirmation.state.validation, null);
    // A fresh validation probes the new Stable Mask revision.
    const result = await confirmation.validate();
    assert.equal(result.canConfirm, true);
});

test('a support-probe failure preserves RGB/Mask and supports recovery', async () => {
    let failures = 0;
    const { anchor, mask, confirmation } = await setup({
        probeAnchorSupport: (request) => {
            if (failures < 1) {
                failures += 1;
                return Promise.reject(new Error('probe backend down'));
            }
            return Promise.resolve(probeResponseFor(request));
        }
    });
    const stable = await confirmStableMask(mask);
    const result = await confirmation.validate();
    assert.equal(result, null);
    assert.equal(confirmation.state.validationStatus, 'failed');
    assert.match(confirmation.state.errorMessage, /probe backend down/);
    // RGB and Stable Mask stay intact; the View is never relabeled failed.
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    const recovered = await confirmation.validate();
    assert.equal(recovered.canConfirm, true);
    assert.equal(confirmation.state.validationStatus, 'idle');
});

test('no computable Gaussian support blocks Confirm Anchor', async () => {
    const { mask, confirmation } = await setup({
        probeAnchorSupport: (request) =>
            Promise.resolve(
                probeResponseFor(request, {
                    support: { computable: false, observedGaussianCount: 0 }
                })
            )
    });
    await confirmStableMask(mask);
    const result = await confirmation.validate();
    assert.ok(result.hardBlocks.includes('no-computable-gaussian-support'));
    await assert.rejects(confirmation.confirmAnchor());
    assert.equal(confirmation.state.confirmedAnchor, null);
    assert.equal(confirmation.locked, false);
});

test('a mismatching probe response fails validation without touching RGB', async () => {
    const { anchor, mask, confirmation } = await setup({
        probeAnchorSupport: (request) =>
            Promise.resolve(
                probeResponseFor(request, {
                    supportProbeAttemptId: 'forged-attempt'
                })
            )
    });
    await confirmStableMask(mask);
    const result = await confirmation.validate();
    assert.equal(result, null);
    assert.equal(confirmation.state.validationStatus, 'failed');
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('Adjust Anchor unlocks without destroying Anchor or Mask state', async () => {
    const { anchor, mask, confirmation } = await setup();
    const stable = await confirmStableMask(mask);
    await confirmation.confirmAnchor();
    assert.equal(confirmation.locked, true);
    confirmation.adjustAnchor();
    assert.equal(confirmation.locked, false);
    assert.equal(confirmation.state.confirmedAnchor, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    anchor.updateAnchorCameraPose([
        1, 0, 0, 9, 0, 1, 0, 9, 0, 0, 1, 9, 0, 0, 0, 1
    ]);
});

test('Restart disposes the confirmed Anchor and unlocks Mask authoring', async () => {
    const { anchor, mask, confirmation } = await setup();
    await confirmStableMask(mask);
    await confirmation.confirmAnchor();
    assert.equal(confirmation.locked, true);
    await anchor.restart(input());
    assert.equal(confirmation.locked, false);
    assert.equal(confirmation.state.confirmedAnchor, null);
    assert.equal(confirmation.state.validation, null);
    mask.applyBrushStroke({ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' });
    assert.equal(mask.state.editingMask.source, 'manual');
});
