const assert = require('node:assert/strict');
const test = require('node:test');

const {
    areEvidenceIdentitiesEqual,
    deriveEvidenceStatus,
    PerViewEvidenceRegistry
} = require('../.test-dist/src/ai-select/evidence-state.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const identity = (overrides = {}) => ({
    viewId: 'anchor-view',
    rgbDigest: digest('a'),
    stableMaskDigest: digest('b'),
    evidencePolicyDigest: digest('c'),
    ...overrides
});

test('a view with no Evidence record is not-requested', () => {
    const registry = new PerViewEvidenceRegistry();
    const state = registry.statusFor('anchor-view', identity());
    assert.equal(state.status, 'not-requested');
    assert.equal(state.artifactIdentity, undefined);
});

test('a ready artifact stays ready only for the exact current identity', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    assert.equal(registry.statusFor('anchor-view', identity()).status, 'ready');
});

test('publishing a new Stable Mask makes only the dependent Evidence stale', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    registry.markReady(identity({ viewId: 'view-2' }));

    const afterMaskChange = registry.statusFor(
        'anchor-view',
        identity({ stableMaskDigest: digest('d') })
    );
    assert.equal(afterMaskChange.status, 'stale');
    assert.deepEqual(afterMaskChange.artifactIdentity, identity());

    const otherView = registry.statusFor(
        'view-2',
        identity({ viewId: 'view-2' })
    );
    assert.equal(otherView.status, 'ready');
});

test('an identical Mask re-publication keeps matching Evidence ready', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    // Confirming unchanged Mask content republishes the same digest identity.
    assert.equal(registry.statusFor('anchor-view', identity()).status, 'ready');
});

test('an RGB or policy identity change also makes Evidence stale', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    assert.equal(
        registry.statusFor('anchor-view', identity({ rgbDigest: digest('e') }))
            .status,
        'stale'
    );
    assert.equal(
        registry.statusFor(
            'anchor-view',
            identity({ evidencePolicyDigest: digest('f') })
        ).status,
        'stale'
    );
});

test('a pending Evidence attempt becomes stale when its inputs change', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markPending(identity());
    assert.equal(
        registry.statusFor('anchor-view', identity()).status,
        'pending'
    );
    assert.equal(
        registry.statusFor(
            'anchor-view',
            identity({ stableMaskDigest: digest('d') })
        ).status,
        'stale'
    );
});

test('Evidence failure is inspectable and does not disturb other state', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markFailed(identity(), 'P/N/V accumulation failed.');
    const state = registry.statusFor('anchor-view', identity());
    assert.equal(state.status, 'failed');
    assert.equal(state.errorMessage, 'P/N/V accumulation failed.');
    // The failure is bound to its exact inputs; superseded inputs read as
    // never-requested rather than masking the current state.
    assert.equal(
        registry.statusFor(
            'anchor-view',
            identity({ stableMaskDigest: digest('d') })
        ).status,
        'not-requested'
    );
});

test('a new attempt replaces the previous record atomically', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    registry.markFailed(identity(), 'second attempt failed');
    const state = registry.statusFor('anchor-view', identity());
    assert.equal(state.status, 'failed');
    registry.markReady(identity());
    assert.equal(registry.statusFor('anchor-view', identity()).status, 'ready');
});

test('a missing Stable Mask leaves prior Evidence stale, never current', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    assert.equal(registry.statusFor('anchor-view', null).status, 'stale');
    assert.equal(deriveEvidenceStatus(null, null), 'not-requested');
});

test('disposeView drops Evidence records for a restarted view', () => {
    const registry = new PerViewEvidenceRegistry();
    registry.markReady(identity());
    registry.disposeView('anchor-view');
    assert.equal(
        registry.statusFor('anchor-view', identity()).status,
        'not-requested'
    );
});

test('identity equality compares every dependency component', () => {
    assert.ok(areEvidenceIdentitiesEqual(identity(), identity()));
    assert.ok(
        !areEvidenceIdentitiesEqual(identity(), identity({ viewId: 'v' }))
    );
    assert.ok(
        !areEvidenceIdentitiesEqual(
            identity(),
            identity({ rgbDigest: digest('z') })
        )
    );
    assert.ok(
        !areEvidenceIdentitiesEqual(
            identity(),
            identity({ stableMaskDigest: digest('z') })
        )
    );
    assert.ok(
        !areEvidenceIdentitiesEqual(
            identity(),
            identity({ evidencePolicyDigest: digest('z') })
        )
    );
    assert.ok(!areEvidenceIdentitiesEqual(identity(), null));
    assert.ok(areEvidenceIdentitiesEqual(null, null));
});
