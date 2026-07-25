const assert = require('node:assert/strict');
const test = require('node:test');

const {
    applyBrushStroke,
    createEmptyMaskArtifact,
    decodeMaskArtifact,
    isMaskAnnotation,
    isMaskArtifact,
    isMaskPrompt,
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const base64Encode = (bytes) => {
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return btoa(binary);
};

const bitsetArtifact = (width, height, foregroundPixels) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    for (const [x, y] of foregroundPixels) {
        const index = y * width + x;
        bytes[index >> 3] |= 1 << (index % 8);
    }
    return {
        encoding: maskBitsetEncoding,
        width,
        height,
        data: base64Encode(bytes),
        digest: sha256Digest(bytes)
    };
};

test('createEmptyMaskArtifact produces a structurally valid zeroed bitset', () => {
    const artifact = createEmptyMaskArtifact(9, 5);
    assert.equal(artifact.encoding, maskBitsetEncoding);
    assert.equal(artifact.width, 9);
    assert.equal(artifact.height, 5);
    assert.ok(isMaskArtifact(artifact));
    const bytes = decodeMaskArtifact(artifact);
    assert.equal(bytes.length, Math.ceil((9 * 5) / 8));
    assert.ok(bytes.every((byte) => byte === 0));
    assert.equal(artifact.digest, sha256Digest(bytes));
});

test('createEmptyMaskArtifact rejects non-positive dimensions', () => {
    assert.throws(() => createEmptyMaskArtifact(0, 5));
    assert.throws(() => createEmptyMaskArtifact(5, 0));
    assert.throws(() => createEmptyMaskArtifact(2.5, 5));
});

test('decodeMaskArtifact round-trips packed bits', () => {
    const artifact = bitsetArtifact(10, 3, [
        [0, 0],
        [9, 0],
        [3, 2]
    ]);
    const bytes = decodeMaskArtifact(artifact);
    const has = (x, y) =>
        (bytes[(y * 10 + x) >> 3] & (1 << ((y * 10 + x) % 8))) !== 0;
    assert.ok(has(0, 0));
    assert.ok(has(9, 0));
    assert.ok(has(3, 2));
    assert.ok(!has(1, 0));
    assert.ok(!has(4, 2));
});

test('decodeMaskArtifact rejects a digest that does not match its bytes', () => {
    const artifact = {
        ...bitsetArtifact(4, 4, [[1, 1]]),
        digest: `sha256:${'0'.repeat(64)}`
    };
    assert.throws(() => decodeMaskArtifact(artifact));
});

test('applyBrushStroke add paints a disc and erase clears it', () => {
    const empty = createEmptyMaskArtifact(16, 16);
    const painted = applyBrushStroke(empty, {
        xPx: 8,
        yPx: 8,
        radiusPx: 2,
        mode: 'add'
    });
    const bytes = decodeMaskArtifact(painted);
    const has = (x, y) =>
        (bytes[(y * 16 + x) >> 3] & (1 << ((y * 16 + x) % 8))) !== 0;
    assert.ok(has(8, 8));
    assert.ok(has(10, 8));
    assert.ok(has(8, 10));
    assert.ok(!has(11, 8));
    assert.ok(!has(8, 5));
    assert.ok(painted.digest !== empty.digest);

    const erased = applyBrushStroke(painted, {
        xPx: 8,
        yPx: 8,
        radiusPx: 3,
        mode: 'erase'
    });
    assert.deepEqual(decodeMaskArtifact(erased), decodeMaskArtifact(empty));
});

test('applyBrushStroke clips at artifact bounds instead of wrapping', () => {
    const empty = createEmptyMaskArtifact(8, 8);
    const painted = applyBrushStroke(empty, {
        xPx: 0,
        yPx: 0,
        radiusPx: 2,
        mode: 'add'
    });
    const bytes = decodeMaskArtifact(painted);
    const has = (x, y) =>
        (bytes[(y * 8 + x) >> 3] & (1 << ((y * 8 + x) % 8))) !== 0;
    assert.ok(has(0, 0));
    assert.ok(has(2, 0));
    assert.ok(!has(7, 7));
});

