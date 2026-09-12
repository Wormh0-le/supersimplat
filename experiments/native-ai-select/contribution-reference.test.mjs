import assert from 'node:assert/strict';
import test from 'node:test';

import { composeLayers } from '../../src/experiments/native-contribution-reference.ts';

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);

test('far .8 behind near .04 preserves identity and exact incoming transmittance', () => {
    const result = composeLayers([
        { id: 9, sourceRow: 90, alpha: 0.8, color: [1, 0, 0] },
        { id: 3, sourceRow: 30, alpha: 0.04, color: [0, 1, 0] }
    ]);
    assert.deepEqual(result.contributors.map(c => [c.id, c.sourceRow, c.drawSlot]), [[3, 30, 1], [9, 90, 0]]);
    close(result.contributors[0].w, 0.04);
    close(result.contributors[1].w, 0.768);
    close(result.finalT, 0.192);
    close(result.total + result.finalT, 1);
    assert.equal(result.winnerId, 9);
    assert.deepEqual(Array.from(result.rgba), [0.768, 0.04, 0, 0.808]);
});

test('zero opacity has no winner; opaque near layer does not truncate hidden contributors', () => {
    assert.equal(composeLayers([{ id: 1, sourceRow: 7, alpha: 0 }]).winnerId, -1);
    const r = composeLayers([{ id: 1, sourceRow: 7, alpha: 0.8 }, { id: 2, sourceRow: 8, alpha: 1 }]);
    assert.equal(r.contributors.length, 2);
    assert.equal(r.contributors[1].w, 0);
    assert.equal(r.finalT, 0);
    assert.throws(() => composeLayers([{ id: 1, sourceRow: 7, alpha: 1 }], 0), /Incomplete contribution/);
});

// Packed native cache fixtures, NOT PLY data. Half 1 = 0x3c00, half 32 = 0x5000.
const snapshot = (width = 1, height = 1, axis = 0x3c00) => ({
    cacheA: new Uint32Array([0, 0x3f800000, 1023, axis, 0, 0x3f800000, 1023 << 10, axis]),
    cacheB: new Uint32Array([axis | (204 << 16), axis | (10 << 16)]),
    order: new Uint32Array([0, 1]), count: 2, entryBase: 0, instanceBase: 0,
    sourceRows: new Uint32Array([90, 30]), width, height
});

test('native cache streaming matches center hand calculation, selected Q and all ROI pixels', async () => {
    const { runContribution } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot();
    const r = runContribution(s, { x: 0, y: 0, width: 1, height: 1 }, new Uint8Array([1]), [[0, 0]], { selectionSets: [[0], [1], [0, 1]] });
    close(r.total[0], 206 / 255);
    close(r.finalT[0], 49 / 255);
    close(r.traces[0].contributors[0].w, 10 / 255);
    close(r.traces[0].contributors[1].w, 196 / 255);
    assert.deepEqual(r.traces[0].contributors.map(c => [c.id, c.sourceRow, c.drawSlot]), [[1, 30, 1], [0, 90, 0]]);
    assert.equal(r.winnerIds[0], 0);
    close(r.selectedSums[0][0], 196 / 255);
    close(r.selectedSums[1][0], 10 / 255);
    close(r.selectedSums[2][0], r.total[0]);
    close(r.stats.target[0], 196 / 255);
    assert.equal(r.stats.positive[0], 0); // erosion cannot establish support in a 1px ROI
    assert.equal(r.summary.records, 2);
    assert.equal(r.summary.processedPixels, 1);
    assert.equal(r.summary.truncated, false);
    assert.equal(r.summary.residualBound, 0);
    close(r.rgba[3], r.total[0]);
    close(r.rgba[0], 0.76865328722093036);
});

