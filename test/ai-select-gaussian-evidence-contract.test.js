const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const {
    admitGaussianEvidence,
    createEvidenceWorkingSet,
    createGaussianEvidenceArtifact,
    expandEvidenceWorkingSet,
    gaussianEvidenceArtifactMatchesAdmission,
    isCurrentGaussianEvidenceArtifact,
    isGaussianEvidenceArtifact,
    rebindGaussianEvidenceArtifactForExactRestoration,
    resolveEvidenceWorkingSetBoundary
} = require('../.test-dist/src/ai-select/gaussian-evidence-contract.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;
const contractVectors = JSON.parse(
    readFileSync(
        'test/fixtures/ai-select-gaussian-evidence-contract-vectors.json',
        'utf8'
    )
);

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const requestBinding = (overrides = {}) => ({
    targetContextId: 'ai-target-context-1',
    contextRevision: 3,
    dependencyToken: dependency(),
    ...overrides
});

const view = (overrides = {}) => ({
    viewId: 'view-1',
    renderStatus: 'ready',
    participation: 'included',
    cameraBindingDigest: digest('a'),
    rgbDigest: digest('b'),
    stableMaskDigest: digest('c'),
    ...overrides
});

const renderWorkingSet = (overrides = {}) => ({
    targetSplatId: 'editor-splat:1',
    dependencyToken: dependency(),
    cameraBindingDigest: digest('a'),
    renderWorkingSetToken: digest('d'),
    stableGaussianIds: [5, 9, 42],
    completeness: 'complete',
    ...overrides
});

const evidenceWorkingSet = (overrides = {}) =>
    createEvidenceWorkingSet({
        targetSplatId: 'editor-splat:1',
        coreTargetStableIds: [5],
        contextStableGaussianIds: [9],
        ...overrides
    });

const input = (overrides = {}) => ({
    requestBinding: requestBinding(),
    targetSplatId: 'editor-splat:1',
    view: view(),
    evidencePolicyDigest: digest('e'),
    renderWorkingSet: renderWorkingSet(),
    evidenceWorkingSet: evidenceWorkingSet(),
    rasterImplementationId: 'gsplat-reference-rgb/v1',
    evidenceBackendKind: 'reference-contributor',
    evidenceBackendId: 'complete-contributor/reference-v1',
    runtimeBuildId: 'locked-runtime-build-1',
    ...overrides
});

const admitted = (value = input()) => {
    const result = admitGaussianEvidence(value);
    assert.equal(result.status, 'admitted');
    return result.admission;
};

const masses = (overrides = {}) => ({
    positiveMass: [0.5, 0],
    negativeMass: [0, 0.25],
    visibleMass: [0.5, 0.25],
    ...overrides
});

test('formal Evidence admits only an Included Stable RGB Ready View', () => {
    const admission = admitted();

    assert.deepEqual(admission.stableGaussianIds, [5, 9]);
    assert.equal(admission.viewId, 'view-1');
    assert.equal(admission.rgbDigest, digest('b'));
    assert.equal(admission.stableMaskDigest, digest('c'));
});

test('shared browser and Companion vector has matching Working-Set and artifact digests', () => {
    const vectorInput = {
        ...contractVectors.admissionInput,
        evidenceWorkingSet: contractVectors.evidenceWorkingSet
    };
    const vectorAdmission = admitGaussianEvidence(vectorInput);

    assert.equal(vectorAdmission.status, 'admitted');
    assert.deepEqual(vectorAdmission.admission.stableGaussianIds, [2, 5, 9]);
    assert.equal(
        vectorAdmission.admission.evidenceWorkingSetToken,
        contractVectors.evidenceWorkingSet.evidenceWorkingSetToken
    );
    const artifact = createGaussianEvidenceArtifact(vectorAdmission.admission, {
        positiveMass: contractVectors.artifact.positiveMass,
        negativeMass: contractVectors.artifact.negativeMass,
        visibleMass: contractVectors.artifact.visibleMass,
        boundaryMass: contractVectors.artifact.boundaryMass
    });
    assert.deepEqual(artifact, contractVectors.artifact);
});

test('excluded and no-Stable-Mask Views fail closed before Evidence computation', () => {
    const excluded = admitGaussianEvidence(
        input({ view: view({ participation: 'excluded' }) })
    );
    assert.deepEqual(excluded, {
        status: 'rejected',
        reason: 'view-excluded'
    });

    const noStableMask = admitGaussianEvidence(
        input({ view: view({ stableMaskDigest: undefined }) })
    );
    assert.deepEqual(noStableMask, {
        status: 'rejected',
        reason: 'stable-mask-unavailable'
    });
});

test('admission rejects partial Render Working Sets and invalid Stable ID mappings', () => {
    const partial = admitGaussianEvidence(
        input({
            renderWorkingSet: renderWorkingSet({ completeness: 'partial' })
        })
    );
    assert.deepEqual(partial, {
        status: 'rejected',
        reason: 'render-working-set-incomplete'
    });

    const invalidMapping = admitGaussianEvidence(
        input({
            evidenceWorkingSet: evidenceWorkingSet({
                contextStableGaussianIds: [99]
            })
        })
    );
    assert.deepEqual(invalidMapping, {
        status: 'rejected',
        reason: 'stable-id-mapping-invalid'
    });

    const spatialDirect = admitGaussianEvidence(
        input({
            evidenceWorkingSet: evidenceWorkingSet({
                contextStableGaussianIds: [99]
            }),
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'global-atomic/direct-v1'
        })
    );
    assert.equal(spatialDirect.status, 'admitted');
    assert.deepEqual(spatialDirect.admission.stableGaussianIds, [5, 99]);
});

test('Evidence Working Set writes exclude a Render Working Set occluder', () => {
    const admission = admitted();
    const artifact = createGaussianEvidenceArtifact(admission, masses());

    assert.deepEqual(artifact.stableGaussianIds, [5, 9]);
    assert.ok(!artifact.stableGaussianIds.includes(42));
    assert.equal(artifact.renderWorkingSetToken, digest('d'));
    assert.ok(isGaussianEvidenceArtifact(artifact));
    assert.ok(gaussianEvidenceArtifactMatchesAdmission(artifact, admission));
    assert.equal('viewSource' in artifact, false);
    assert.equal('promptArtifactDigest' in artifact, false);
    assert.equal('maskReviewReasons' in artifact, false);
});

test('exact restoration rebinds retained Evidence to the fresh lifecycle revision only', () => {
    const artifact = createGaussianEvidenceArtifact(admitted(), masses());
    const restoredBinding = requestBinding({ contextRevision: 5 });
    const restoredInput = input({ requestBinding: restoredBinding });

    assert.equal(
        isCurrentGaussianEvidenceArtifact(artifact, restoredInput),
        false
    );
    const rebound = rebindGaussianEvidenceArtifactForExactRestoration(
        artifact,
        restoredBinding
    );

    assert.equal(
        isCurrentGaussianEvidenceArtifact(rebound, restoredInput),
        true
    );
    assert.notEqual(rebound.artifactDigest, artifact.artifactDigest);
    assert.deepEqual(rebound.positiveMass, artifact.positiveMass);
    assert.deepEqual(rebound.negativeMass, artifact.negativeMass);
    assert.deepEqual(rebound.visibleMass, artifact.visibleMass);
    assert.throws(
        () =>
            rebindGaussianEvidenceArtifactForExactRestoration(
                artifact,
                requestBinding({
                    contextRevision: 5,
                    dependencyToken: dependency({
                        geometryToken: 'geometry-v2'
                    })
                })
            ),
        /cannot rebind Evidence across/
    );
});

test('a TargetGeometryHint seed can expand through a later Included Stable View', () => {
    const seeded = evidenceWorkingSet({
        targetGeometryHintSeedDigest: digest('f')
    });
    const expanded = expandEvidenceWorkingSet(seeded, {
        sourceView: {
            viewId: 'later-view',
            renderStatus: 'ready',
            participation: 'included',
            stableMaskDigest: digest('1')
        },
        coreTargetStableIds: [42],
        contextStableGaussianIds: []
    });

    assert.equal(seeded.targetGeometryHintSeedDigest, digest('f'));
    assert.deepEqual(expanded.stableGaussianIds, [5, 9, 42]);
    assert.notEqual(
        expanded.evidenceWorkingSetToken,
        seeded.evidenceWorkingSetToken
    );
    assert.throws(
        () =>
            expandEvidenceWorkingSet(seeded, {
                sourceView: {
                    viewId: 'excluded-view',
                    renderStatus: 'ready',
                    participation: 'excluded',
                    stableMaskDigest: digest('2')
                },
                coreTargetStableIds: [42],
                contextStableGaussianIds: []
            }),
        /Included Stable View/
    );
});

test('Working Set boundary contact either expands explicitly or fails closed', () => {
    const current = evidenceWorkingSet();
    const failed = resolveEvidenceWorkingSetBoundary({
        renderWorkingSet: renderWorkingSet(),
        evidenceWorkingSet: current,
        boundaryStableGaussianIds: [42],
        resolution: 'fail-closed'
    });
    assert.deepEqual(failed, {
        status: 'failed-closed',
        reason: 'evidence-working-set-boundary-contact',
        contactStableGaussianIds: [42]
    });

    const expanded = resolveEvidenceWorkingSetBoundary({
        renderWorkingSet: renderWorkingSet(),
        evidenceWorkingSet: current,
        boundaryStableGaussianIds: [42],
        resolution: 'expand',
        expansion: {
            sourceView: {
                viewId: 'later-view',
                renderStatus: 'ready',
                participation: 'included',
                stableMaskDigest: digest('1')
            },
            coreTargetStableIds: [42],
            contextStableGaussianIds: []
        }
    });
    assert.equal(expanded.status, 'expanded');
    assert.deepEqual(expanded.contactStableGaussianIds, [42]);
    assert.deepEqual(expanded.evidenceWorkingSet.stableGaussianIds, [5, 9, 42]);
});

test('a formal artifact invalidates on every material identity change', () => {
    const originalInput = input();
    const artifact = createGaussianEvidenceArtifact(
        admitted(originalInput),
        masses()
    );
    assert.ok(isCurrentGaussianEvidenceArtifact(artifact, originalInput));

    const changedInputs = [
        input({
            requestBinding: requestBinding({ contextRevision: 4 })
        }),
        input({ view: view({ cameraBindingDigest: digest('2') }) }),
        input({ view: view({ rgbDigest: digest('3') }) }),
        input({ view: view({ stableMaskDigest: digest('4') }) }),
        input({ evidencePolicyDigest: digest('5') }),
        input({
            renderWorkingSet: renderWorkingSet({
                renderWorkingSetToken: digest('6')
            })
        }),
        input({
            evidenceWorkingSet: evidenceWorkingSet({
                contextStableGaussianIds: [9, 42]
            })
        }),
        input({ rasterImplementationId: 'other-raster/v1' }),
        input({ evidenceBackendId: 'other-reference/v1' }),
        input({ runtimeBuildId: 'locked-runtime-build-2' })
    ];

    for (const changed of changedInputs) {
        assert.ok(!isCurrentGaussianEvidenceArtifact(artifact, changed));
    }
});

test('reference and production Direct Evidence artifacts are admitted but cannot collide', () => {
    const referenceAdmission = admitted();
    const productionAdmission = admitted(
        input({
            rasterImplementationId: 'supersimplat-direct-evidence/v1',
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'global-atomic/direct-v1',
            runtimeBuildId: 'direct-runtime-build-1'
        })
    );
    const referenceArtifact = createGaussianEvidenceArtifact(
        referenceAdmission,
        masses()
    );
    const productionArtifact = createGaussianEvidenceArtifact(
        productionAdmission,
        masses()
    );

    assert.ok(isGaussianEvidenceArtifact(referenceArtifact));
    assert.ok(isGaussianEvidenceArtifact(productionArtifact));
    assert.notEqual(
        referenceArtifact.artifactDigest,
        productionArtifact.artifactDigest
    );
    assert.equal(
        gaussianEvidenceArtifactMatchesAdmission(
            referenceArtifact,
            productionAdmission
        ),
        false
    );
});

test('artifact validation rejects incomplete, non-finite, and tampered P/N/V arrays', () => {
    const artifact = createGaussianEvidenceArtifact(admitted(), masses());
    assert.throws(
        () =>
            createGaussianEvidenceArtifact(admitted(), {
                positiveMass: [0.5, 0],
                negativeMass: [0, 0.25]
            }),
        /complete finite non-negative P\/N\/V arrays/
    );
    assert.throws(
        () =>
            createGaussianEvidenceArtifact(
                admitted(),
                masses({ positiveMass: [Number.POSITIVE_INFINITY, 0] })
            ),
        /complete finite non-negative P\/N\/V arrays/
    );
    assert.ok(
        !isGaussianEvidenceArtifact({
            ...artifact,
            visibleMass: [0.5]
        })
    );
    assert.ok(
        !isGaussianEvidenceArtifact({
            ...artifact,
            positiveMass: [Number.NaN, 0]
        })
    );
    assert.ok(
        !isGaussianEvidenceArtifact({
            ...artifact,
            artifactDigest: digest('z')
        })
    );
});
