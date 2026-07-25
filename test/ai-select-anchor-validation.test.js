const assert = require('node:assert/strict');
const test = require('node:test');

const {
    aiSelectAnchorValidationPolicyVersion,
    evaluateAnchorValidation
} = require('../.test-dist/src/ai-select/anchor-validation.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const rgbDigest = `sha256:${'a'.repeat(64)}`;

const maskArtifact = (width, height, foreground = []) => {
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

const stableMask = (artifact, overrides = {}) => ({
    maskId: 'mask-1',
    viewId: 'anchor-view',
    source: 'single-frame-sam',
    status: 'user-confirmed',
    artifact,
    createdFromRgbDigest: rgbDigest,
    ...overrides
});

const solidMask = (width = 64, height = 48) => {
    const foreground = [];
    // A centered 16x16 block: no boundary contact, one component, enough area.
    for (let y = 16; y < 32; y += 1) {
        for (let x = 24; x < 40; x += 1) {
            foreground.push([x, y]);
        }
    }
    return maskArtifact(width, height, foreground);
};

const input = (overrides = {}) => ({
    rgbReady: true,
    rgbDigest,
    rgbWidth: 64,
    rgbHeight: 48,
    cameraBindingCurrent: true,
    stableMask: stableMask(solidMask()),
    maskRevisionPending: false,
    stableIdMappingValid: true,
    renderWorkingSetValid: true,
    support: { computable: true, observedGaussianCount: 500 },
    ...overrides
});

test('a fully bound Anchor passes with no blocks or warnings', () => {
    const result = evaluateAnchorValidation(input());
    assert.deepEqual(result.hardBlocks, []);
    assert.deepEqual(result.softWarnings, []);
    assert.equal(result.canConfirm, true);
    assert.equal(result.policyVersion, aiSelectAnchorValidationPolicyVersion);
});

test('unavailable authoritative RGB and stale CameraBinding block Confirm', () => {
    const noRgb = evaluateAnchorValidation(
        input({ rgbReady: false, rgbDigest: null, stableMask: null })
    );
    assert.ok(noRgb.hardBlocks.includes('authoritative-rgb-unavailable'));
    assert.equal(noRgb.canConfirm, false);
    const staleCamera = evaluateAnchorValidation(
        input({ cameraBindingCurrent: false })
    );
    assert.ok(staleCamera.hardBlocks.includes('camera-binding-stale'));
});

test('a missing Stable Mask blocks Confirm', () => {
    const result = evaluateAnchorValidation(input({ stableMask: null }));
    assert.ok(result.hardBlocks.includes('stable-mask-missing'));
});

test('empty and nearly-empty Masks block Confirm', () => {
    const empty = evaluateAnchorValidation(
        input({ stableMask: stableMask(maskArtifact(64, 48, [])) })
    );
    assert.ok(empty.hardBlocks.includes('mask-empty'));
    const tiny = evaluateAnchorValidation(
        input({
            stableMask: stableMask(
                maskArtifact(64, 48, [
                    [10, 10],
                    [11, 10]
                ])
            )
        })
    );
    assert.ok(tiny.hardBlocks.includes('mask-below-minimum-area'));
});

test('a Mask bound to different RGB or dimensions blocks as identity mismatch', () => {
    const wrongDigest = evaluateAnchorValidation(
        input({
            stableMask: stableMask(solidMask(), {
                createdFromRgbDigest: `sha256:${'b'.repeat(64)}`
            })
        })
    );
    assert.ok(wrongDigest.hardBlocks.includes('camera-rgb-mask-mismatch'));
    const wrongSize = evaluateAnchorValidation(
        input({ stableMask: stableMask(solidMask(32, 24)) })
    );
    assert.ok(wrongSize.hardBlocks.includes('camera-rgb-mask-mismatch'));
});

test('a pending latest Mask/SAM revision blocks Confirm', () => {
    const result = evaluateAnchorValidation(
        input({ maskRevisionPending: true })
    );
    assert.ok(result.hardBlocks.includes('mask-revision-pending'));
});

test('invalid Stable ID mapping or Render Working Set blocks Confirm', () => {
    const noIds = evaluateAnchorValidation(
        input({ stableIdMappingValid: false })
    );
    assert.ok(noIds.hardBlocks.includes('stable-id-mapping-unavailable'));
    const noWorkingSet = evaluateAnchorValidation(
        input({ renderWorkingSetValid: false })
    );
    assert.ok(
        noWorkingSet.hardBlocks.includes('render-working-set-unavailable')
    );
});

test('Gaussian support must be proven computable by the probe', () => {
    const unproven = evaluateAnchorValidation(input({ support: null }));
    assert.ok(unproven.hardBlocks.includes('gaussian-support-unproven'));
    const none = evaluateAnchorValidation(
        input({ support: { computable: false, observedGaussianCount: 0 } })
    );
    assert.ok(none.hardBlocks.includes('no-computable-gaussian-support'));
});

test('soft warnings never block Confirm', () => {
    const foreground = [];
    // A big blob touching the left boundary, plus scattered fragments.
    for (let y = 4; y < 44; y += 1) {
        for (let x = 0; x < 30; x += 1) {
            foreground.push([x, y]);
        }
    }
    for (let n = 0; n < 10; n += 1) {
        // Isolated single pixels, each its own 4-connected component.
        foreground.push([60, 2 + n * 4]);
    }
    const result = evaluateAnchorValidation(
        input({
            stableMask: stableMask(maskArtifact(64, 48, foreground)),
            support: { computable: true, observedGaussianCount: 3 }
        })
    );
    assert.equal(result.canConfirm, true);
    assert.ok(result.softWarnings.includes('image-boundary-contact'));
    assert.ok(result.softWarnings.includes('fragmented-mask'));
    assert.ok(result.softWarnings.includes('weak-visible-support'));
});

test('extreme Mask sizes warn without blocking', () => {
    const few = [];
    for (let y = 20; y < 28; y += 1) {
        for (let x = 28; x < 36; x += 1) {
            few.push([x, y]);
        }
    }
    const small = evaluateAnchorValidation(
        input({
            rgbWidth: 640,
            rgbHeight: 480,
            stableMask: stableMask(maskArtifact(640, 480, few))
        })
    );
    assert.ok(small.softWarnings.includes('target-very-small'));
    assert.equal(small.canConfirm, true);

    const most = [];
    for (let y = 0; y < 48; y += 1) {
        for (let x = 0; x < 64; x += 1) {
            most.push([x, y]);
        }
    }
    const large = evaluateAnchorValidation(
        input({ stableMask: stableMask(maskArtifact(64, 48, most)) })
    );
    assert.ok(large.softWarnings.includes('target-very-large'));
    assert.equal(large.canConfirm, true);
});

test('validation answers are immutable and carry the mask analysis', () => {
    const result = evaluateAnchorValidation(input());
    assert.ok(Object.isFrozen(result));
    assert.ok(Object.isFrozen(result.hardBlocks));
    assert.equal(result.maskAnalysis?.foregroundPixels, 256);
});