test('classification uses immutable equal-weight raw evidence; unobserved B is not negative', async () => {
    const { classifySupport } = await import('../../src/experiments/native-contribution-reference.ts');
    const a = Object.freeze({ positive: 4, negative: 0 });
    const b = Object.freeze({ positive: 0, negative: 0 });
    assert.deepEqual(classifySupport([a, b]), { positive: 4, negative: 0, support: 4, ratio: 1, status: 'selected', selected: true, conflict: false });
    const conflict = classifySupport([a, { positive: 0, negative: 1 }]);
    assert.equal(conflict.ratio, 0.8);
    assert.equal(conflict.selected, true);
    assert.equal(conflict.conflict, true);
    assert.equal(classifySupport([b]).status, 'unknown');
    assert.equal(classifySupport([{ positive: 0.4, negative: 0 }]).status, 'unknown');
    assert.equal(classifySupport([{ positive: 0, negative: 1 }]).status, 'rejected');
    assert.equal(classifySupport([a, { positive: 0, negative: 2 }]).status, 'rejected');
    assert.deepEqual(a, { positive: 4, negative: 0 });
});

test('oracle rejects invalid bounds, identities and colors instead of producing plausible partial evidence', () => {
    const layer = { id: 1, sourceRow: 2, alpha: 0.5 };
    assert.throws(() => composeLayers([layer], NaN), /Invalid/);
    assert.throws(() => composeLayers([layer, layer]), /duplicate/);
    assert.throws(() => composeLayers([{ ...layer, id: -1 }]), /Invalid/);
    assert.throws(() => composeLayers([{ ...layer, color: [NaN, 0, 0] }]), /Invalid/);
});

test('complete ROI includes background, fixed ignore bands, and conservation at every pixel', async () => {
    const { runContribution } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot(25, 25, 0x5000);
    const mask = new Uint8Array(625);
    // 5x5 mask: only its central pixel survives radius-2 erosion.
    for (let y = 10; y <= 14; y++) for (let x = 10; x <= 14; x++) mask[y * 25 + x] = 1;
    const r = runContribution(s, { x: 0, y: 0, width: 25, height: 25 }, mask, [[12, 12]], { selectionSets: [[0, 1]] });
    assert.equal(r.summary.processedPixels, 625);
    assert.equal(r.summary.records, 1250);
    assert.equal(r.summary.positivePixels, 1);
    assert.equal(r.summary.negativePixels, 120); // 17x17 ROI interior minus 13x13 mask dilation
    assert.equal(r.summary.targetPixels, 25);
    assert.equal(r.regions[12 * 25 + 12], 1);
    assert.equal(r.regions[12 * 25 + 11], 0);
    assert.equal(r.regions[12 * 25 + 6], 0); // distance four: gap
    assert.equal(r.regions[12 * 25 + 5], 2); // distance five: negative
    assert.equal(r.regions[0], 0); // cannot establish complete neighborhood at ROI boundary
    assert.equal(r.winnerIds[0], -1);
    assert.equal(r.traces.length, 1);
    assert.equal(r.traces[0].contributors.length, 2);
    for (let p = 0; p < 625; p++) {
        close(r.total[p] + r.finalT[p], 1);
        close(r.rgba[p * 4 + 3], r.total[p]);
        close(r.selectedSums[0][p], r.total[p]);
    }
    close(r.stats.positive[0], 196 / 255);
    assert.ok(r.stats.negative[0] > 0);
    close(r.stats.visible[0] + r.stats.visible[1], r.total.reduce((a, b) => a + b, 0));
});

test('entry bases, reversed order, stale cache and untouched source identities are explicit', async () => {
    const { runContribution } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot();
    s.cacheA = new Uint32Array([...s.cacheA, 0, 0, 0, 0x7c00]); // stale invalid axis
    s.cacheB = new Uint32Array([...s.cacheB, 0x7c00]);
    s.order = new Uint32Array([1, 999999]); // stale order tail ignored too
    s.count = 1;
    s.entryBase = 1;
    s.instanceBase = 2;
    s.sourceRows = new Uint32Array([9, 8, 77, 66]);
    const roi = { x: 0, y: 0, width: 1, height: 1 };
    const r = runContribution(s, roi, new Uint8Array([1]), [[0, 0]]);
    assert.equal(r.winnerIds[0], 2);
    assert.deepEqual(r.traces[0].contributors.map(c => [c.id, c.sourceRow]), [[2, 77]]);
    assert.deepEqual(Array.from(r.stats.touched), [0, 0, 1, 0]);
    assert.equal(r.stats.visible[0], 0);
    const original = snapshot();
    const first = runContribution(original, roi, new Uint8Array([1]), []);
    original.order.reverse();
    const reversed = runContribution(original, roi, new Uint8Array([1]), []);
    close(reversed.stats.visible[1], 2 / 255);
    assert.ok(first.stats.visible[1] > reversed.stats.visible[1]);
    close(first.total[0], reversed.total[0]);
});

