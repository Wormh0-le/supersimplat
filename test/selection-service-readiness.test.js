const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
    ReadinessGatedSelectionServiceAdapter,
    SelectionServiceReadiness,
    SelectionServiceTransportError
} = require('../.test-dist/src/selection-service-readiness.js');
const {
    aiSelectImageInstancePromptSynthesisPolicyDigest,
    aiSelectImageInstancePromptSynthesisPolicyVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    aiSelectLocalKeyViewPlannerVersion,
    aiSelectLocalKeyViewPolicyDigest
} = require('../.test-dist/src/ai-select/local-key-view-plan.js');
const {
    aiSelectTargetGeometryPolicyDigest,
    aiSelectTargetGeometryPolicyVersion
} = require('../.test-dist/src/ai-select/target-geometry-hint.js');
const {
    aiSelectViewAssessmentPolicyDigest,
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');
const {
    defaultLiftReadinessPolicy
} = require('../.test-dist/src/ai-select/lift-readiness.js');
const {
    createPromptAdapterCapabilities
} = require('../.test-dist/src/ai-select/prompt-state.js');

const editorOrigin = 'https://editor.example';
const activeModelDigest = 'sha256:model-v1';
const checkpointDigest = `sha256:${'4'.repeat(64)}`;
const runtimeConfigDigest = `sha256:${'5'.repeat(64)}`;
const runtimeBuildId =
    'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4';
const evidencePolicyDigest =
    'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd';
const aggregationPolicyDigest =
    'sha256:082dd2a030a21448c16571ce28f741fa50023a831990cae3dd3e7bcc16c02454';

const canonicalJson = (value) => {
    if (value === null || typeof value !== 'object') {
        return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
        return `[${value.map(canonicalJson).join(',')}]`;
    }
    return `{${Object.keys(value)
        .sort()
        .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
        .join(',')}}`;
};

const productionIdentity = () => {
    const payload = {
        schemaVersion: 1,
        renderer: {
            rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
            rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
            runtimeBuildId
        },
        model: {
            adapterId: 'sam3-image-instance/v1',
            manifestId: activeModelDigest,
            manifestRecordDigest: `sha256:${createHash('sha256')
                .update(
                    canonicalJson({
                        adapterId: 'sam3-image-instance/v1',
                        digest: activeModelDigest,
                        modelName: 'SAM 3 Image Instance',
                        checkpointDigest,
                        sourceCommit: 'sam3-source-commit',
                        runtimeConfigDigest,
                        weightsBundled: false
                    })
                )
                .digest('hex')}`,
            checkpointDigest,
            runtimeConfigDigest
        },
        prompt: {
            compilerPolicyVersion: 'sam3-image-instance-compiler/v1',
            adapterCapabilityDigest: promptCapabilityDigest(),
            synthesisPolicyVersion:
                aiSelectImageInstancePromptSynthesisPolicyVersion,
            synthesisPolicyDigest:
                aiSelectImageInstancePromptSynthesisPolicyDigest
        },
        geometry: {
            targetGeometryPolicyVersion: aiSelectTargetGeometryPolicyVersion,
            targetGeometryPolicyDigest: aiSelectTargetGeometryPolicyDigest,
            localViewPolicyVersion: aiSelectLocalKeyViewPlannerVersion,
            localViewPolicyDigest: aiSelectLocalKeyViewPolicyDigest
        },
        maskReview: {
            policyVersion: aiSelectViewAssessmentPolicyVersion,
            policyDigest: aiSelectViewAssessmentPolicyDigest
        },
        evidence: {
            policyDigest: evidencePolicyDigest,
            aggregationPolicyDigest,
            rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'global-atomic/direct-v1',
            runtimeBuildId
        },
        liftReadiness: {
            policyId: defaultLiftReadinessPolicy().policyId,
            policyDigest: defaultLiftReadinessPolicy().readinessPolicyDigest
        }
    };
    return {
        status: 'ready',
        record: {
            ...payload,
            identityDigest: `sha256:${createHash('sha256')
                .update(canonicalJson(payload))
                .digest('hex')}`
        }
    };
};

const configuration = (overrides = {}) => ({
    endpoint: 'http://127.0.0.1:8787',
    profile: 'loopback',
    editorOrigin,
    modelManifestDigest: null,
    ...overrides
});

const health = (companionInstanceId = 'companion-instance-1') => ({
    status: 'ok',
    serviceBuild: 'selection-service-companion/0.1.0+test',
    companionInstanceId
});

const promptCapabilities = (overrides = {}) => ({
    positivePoints: true,
    negativePoints: true,
    positiveInstanceBox: true,
    previousLogitsRefinement: true,
    singlePointMultimask: false,
    ...overrides
});
const promptCapabilityDigest = () =>
    createPromptAdapterCapabilities({
        ...promptCapabilities(),
        compilerPolicyVersion: 'sam3-image-instance-compiler/v1'
    }).capabilityDigest;

const capabilities = (overrides = {}) => ({
    protocolVersion: '2',
    serviceBuild: 'selection-service-companion/0.1.0+test',
    companionInstanceId: 'companion-instance-1',
    runtimeProfileId: 'ai-select-static-image-instance/v1',
    renderer: {
        id: 'gsplat',
        status: 'ready',
        cudaVersion: '12.8',
        rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
        rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
        runtimeBuildId: runtimeBuildId
    },
    imageInstanceProvider: {
        status: 'ready',
        adapterId: 'sam3-image-instance/v1',
        authoritativeRgb: {
            artifact: true,
            companionReference: true
        },
        promptCapabilities: promptCapabilities(),
        compilerPolicyVersion: 'sam3-image-instance-compiler/v1',
        adapterCapabilityDigest: promptCapabilityDigest()
    },
    directEvidence: {
        status: 'ready',
        rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
        evidenceBackendKind: 'production-direct',
        evidenceBackendId: 'global-atomic/direct-v1',
        sourceRevision:
            'sha256:d5568856951be511573c6c766d225f8b95c3ac5850eb965805c2aa632c01976a',
        expectedSourceRevision:
            'sha256:d5568856951be511573c6c766d225f8b95c3ac5850eb965805c2aa632c01976a',
        abiVersion: 'supersimplat-direct-evidence-abi/v1',
        runtimeBuildId: runtimeBuildId,
        torchVersion: '2.11.0+cu128',
        cudaVersion: '12.8',
        gsplatSourceCommit: '77ab983ffe43420b2131669cb35776b883ca4c3c',
        supportedComputeCapabilities: ['8.9'],
        accumulation: 'global-atomic-baseline',
        buildFlags: [
            '-O3',
            '--use_fast_math',
            '--generate-line-info',
            '--ptxas-options=-v'
        ]
    },
    productionCandidateReLift: {
        status: 'ready',
        evidencePolicyDigest,
        aggregationPolicyDigest,
        rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
        evidenceBackendKind: 'production-direct',
        evidenceBackendId: 'global-atomic/direct-v1',
        runtimeBuildId
    },
    productionIdentity: productionIdentity(),
    supportedOperations: [
        'aiSelectAnchorRender',
        'aiSelectProductionCandidateReLift',
        'aiSelectProductionDirectEvidence',
        'aiSelectMaskProposals',
        'autoMaskProposalSetSchemaV3',
        'binarySceneSnapshotRegistrationV1'
    ],
    activeModelManifest: {
        digest: activeModelDigest,
        adapterId: 'sam3-image-instance/v1',
        modelName: 'SAM 3 Image Instance',
        checkpointDigest,
        sourceCommit: 'sam3-source-commit',
        runtimeConfigDigest,
        weightsBundled: false,
        initialized: true
    },
    allowedEditorOrigins: [editorOrigin],
    ...overrides
});

class DeterministicReadinessProbe {
    constructor(options = {}) {
        this.healthResult = options.healthResult ?? health();
        this.capabilitiesResult = options.capabilitiesResult ?? capabilities();
        this.healthError = options.healthError;
        this.capabilitiesError = options.capabilitiesError;
        this.healthRequests = [];
        this.capabilitiesRequests = [];
    }

    async checkHealth(request) {
        this.healthRequests.push(request);
        if (this.healthError) {
            throw this.healthError;
        }
        return typeof this.healthResult === 'function'
            ? this.healthResult()
            : this.healthResult;
    }

    async getCapabilities(request) {
        this.capabilitiesRequests.push(request);
        if (this.capabilitiesError) {
            throw this.capabilitiesError;
        }
        return typeof this.capabilitiesResult === 'function'
            ? this.capabilitiesResult()
            : this.capabilitiesResult;
    }
}

class FakeClock {
    constructor() {
        this.nextId = 1;
        this.tasks = new Map();
        this.delays = [];
    }

    setTimeout(callback, delayMs) {
        const id = this.nextId++;
        this.tasks.set(id, callback);
        this.delays.push(delayMs);
        return id;
    }

    clearTimeout(id) {
        this.tasks.delete(id);
    }

    async runNext() {
        const entry = this.tasks.entries().next().value;
        assert.ok(entry, 'expected a scheduled readiness check');
        const [id, callback] = entry;
        this.tasks.delete(id);
        callback();
        await new Promise((resolve) => setImmediate(resolve));
        await new Promise((resolve) => setImmediate(resolve));
    }
}

class RecordingAISelectAdapter {
    constructor() {
        this.anchorRequests = [];
        this.error = null;
    }

    async renderAnchor(request) {
        this.anchorRequests.push(request);
        if (this.error) {
            throw this.error;
        }
        return {};
    }
}

test('starts automatic readiness as a single flight and binds the Companion Active Model Manifest', async () => {
    let resolveHealth;
    const healthPromise = new Promise((resolve) => {
        resolveHealth = resolve;
    });
    const probe = new DeterministicReadinessProbe({
        healthResult: () => healthPromise
    });
    const readiness = new SelectionServiceReadiness({
        probe,
        configuration: configuration(),
        logTransition: () => {}
    });

    readiness.start();
    readiness.start();
    const refresh = readiness.refresh();
    assert.equal(readiness.state.status, 'connecting');
    assert.equal(probe.healthRequests.length, 1);

    resolveHealth(health());
    await refresh;

    assert.equal(readiness.state.status, 'available');
    assert.equal(probe.capabilitiesRequests.length, 1);
    assert.equal(
        readiness.state.configuration.modelManifestDigest,
        activeModelDigest
    );
    // The adapter capability identity must survive the stored copy: the
    // Prompt capability derivation trusts the advertised record only when
    // the recomputed digest matches these fields.
    const provider = readiness.state.capabilities.imageInstanceProvider;
    assert.equal(
        provider.compilerPolicyVersion,
        'sam3-image-instance-compiler/v1'
    );
    assert.equal(provider.adapterCapabilityDigest, promptCapabilityDigest());
    readiness.stop();
});

test('uses lightweight heartbeats while Available and full validation after connection recovery', async () => {
    const clock = new FakeClock();
    const probe = new DeterministicReadinessProbe();
    const readiness = new SelectionServiceReadiness({
        probe,
        configuration: configuration(),
        clock,
        heartbeatIntervalMs: 50,
        retryInitialMs: 10,
        retryMaximumMs: 40,
        logTransition: () => {}
    });

    readiness.start();
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(readiness.state.status, 'available');
    assert.equal(probe.capabilitiesRequests.length, 1);

    await clock.runNext();
    assert.equal(probe.healthRequests.length, 2);
    assert.equal(
        probe.capabilitiesRequests.length,
        1,
        'an Available heartbeat must not repeat model/runtime validation'
    );

    probe.healthError = new SelectionServiceTransportError('browserTransport');
    await clock.runNext();
    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(clock.delays.at(-1), 10);

    probe.healthError = null;
    await clock.runNext();
    assert.equal(readiness.state.status, 'available');
    assert.equal(
        probe.capabilitiesRequests.length,
        2,
        'connection recovery must run full compatibility validation'
    );
    readiness.stop();
});

test('caps automatic retry backoff and pauses probes outside the foreground', async () => {
    const clock = new FakeClock();
    let foreground = true;
    const probe = new DeterministicReadinessProbe({
        healthError: new SelectionServiceTransportError('browserTransport')
    });
    const readiness = new SelectionServiceReadiness({
        probe,
        configuration: configuration(),
        clock,
        retryInitialMs: 10,
        retryMaximumMs: 20,
        isForeground: () => foreground,
        logTransition: () => {}
    });

    readiness.start();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(clock.delays.at(-1), 10);
    await clock.runNext();
    assert.equal(clock.delays.at(-1), 20);
    await clock.runNext();
    assert.equal(clock.delays.at(-1), 20);

    foreground = false;
    const requestsBeforeHiddenTick = probe.healthRequests.length;
    await clock.runNext();
    assert.equal(probe.healthRequests.length, requestsBeforeHiddenTick);
    assert.equal(clock.delays.at(-1), 20);
    readiness.stop();
});

test('runs full validation and invalidates Companion-local references after Instance replacement', async () => {
    const clock = new FakeClock();
    let instanceId = 'companion-instance-1';
    const invalidations = [];
    const probe = new DeterministicReadinessProbe({
        healthResult: () => health(instanceId),
        capabilitiesResult: () =>
            capabilities({ companionInstanceId: instanceId })
    });
    const readiness = new SelectionServiceReadiness({
        probe,
        configuration: configuration(),
        clock,
        heartbeatIntervalMs: 10,
        onCompanionInstanceChanged: (previous, current) => {
            invalidations.push([previous, current]);
        },
        logTransition: () => {}
    });

    readiness.start();
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
    instanceId = 'companion-instance-2';
    await clock.runNext();

    assert.deepEqual(invalidations, [
        ['companion-instance-1', 'companion-instance-2']
    ]);
    assert.equal(probe.capabilitiesRequests.length, 2);
    assert.equal(readiness.state.status, 'available');
    assert.equal(
        readiness.state.health.companionInstanceId,
        'companion-instance-2'
    );
    readiness.stop();
});

test('accepts only the current SAM 3 Image instance Runtime Profile', async () => {
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe(),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'available');
    assert.equal(readiness.state.diagnostic.code, 'available');
});

