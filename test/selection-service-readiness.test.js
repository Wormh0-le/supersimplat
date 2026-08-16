const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
    ReadinessGatedSelectionServiceAdapter,
    SelectionServiceReadiness,
    SelectionServiceTransportError
} = require('../.test-dist/src/selection-service-readiness.js');

const editorOrigin = 'https://editor.example';
const activeModelDigest = 'sha256:model-v1';

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
    negativeBox: false,
    promptBrush: false,
    maskConstraints: false,
    text: false,
    ...overrides
});

const capabilities = (overrides = {}) => ({
    protocolVersion: '2',
    serviceBuild: 'selection-service-companion/0.1.0+test',
    companionInstanceId: 'companion-instance-1',
    runtimeProfileId: 'ai-select-static-image-instance/v1',
    renderer: {
        id: 'gsplat',
        status: 'ready',
        cudaVersion: '12.8',
        rgbRendererVersion: 'gsplat-rgb/v1'
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
        adapterCapabilityDigest: `sha256:${'c'.repeat(64)}`
    },
    referenceCandidateReLift: {
        evidencePolicyDigest:
            'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd',
        aggregationPolicyDigest:
            'sha256:082dd2a030a21448c16571ce28f741fa50023a831990cae3dd3e7bcc16c02454',
        rasterImplementationId: 'gsplat-reference-rgb/v1',
        evidenceBackendKind: 'reference-contributor',
        evidenceBackendId: 'complete-contributor/reference-v1',
        runtimeBuildId:
            'sha256:a04a3840702bca8d86365dc44c8a693344e54fb09db8a2c2131a4ed711717e40'
    },
    supportedOperations: [
        'aiSelectAnchorRender',
        'aiSelectReferenceCandidateReLift',
        'aiSelectMaskProposals',
        'autoMaskProposalSetSchemaV3',
        'binarySceneSnapshotRegistrationV1'
    ],
    activeModelManifest: {
        digest: activeModelDigest,
        adapterId: 'sam3-image-instance/v1',
        modelName: 'SAM 3 Image Instance',
        checkpointDigest: 'sha256:checkpoint',
        sourceCommit: 'sam3-source-commit',
        runtimeConfigDigest: 'sha256:runtime',
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

class RecordingSelectionServiceAdapter {
    constructor() {
        this.openRequests = [];
        this.error = null;
    }

    async openSession(start) {
        this.openRequests.push(start);
        if (this.error) {
            throw this.error;
        }
        return 'selection-session';
    }

    async updatePreview() {
        throw new Error('not used by readiness tests');
    }

    async cancelUpdate() {
        throw new Error('not used by readiness tests');
    }

    async closeSession() {
        throw new Error('not used by readiness tests');
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
    assert.equal(provider.adapterCapabilityDigest, `sha256:${'c'.repeat(64)}`);
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
    const current = capabilities().referenceCandidateReLift;
    const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({
            capabilitiesResult: capabilities({
                referenceCandidateReLift: {
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
            'imageInstanceCapabilityMismatch'
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
    const adapter = new RecordingSelectionServiceAdapter();
    adapter.error = new Error('task-local model OOM');
    const gatedAdapter = new ReadinessGatedSelectionServiceAdapter({
        readiness,
        adapter
    });

    await readiness.refresh();
    assert.equal(readiness.state.status, 'available');
    await assert.rejects(
        gatedAdapter.openSession({ target: {}, prompt: {} }),
        /task-local model OOM/
    );
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
        adapter: new RecordingSelectionServiceAdapter()
    });

    await readiness.refresh();

    assert.equal(readiness.state.status, 'unavailable');
    await assert.rejects(
        gatedAdapter.openSession({ target: {}, prompt: {} }),
        /cannot start/i
    );
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

    // The three-state projection rides on the AI Select toggle and inside
    // the AI Select panel; both are localized, never hardcoded.
    assert.match(statusBarSource, /status-bar-availability-dot/);
    assert.match(statusBarSource, /ai-select\.availability\./);
    assert.match(dockSource, /ai-select-anchor-dock-availability/);
    assert.match(dockSource, /ai-select\.availability\./);
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