test('applyBrushStroke rejects an invalid stroke', () => {
    const empty = createEmptyMaskArtifact(8, 8);
    assert.throws(() =>
        applyBrushStroke(empty, { xPx: 1, yPx: 1, radiusPx: 0, mode: 'add' })
    );
    assert.throws(() =>
        applyBrushStroke(empty, { xPx: 1.5, yPx: 1, radiusPx: 2, mode: 'add' })
    );
});

test('isMaskArtifact rejects malformed artifacts at the trust boundary', () => {
    const valid = bitsetArtifact(9, 5, [[2, 2]]);
    assert.ok(isMaskArtifact(valid));
    assert.ok(!isMaskArtifact(null));
    assert.ok(!isMaskArtifact({ ...valid, encoding: 'rle-v1' }));
    assert.ok(!isMaskArtifact({ ...valid, width: 10 }));
    assert.ok(!isMaskArtifact({ ...valid, width: 0 }));
    assert.ok(!isMaskArtifact({ ...valid, data: 'not-base64!' }));
    assert.ok(!isMaskArtifact({ ...valid, data: valid.data.slice(0, -4) }));
    assert.ok(
        !isMaskArtifact({ ...valid, digest: `sha256:${'z'.repeat(64)}` })
    );
});

test('isMaskArtifact rejects dirty trailing bits beyond the pixel count', () => {
    // 9*5 = 45 pixels = 6 bytes with 3 unused trailing bits.
    const dirty = bitsetArtifact(9, 5, [[2, 2]]);
    const bytes = decodeMaskArtifact(dirty);
    bytes[bytes.length - 1] |= 1 << 7;
    assert.ok(
        !isMaskArtifact({
            ...dirty,
            data: base64Encode(bytes)
        })
    );
});

test('isMaskArtifact accepts an empty editing bitset', () => {
    assert.ok(isMaskArtifact(createEmptyMaskArtifact(12, 7)));
});

test('isMaskPrompt validates editor prompt points', () => {
    assert.ok(
        isMaskPrompt({
            promptId: 'p-1',
            xPx: 10,
            yPx: 20,
            polarity: 'include'
        })
    );
    assert.ok(
        isMaskPrompt({
            promptId: 'p-2',
            xPx: 0,
            yPx: 0,
            polarity: 'exclude'
        })
    );
    assert.ok(
        !isMaskPrompt({ promptId: '', xPx: 1, yPx: 1, polarity: 'include' })
    );
    assert.ok(
        !isMaskPrompt({ promptId: 'p', xPx: -1, yPx: 1, polarity: 'include' })
    );
    assert.ok(
        !isMaskPrompt({ promptId: 'p', xPx: 1.5, yPx: 1, polarity: 'include' })
    );
    assert.ok(
        !isMaskPrompt({ promptId: 'p', xPx: 1, yPx: 1, polarity: 'maybe' })
    );
});

test('isMaskAnnotation validates a complete versioned annotation', () => {
    const artifact = bitsetArtifact(8, 6, [[1, 1]]);
    const annotation = {
        maskId: 'mask-1',
        viewId: 'anchor-view',
        source: 'single-frame-sam',
        status: 'draft',
        artifact,
        prompts: [{ promptId: 'p-1', xPx: 1, yPx: 1, polarity: 'include' }],
        createdFromRgbDigest: `sha256:${'a'.repeat(64)}`
    };
    assert.ok(isMaskAnnotation(annotation));
    assert.ok(
        isMaskAnnotation({
            ...annotation,
            status: 'user-confirmed',
            parentMaskId: 'mask-0'
        })
    );
    assert.ok(!isMaskAnnotation({ ...annotation, maskId: '' }));
    assert.ok(!isMaskAnnotation({ ...annotation, source: 'unknown' }));
    assert.ok(!isMaskAnnotation({ ...annotation, status: 'published' }));
    assert.ok(
        !isMaskAnnotation({
            ...annotation,
            artifact: { ...artifact, width: 9 }
        })
    );
    assert.ok(
        !isMaskAnnotation({ ...annotation, createdFromRgbDigest: 'md5:abc' })
    );
    assert.ok(
        !isMaskAnnotation({
            ...annotation,
            prompts: [{ promptId: 'p', xPx: -1, yPx: 0, polarity: 'include' }]
        })
    );
});
