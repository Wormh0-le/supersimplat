const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createEmptyMaskArtifact,
    applyBrushStroke,
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    MaskAnnotationRegistry
} = require('../.test-dist/src/ai-select/mask-registry.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const rgbDigest = (letter) => `sha256:${letter.repeat(64)}`;

const samArtifact = (width, height, seedByte) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    bytes[0] = seedByte;
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: (() => {
            let binary = '';
            for (const byte of bytes) {
                binary += String.fromCharCode(byte);
            }
            return btoa(binary);
        })(),
        digest: sha256Digest(bytes)
    });
};

const prompts = [{ promptId: 'p-1', xPx: 2, yPx: 2, polarity: 'include' }];

test('a SAM result creates the first Editing Mask and leaves Stable Mask unset', () => {
    const registry = new MaskAnnotationRegistry();
    const editing = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    assert.equal(editing.source, 'single-frame-sam');
    assert.equal(editing.status, 'draft');
    assert.equal(editing.createdFromRgbDigest, rgbDigest('a'));
    assert.deepEqual(editing.prompts, prompts);
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask?.maskId, editing.maskId);
    assert.equal(view.stableMask, null);
});

test('a later SAM result replaces the Editing Mask without touching the Stable Mask', () => {
    const registry = new MaskAnnotationRegistry();
    const first = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.confirm('anchor-view', rgbDigest('a'));
    const replaced = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b111),
        prompts
    });
    assert.equal(replaced.parentMaskId, first.maskId);
    assert.notEqual(replaced.maskId, first.maskId);
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask?.maskId, replaced.maskId);
    assert.equal(view.stableMask?.status, 'user-confirmed');
    assert.notEqual(view.stableMask?.maskId, replaced.maskId);
});

test('a brush stroke with no Editing Mask begins a manual draft bound to the current RGB', () => {
    const registry = new MaskAnnotationRegistry();
    const editing = registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' },
        width: 8,
        height: 8
    });
    assert.equal(editing.source, 'manual');
    assert.equal(editing.status, 'draft');
    assert.equal(editing.createdFromRgbDigest, rgbDigest('a'));
    assert.equal(editing.parentMaskId, undefined);
});

test('a brush stroke on a SAM Editing Mask creates a hybrid draft version', () => {
    const registry = new MaskAnnotationRegistry();
    const sam = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const brushed = registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 4, yPx: 4, radiusPx: 1, mode: 'add' },
        width: 8,
        height: 8
    });
    assert.equal(brushed.source, 'hybrid');
    assert.equal(brushed.parentMaskId, sam.maskId);
    assert.notDeepEqual(brushed.artifact.digest, sam.artifact.digest);
});

test('a brush stroke after an RGB change starts a fresh manual chain', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const brushed = registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('b'),
        stroke: { xPx: 1, yPx: 1, radiusPx: 1, mode: 'add' },
        width: 8,
        height: 8
    });
    assert.equal(brushed.source, 'manual');
    assert.equal(brushed.createdFromRgbDigest, rgbDigest('b'));
    assert.equal(brushed.parentMaskId, undefined);
});

test('Confirm Mask atomically publishes the Editing Mask as a new Stable revision', () => {
    const registry = new MaskAnnotationRegistry();
    const editing = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const stable = registry.confirm('anchor-view', rgbDigest('a'));
    assert.notEqual(stable.maskId, editing.maskId);
    assert.equal(stable.status, 'user-confirmed');
    assert.equal(stable.source, 'single-frame-sam');
    assert.equal(stable.parentMaskId, editing.maskId);
    assert.equal(stable.artifact.digest, editing.artifact.digest);
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.stableMask?.maskId, stable.maskId);
    assert.equal(view.editingMask?.maskId, editing.maskId);
});

test('Confirm Mask retains the previous Stable Mask version for inspection', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const firstStable = registry.confirm('anchor-view', rgbDigest('a'));
    registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 5, yPx: 5, radiusPx: 1, mode: 'add' },
        width: 8,
        height: 8
    });
    const secondStable = registry.confirm('anchor-view', rgbDigest('a'));
    assert.notEqual(secondStable.maskId, firstStable.maskId);
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.stableMask?.maskId, secondStable.maskId);
    assert.ok(registry.version('anchor-view', firstStable.maskId));
});

test('a fully manual mask uses the same publication contract as an automatic one', () => {
    const registry = new MaskAnnotationRegistry();
    registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' },
        width: 8,
        height: 8
    });
    const stable = registry.confirm('anchor-view', rgbDigest('a'));
    assert.equal(stable.source, 'manual');
    assert.equal(stable.status, 'user-confirmed');
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.stableMask?.maskId, stable.maskId);
});

test('masks bound to an older RGB digest are not current for a newer RGB', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.confirm('anchor-view', rgbDigest('a'));
    const staleView = registry.viewState('anchor-view', rgbDigest('b'));
    assert.equal(staleView.editingMask, null);
    assert.equal(staleView.stableMask, null);
    const currentView = registry.viewState('anchor-view', rgbDigest('a'));
    assert.ok(currentView.editingMask);
    assert.ok(currentView.stableMask);
});

test('Confirm Mask refuses to publish without a current Editing Mask', () => {
    const registry = new MaskAnnotationRegistry();
    assert.throws(() => registry.confirm('anchor-view', rgbDigest('a')));
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    assert.throws(() => registry.confirm('anchor-view', rgbDigest('b')));
});

test('a SAM result with an invalid artifact is rejected at the trust boundary', () => {
    const registry = new MaskAnnotationRegistry();
    const artifact = samArtifact(8, 8, 0b101);
    assert.throws(() =>
        registry.registerSamResult({
            viewId: 'anchor-view',
            rgbDigest: rgbDigest('a'),
            artifact: { ...artifact, digest: rgbDigest('f') },
            prompts
        })
    );
    assert.throws(() =>
        registry.registerSamResult({
            viewId: 'anchor-view',
            rgbDigest: rgbDigest('a'),
            artifact: { ...artifact, width: 9 },
            prompts
        })
    );
});

test('disposeView drops all mask versions for a restarted view', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.disposeView('anchor-view');
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask, null);
    assert.equal(view.stableMask, null);
});

test('returned annotations are immutable domain records', () => {
    const registry = new MaskAnnotationRegistry();
    const editing = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    assert.ok(Object.isFrozen(editing));
    assert.ok(Object.isFrozen(editing.artifact));
    assert.throws(() =>
        registry.applyBrush({
            viewId: 'anchor-view',
            rgbDigest: rgbDigest('a'),
            stroke: { xPx: 20, yPx: 20, radiusPx: 1, mode: 'add' },
            width: 8,
            height: 8
        })
    );
});