test('all hard limits fail explicitly; exact typed-array accounting includes scratch', async () => {
    const { runContribution, IncompleteContributionError } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot();
    const roi = { x: 0, y: 0, width: 1, height: 1 };
    const mask = new Uint8Array([1]);
    const options = { selectionSets: [[0], [1], [0, 1]] };
    assert.equal(runContribution(s, roi, mask, [[0, 0]], options).summary.typedArrayBytes, 178);
    for (const limits of [{ pixels: 0 }, { records: 1 }, { traceRecords: 1 }, { bytes: 177 }, { tracePixels: 0 }, { selectionSets: 2 }]) {
        assert.throws(() => runContribution(s, roi, mask, [[0, 0]], { ...options, limits }), IncompleteContributionError);
    }
    assert.throws(() => runContribution(s, roi, mask, [], { limits: { records: 20000001 } }), /hard ceiling/);
    assert.throws(() => runContribution(s, { ...roi, x: 1 }, mask, []), /outside framebuffer/);
    assert.throws(() => runContribution(s, roi, new Uint8Array(0), []), /full framebuffer/);
    assert.throws(() => runContribution(s, roi, mask, [[1, 0]]), /outside ROI/);
    assert.throws(() => runContribution(s, roi, mask, [[0, 0], [0, 0]]), /duplicate trace/);
    assert.throws(() => runContribution({ ...s, order: new Uint32Array([0, 0]) }, roi, mask, []), /duplicate order/);
    assert.throws(() => runContribution({ ...s, order: new Uint32Array([0, 2]) }, roi, mask, []), /identity/);
});

test('ellipse rasterization uses Y-down centers, pixel centers, and exact native footprint', async () => {
    const { runContribution, halfToFloat } = await import('../../src/experiments/native-contribution-reference.ts');
    assert.equal(halfToFloat(0x0001), 2 ** -24);
    assert.equal(halfToFloat(0xbc00), -1);
    assert.equal(halfToFloat(0x7c00), Infinity);
    assert.ok(Number.isNaN(halfToFloat(0x7e00)));
    const s = snapshot(5, 5);
    s.count = 1;
    // x=0 NDC, positive y NDC 0.1 puts center at (2.5,1.25), not (2.5,3.75).
    s.cacheA[0] = 3277 << 16;
    const r = runContribution(s, { x: 0, y: 0, width: 5, height: 5 }, new Uint8Array(25).fill(1), [[2, 1], [2, 3]]);
    assert.ok(r.total[1 * 5 + 2] > 0.5);
    assert.equal(r.total[3 * 5 + 2], 0);
    assert.equal(r.total[1 * 5 + 1], 0); // outside ellipse, despite quad bbox
    assert.equal(r.traces[1].contributors.length, 0);
    assert.equal(r.winnerIds[3 * 5 + 2], -1);
    // Native vertex shader discards zero-alpha splats before decoding axes.
    s.cacheA[0] = 0;
    s.cacheB[0] = 0x3c00;
    const zero = runContribution(s, { x: 0, y: 0, width: 5, height: 5 }, new Uint8Array(25).fill(1), [[2, 2]]);
    assert.equal(zero.total[12], 0);
    assert.equal(zero.finalT[12], 1);
    assert.equal(zero.winnerIds[12], -1);
    assert.equal(zero.traces[0].contributors.length, 0);
});

test('zero-width native primitives are reported; other nonfinite axes reject', async () => {
    const { runContribution } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot(1, 1);
    s.count = 1;
    s.cacheA[3] = 0x7fff7fff;
    s.cacheB[0] = 0xff0000;
    const roi = { x: 0, y: 0, width: 1, height: 1 };
    const mask = new Uint8Array([1]);
    const result = runContribution(s, roi, mask, []);
    assert.deepEqual(result.summary.degenerateEntries, [0]);
    assert.equal(result.finalT[0], 1);
    assert.equal(result.winnerIds[0], -1);
    s.cacheB[0] |= 0x3c00;
    assert.throws(() => runContribution(s, roi, mask, []), /nonfinite/);
});
