const assert = require('node:assert/strict');
const test = require('node:test');

const {
    semanticDeletedMembershipFingerprint,
    semanticGeometryFingerprint,
    semanticValueFingerprint
} = require('../.test-dist/src/ai-select/target-dependency-fingerprint.js');

test('selection and lock flags are excluded from Gaussian membership identity', () => {
    const selected = 1;
    const locked = 2;
    const deleted = 4;
    const baseline = new Uint8Array([0, selected, locked, deleted]);

    const original = semanticDeletedMembershipFingerprint(
        baseline,
        deleted,
        'asset-1'
    );
    const editorOnlyChanged = semanticDeletedMembershipFingerprint(
        new Uint8Array([selected, 0, selected | locked, deleted | selected]),
        deleted,
        'asset-1'
    );
    const membershipChanged = semanticDeletedMembershipFingerprint(
        new Uint8Array([deleted, selected, locked, deleted]),
        deleted,
        'asset-1'
    );

    assert.equal(editorOnlyChanged, original);
    assert.notEqual(membershipChanged, original);
    assert.equal(
        semanticDeletedMembershipFingerprint(baseline, deleted, 'asset-1'),
        original
    );
});

test('effective geometry identity restores exactly after an inverse transform', () => {
    const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0];
    const translated = [1, 0, 0, 3, 0, 1, 0, 2, 0, 0, 1, 1];
    const palette = [identity, translated];
    const transformIndices = new Uint16Array([0, 0, 0]);
    const fingerprint = () =>
        semanticGeometryFingerprint({
            contentIdentity: 'asset-1',
            transformIndices,
            writeTransform: (transformIndex, target) => {
                target.set(palette[transformIndex]);
            }
        });

    const original = fingerprint();
    transformIndices[1] = 1;
    const changed = fingerprint();
    transformIndices[1] = 0;

    assert.notEqual(changed, original);
    assert.equal(fingerprint(), original);
});

test('render and world fingerprints compare semantic values, not edit ordinals', () => {
    const originalRender = semanticValueFingerprint('render', [
        'asset-1',
        1,
        0,
        1,
        1,
        'opaque-background'
    ]);
    const changedRender = semanticValueFingerprint('render', [
        'asset-1',
        0.5,
        0,
        1,
        1,
        'opaque-background'
    ]);

    assert.notEqual(changedRender, originalRender);
    assert.equal(
        semanticValueFingerprint('render', [
            'asset-1',
            1,
            0,
            1,
            1,
            'opaque-background'
        ]),
        originalRender
    );
});