test('rejects a Candidate Re-Lift policy, backend, or runtime identity mismatch', async () => {
    const current = capabilities().productionCandidateReLift;
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                productionCandidateReLift: {
                    ...current,
                    runtimeBuildId: `sha256:${'0'.repeat(64)}`
                }
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(readiness.state.diagnostic.code, 'candidateReLiftUnsupported');
});

test('rejects a correctly checksummed production identity with an extra field', async () => {
    const identity = productionIdentity();
    identity.record.unexpected = true;
    const payload = Object.fromEntries(
        Object.entries(identity.record).filter(
            ([key]) => key !== 'identityDigest'
        )
    );
    identity.record.identityDigest = `sha256:${createHash('sha256')
        .update(canonicalJson(payload))
        .digest('hex')}`;
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                productionIdentity: identity
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(readiness.state.diagnostic.code, 'invalidCapabilities');
});

test('rejects a checksummed production identity with a foreign Evidence raster', async () => {
    const identity = productionIdentity();
    identity.record.evidence.rasterImplementationId = 'foreign-raster/v1';
    const payload = Object.fromEntries(
        Object.entries(identity.record).filter(
            ([key]) => key !== 'identityDigest'
        )
    );
    identity.record.identityDigest = `sha256:${createHash('sha256')
        .update(canonicalJson(payload))
        .digest('hex')}`;
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                productionIdentity: identity
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(readiness.state.diagnostic.code, 'candidateReLiftUnsupported');
});

