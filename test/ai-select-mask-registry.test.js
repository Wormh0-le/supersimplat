const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createEmptyMaskArtifact,
    applyBrushStroke,
    decodeMaskArtifact,
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

test('Mask-local Undo may restore an older draft from the confirmed Editing chain', () => {
    const registry = new MaskAnnotationRegistry();
    const firstEditing = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 5, yPx: 5, radiusPx: 1, mode: 'add' },
        width: 8,
        height: 8
    });
    registry.confirm('anchor-view', rgbDigest('a'));

    registry.restoreEditing('anchor-view', firstEditing.maskId, rgbDigest('a'));
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask?.maskId, firstEditing.maskId);
    assert.equal(view.editingMaskIssue, null);
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
    assert.equal(staleView.editingMaskIssue, 'rgb-mismatch');
    const currentView = registry.viewState('anchor-view', rgbDigest('a'));
    assert.ok(currentView.editingMask);
    assert.ok(currentView.stableMask);
});

test('an Editing Mask inconsistent with a replaced Stable base fails closed', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.confirm('generated-00', rgbDigest('g'));
    registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b111),
        source: 'single-frame-sam',
        status: 'auto-good'
    });

    const view = registry.viewState('generated-00', rgbDigest('g'));
    assert.equal(view.editingMask, null);
    assert.equal(view.editingMaskIssue, 'stable-base-mismatch');
    assert.ok(view.stableMask);
});

test('the first SAM correction branches from an automatically published Stable Mask', () => {
    const registry = new MaskAnnotationRegistry();
    const stable = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b101),
        source: 'single-frame-sam',
        status: 'auto-good'
    });
    const editing = registry.registerSamResult({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b111),
        prompts
    });

    assert.equal(editing.parentMaskId, stable.maskId);
    const view = registry.viewState('generated-00', rgbDigest('g'));
    assert.equal(view.editingMask?.maskId, editing.maskId);
    assert.equal(view.editingMaskIssue, null);
    assert.equal(view.stableMask?.maskId, stable.maskId);
});

test('automatic Stable replacement rejects a correction draft from its sibling lineage', () => {
    const registry = new MaskAnnotationRegistry();
    registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b101),
        source: 'single-frame-sam',
        status: 'auto-good'
    });
    registry.registerSamResult({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b111),
        prompts
    });
    const replacement = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b1001),
        source: 'single-frame-sam',
        status: 'auto-good'
    });

    const view = registry.viewState('generated-00', rgbDigest('g'));
    assert.equal(view.editingMask, null);
    assert.equal(view.editingMaskIssue, 'stable-base-mismatch');
    assert.equal(view.stableMask?.maskId, replacement.maskId);
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

test('Clear creates an empty manual Editing Mask chained from the current draft', () => {
    const registry = new MaskAnnotationRegistry();
    const sam = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const cleared = registry.clearEditing('anchor-view', rgbDigest('a'), 8, 8);
    assert.equal(cleared.source, 'manual');
    assert.equal(cleared.status, 'draft');
    assert.equal(cleared.parentMaskId, sam.maskId);
    assert.equal(cleared.createdFromRgbDigest, rgbDigest('a'));
    assert.equal(cleared.artifact.digest, createEmptyMaskArtifact(8, 8).digest);
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask?.maskId, cleared.maskId);
});

test('Clear with no Editing Mask creates the first empty manual draft', () => {
    const registry = new MaskAnnotationRegistry();
    const cleared = registry.clearEditing('anchor-view', rgbDigest('a'), 8, 8);
    assert.equal(cleared.source, 'manual');
    assert.equal(cleared.parentMaskId, undefined);
    assert.equal(
        registry.viewState('anchor-view', rgbDigest('a')).editingMask?.maskId,
        cleared.maskId
    );
});

test('a fully manual Clear then Brush then Confirm publishes a User Confirmed Stable Mask', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.clearEditing('anchor-view', rgbDigest('a'), 8, 8);
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
    assert.notEqual(
        stable.artifact.digest,
        createEmptyMaskArtifact(8, 8).digest
    );
});

test('restoreEditing restores a retained version as the current Editing Mask', () => {
    const registry = new MaskAnnotationRegistry();
    const sam = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const cleared = registry.clearEditing('anchor-view', rgbDigest('a'), 8, 8);
    const restored = registry.restoreEditing(
        'anchor-view',
        sam.maskId,
        rgbDigest('a')
    );
    assert.equal(restored.maskId, sam.maskId);
    assert.equal(restored.source, 'single-frame-sam');
    const view = registry.viewState('anchor-view', rgbDigest('a'));
    assert.equal(view.editingMask?.maskId, sam.maskId);
    // The cleared version stays retained for a later restore.
    assert.ok(registry.version('anchor-view', cleared.maskId));
});

