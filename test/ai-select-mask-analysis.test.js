const assert = require('node:assert/strict');
const test = require('node:test');

const {
    analyzeMaskArtifact,
    maskBitsetByteLength
} = require('../.test-dist/src/ai-select/mask-analysis.js');
const {
    createEmptyMaskArtifact,
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const artifact = (width, height, foreground = []) => {
    const bytes = new Uint8Array(maskBitsetByteLength(width, height));
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

test('an empty Mask analyzes as zero coverage with no boundary contact', () => {
    const analysis = analyzeMaskArtifact(createEmptyMaskArtifact(8, 8));
    assert.equal(analysis.foregroundPixels, 0);
    assert.equal(analysis.totalPixels, 64);
    assert.equal(analysis.coverageRatio, 0);
    assert.equal(analysis.touchesImageBoundary, false);
    assert.equal(analysis.connectedComponents, 0);
    assert.equal(analysis.largestComponentPixels, 0);
});

test('a single interior blob reports one component and no boundary contact', () => {
    const analysis = analyzeMaskArtifact(
        artifact(8, 8, [
            [3, 3],
            [4, 3],
            [3, 4],
            [4, 4]
        ])
    );
    assert.equal(analysis.foregroundPixels, 4);
    assert.equal(analysis.coverageRatio, 4 / 64);
    assert.equal(analysis.touchesImageBoundary, false);
    assert.equal(analysis.connectedComponents, 1);
    assert.equal(analysis.largestComponentPixels, 4);
});

test('foreground on any image edge counts as boundary contact', () => {
    assert.equal(
        analyzeMaskArtifact(artifact(8, 8, [[0, 4]])).touchesImageBoundary,
        true
    );
    assert.equal(
        analyzeMaskArtifact(artifact(8, 8, [[7, 4]])).touchesImageBoundary,
        true
    );
    assert.equal(
        analyzeMaskArtifact(artifact(8, 8, [[4, 0]])).touchesImageBoundary,
        true
    );
    assert.equal(
        analyzeMaskArtifact(artifact(8, 8, [[4, 7]])).touchesImageBoundary,
        true
    );
});

test('separated blobs count as distinct 4-connected components', () => {
    const analysis = analyzeMaskArtifact(
        artifact(10, 10, [
            [1, 1],
            [2, 1],
            [8, 8],
            // Diagonal contact is not 4-connected.
            [5, 5],
            [6, 6]
        ])
    );
    assert.equal(analysis.foregroundPixels, 5);
    assert.equal(analysis.connectedComponents, 4);
    assert.equal(analysis.largestComponentPixels, 2);
});

test('a full Mask reports complete coverage and boundary contact', () => {
    const foreground = [];
    for (let y = 0; y < 8; y += 1) {
        for (let x = 0; x < 8; x += 1) {
            foreground.push([x, y]);
        }
    }
    const analysis = analyzeMaskArtifact(artifact(8, 8, foreground));
    assert.equal(analysis.coverageRatio, 1);
    assert.equal(analysis.touchesImageBoundary, true);
    assert.equal(analysis.connectedComponents, 1);
});

test('analysis rejects a corrupt artifact at the trust boundary', () => {
    const valid = artifact(8, 8, [[2, 2]]);
    assert.throws(() =>
        analyzeMaskArtifact({ ...valid, digest: `sha256:${'f'.repeat(64)}` })
    );
});