test('rejects the historical Multiplex static manifest', async () => {
    const multiplexManifest = {
        ...capabilities().activeModelManifest,
        adapterId: 'sam3.1',
        modelName: 'SAM 3.1 Multiplex'
    };
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                activeModelManifest: multiplexManifest,
                imageInstanceProvider: {
                    ...capabilities().imageInstanceProvider,
                    status: 'unavailable',
                    adapterId: 'sam3.1'
                }
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(readiness.state.diagnostic.code, 'modelAdapterMismatch');
});

test('rejects authoritative RGB, opaque refinement, and removed Prompt capability mismatches', async (t) => {
    const cases = [
        [
            'authoritative RGB',
            {
                authoritativeRgb: {
                    artifact: false,
                    companionReference: false
                }
            },
            'rgbResolutionUnsupported'
        ],
        [
            'opaque refinement reference',
            {
                promptCapabilities: promptCapabilities({
                    previousLogitsRefinement: false
                })
            },
            'imageInstanceCapabilityMismatch'
        ],
        [
            'removed Prompt family',
            {
                promptCapabilities: promptCapabilities({
                    promptBrush: true
                })
            },
            'invalidCapabilities'
        ],
        [
            'single-point multimask',
            {
                promptCapabilities: promptCapabilities({
                    singlePointMultimask: true
                })
            },
            'imageInstanceCapabilityMismatch'
        ],
        [
            'missing compiler policy version',
            { compilerPolicyVersion: undefined },
            'imageInstanceCapabilityMismatch'
        ],
        [
            'missing adapter capability digest',
            { adapterCapabilityDigest: undefined },
            'imageInstanceCapabilityMismatch'
        ],
        [
            'malformed adapter capability digest',
            { adapterCapabilityDigest: 'not-a-digest' },
            'invalidCapabilities'
        ]
    ];

    for (const [name, providerOverride, code] of cases) {
        await t.test(name, async () => {
            const provider = {
                ...capabilities().imageInstanceProvider,
                ...providerOverride
            };
            const readiness = new SelectionServiceReadiness({
                probe: new DeterministicReadinessProbe({
                    capabilitiesResult: capabilities({
                        imageInstanceProvider: provider
                    })
                }),
                configuration: configuration(),
                logTransition: () => {}
            });

            await readiness.refresh();

            assert.equal(readiness.state.status, 'unavailable');
            assert.equal(readiness.state.diagnostic.code, code);
        });
    }
});