test('restoreEditing can detach the Editing Mask back to the empty start state', () => {
    const registry = new MaskAnnotationRegistry();
    registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.restoreEditing('anchor-view', null, rgbDigest('a'));
    assert.equal(
        registry.viewState('anchor-view', rgbDigest('a')).editingMask,
        null
    );
});

test('restoreEditing rejects unknown, stale-RGB, and Stable versions', () => {
    const registry = new MaskAnnotationRegistry();
    const sam = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    const stable = registry.confirm('anchor-view', rgbDigest('a'));
    assert.throws(() =>
        registry.restoreEditing('anchor-view', 'mask-999', rgbDigest('a'))
    );
    assert.throws(() =>
        registry.restoreEditing('anchor-view', sam.maskId, rgbDigest('b'))
    );
    // A published Stable Mask is not an Editing-chain version.
    assert.throws(() =>
        registry.restoreEditing('anchor-view', stable.maskId, rgbDigest('a'))
    );
});

test('latestAutoMask returns the newest SAM version bound to the current RGB only', () => {
    const registry = new MaskAnnotationRegistry();
    assert.equal(registry.latestAutoMask('anchor-view', rgbDigest('a')), null);
    const first = registry.registerSamResult({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        artifact: samArtifact(8, 8, 0b101),
        prompts
    });
    registry.applyBrush({
        viewId: 'anchor-view',
        rgbDigest: rgbDigest('a'),
        stroke: { xPx: 5, yPx: 5, radiusPx: 1, mode: 'add' },
        width: 8,
        height: 8
    });
    // A later hybrid draft does not replace the latest auto version.
    assert.equal(
        registry.latestAutoMask('anchor-view', rgbDigest('a'))?.maskId,
        first.maskId
    );
    // No auto version exists for a different RGB identity.
    assert.equal(registry.latestAutoMask('anchor-view', rgbDigest('b')), null);
});

test('publishAutoStable publishes an auto-review Stable Mask without an Editing Mask', () => {
    const registry = new MaskAnnotationRegistry();
    const stable = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b110),
        source: 'single-frame-sam',
        status: 'auto-review'
    });
    assert.equal(stable.viewId, 'generated-00');
    assert.equal(stable.source, 'single-frame-sam');
    // The Companion assessment explicitly selected the fail-closed label.
    assert.equal(stable.status, 'auto-review');
    assert.equal(stable.createdFromRgbDigest, rgbDigest('g'));
    const view = registry.viewState('generated-00', rgbDigest('g'));
    assert.equal(view.stableMask?.maskId, stable.maskId);
    assert.equal(view.editingMask, null);
});

test('the first Erase gesture edits the current Stable Mask instead of an empty draft', () => {
    const registry = new MaskAnnotationRegistry();
    const stable = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0xff),
        source: 'single-frame-sam',
        status: 'auto-good'
    });

    const editing = registry.applyBrush({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        stroke: { xPx: 0, yPx: 0, radiusPx: 1, mode: 'erase' },
        width: 8,
        height: 8
    });

    assert.equal(editing.source, 'hybrid');
    assert.equal(editing.parentMaskId, stable.maskId);
    // Erasing one corner may clear nearby pixels, but the rest of the
    // auto-published Stable Mask must survive in the Editing revision.
    assert.notEqual(decodeMaskArtifact(editing.artifact)[0], 0);
});

test('publishAutoStable atomically replaces the previous Stable revision', () => {
    const registry = new MaskAnnotationRegistry();
    const first = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b110),
        source: 'single-frame-sam',
        status: 'auto-review'
    });
    const second = registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b111),
        source: 'single-frame-sam',
        status: 'auto-review'
    });
    assert.notEqual(second.maskId, first.maskId);
    assert.equal(second.parentMaskId, first.maskId);
    const view = registry.viewState('generated-00', rgbDigest('g'));
    assert.equal(view.stableMask?.maskId, second.maskId);
    // The replaced revision stays retained for inspection.
    assert.equal(
        registry.version('generated-00', first.maskId)?.status,
        'auto-review'
    );
});

test('publishAutoStable rejects artifacts whose bytes do not match their digest', () => {
    const registry = new MaskAnnotationRegistry();
    const artifact = samArtifact(8, 8, 0b110);
    assert.throws(() =>
        registry.publishAutoStable({
            viewId: 'generated-00',
            rgbDigest: rgbDigest('g'),
            artifact: { ...artifact, digest: rgbDigest('f') },
            source: 'single-frame-sam',
            status: 'auto-review'
        })
    );
    assert.equal(
        registry.viewState('generated-00', rgbDigest('g')).stableMask,
        null
    );
});

test('an auto-published Stable Mask stops being current when RGB identity changes', () => {
    const registry = new MaskAnnotationRegistry();
    registry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('g'),
        artifact: samArtifact(8, 8, 0b110),
        source: 'single-frame-sam',
        status: 'auto-review'
    });
    assert.equal(
        registry.viewState('generated-00', rgbDigest('h')).stableMask,
        null
    );
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