test('does not use Companion capacity or task-local failures as Availability', async () => {
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                capacity: {
                    maximumActiveSessions: 1,
                    activeSessions: 1
                }
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });
    const adapter = new RecordingAISelectAdapter();
    adapter.error = new Error('task-local model OOM');
    const gatedAdapter = new ReadinessGatedSelectionServiceAdapter({
        readiness,
        adapter
    });

    await readiness.refresh();
    assert.equal(readiness.state.status, 'available');
    await assert.rejects(gatedAdapter.renderAnchor({}), /task-local model OOM/);
    assert.equal(readiness.state.status, 'available');
});

test('same-Instance recovery is identity-bound and fails closed on replacement or stale input', async () => {
    let instanceId = 'companion-instance-1';
    let bindingCurrent = true;
    const invalidations = [];
    const probe = new DeterministicReadinessProbe({
        healthResult: () => health(instanceId),
        capabilitiesResult: () =>
            capabilities({ companionInstanceId: instanceId })
    });
    const readiness = new SelectionServiceReadiness({
        probe,
        configuration: configuration(),
        onCompanionInstanceChanged: (previous, current) => {
            invalidations.push([previous, current]);
        },
        logTransition: () => {}
    });

    await readiness.refresh();
    assert.equal(
        await readiness.recoverSameInstance(
            'companion-instance-1',
            () => bindingCurrent
        ),
        true
    );

    bindingCurrent = false;
    assert.equal(
        await readiness.recoverSameInstance(
            'companion-instance-1',
            () => bindingCurrent
        ),
        false
    );

    bindingCurrent = true;
    instanceId = 'companion-instance-2';
    assert.equal(
        await readiness.recoverSameInstance(
            'companion-instance-1',
            () => bindingCurrent
        ),
        false
    );
    assert.equal(readiness.state.status, 'unavailable');
    assert.deepEqual(invalidations, [
        ['companion-instance-1', 'companion-instance-2']
    ]);
});

test('rejects stale full-validation results whose Instance differs from health', async () => {
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            healthResult: health('companion-instance-1'),
            capabilitiesResult: capabilities({
                companionInstanceId: 'companion-instance-2'
            })
        }),
        configuration: configuration(),
        logTransition: () => {}
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    assert.equal(readiness.state.diagnostic.code, 'companionInstanceMismatch');
});

test('gates AI work while unavailable without blocking native editor state', async () => {
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            healthError: new SelectionServiceTransportError('browserTransport')
        }),
        configuration: configuration(),
        logTransition: () => {}
    });
    const nativeSelection = new Set([7, 9]);
    const gatedAdapter = new ReadinessGatedSelectionServiceAdapter({
        readiness,
        adapter: new RecordingAISelectAdapter()
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    await assert.rejects(gatedAdapter.renderAnchor({}), /cannot start/i);
    assert.deepEqual([...nativeSelection], [7, 9]);
});

test('ordinary Availability UI is accessible and contains no technical/model controls', () => {
    const statusBarSource = fs.readFileSync(
        path.join(__dirname, '..', 'src', 'ui', 'status-bar.ts'),
        'utf8'
    );
    const dockSource = fs.readFileSync(
        path.join(__dirname, '..', 'src', 'ui', 'ai-select-anchor-dock.ts'),
        'utf8'
    );

    // The three-state projection stays in the Status Bar. The header-free
    // Dock consumes availability only as contextual action gating.
    assert.match(statusBarSource, /status-bar-availability-dot/);
    assert.match(statusBarSource, /ai-select\.availability\./);
    assert.doesNotMatch(dockSource, /ai-select-anchor-dock-availability/);
    assert.match(dockSource, /serviceAvailable:/);
    assert.match(dockSource, /reLiftDescription/);
    assert.match(dockSource, /aria-live/);
    const locales = JSON.parse(
        fs.readFileSync(
            path.join(__dirname, '..', 'static', 'locales', 'en.json'),
            'utf8'
        )
    );
    assert.ok(locales['ai-select.availability.connecting']);
    assert.ok(locales['ai-select.availability.available']);
    assert.ok(locales['ai-select.availability.unavailable']);
    for (const forbidden of [
        'TextInput',
        'SelectInput',
        'Endpoint',
        'Model Manifest',
        'CUDA',
        'Check readiness',
        'Ping'
    ]) {
        assert.doesNotMatch(statusBarSource, new RegExp(forbidden, 'i'));
        assert.doesNotMatch(dockSource, new RegExp(forbidden, 'i'));
    }
});
