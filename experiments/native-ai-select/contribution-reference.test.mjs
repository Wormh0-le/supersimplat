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

test('identity gate rejects an omitted fully occluded layer despite identical RGB and T', async () => {
    const { compareTraceIdentity } = await import('../../src/experiments/native-contribution-reference.ts');
    const near = { id: 8, sourceRow: 80, alpha: 1, color: [1, 0, 0] };
    const full = composeLayers([{ id: 3, sourceRow: 30, alpha: .5, color: [0, 1, 0] }, near]);
    const omitted = composeLayers([near]);
    assert.deepEqual(full.rgba, omitted.rgba);
    assert.equal(full.finalT, omitted.finalT);
    const gpu = full.contributors;
    assert.equal(compareTraceIdentity(gpu, gpu).drawOrderMatches, true);
    const mismatch = compareTraceIdentity([gpu[0]], gpu);
    assert.deepEqual(mismatch.missingCPU, [3]);
    assert.equal(mismatch.drawOrderMatches, false);
    assert.equal(compareTraceIdentity(gpu.toReversed(), gpu).drawOrderMatches, false);
    assert.equal(compareTraceIdentity(gpu.map(c => ({ ...c, drawSlot: 99 })), gpu).drawOrderMatches, false);
});

test('tiled horizontal bands preserve full-ROI raw evidence, seams, holes, traces and Q exactly', async () => {
    const { runContribution, runContributionTiled, classifySupport } = await import('../../src/experiments/native-contribution-reference.ts');
    for (const roi of [{ x: 0, y: 0, width: 31, height: 29 }, { x: 1, y: 2, width: 13, height: 23 }]) {
        const s = snapshot(31, 29, 0x5000); // second ROI excludes both centers, not their footprints
        const mask = new Uint8Array(31 * 29);
        for (let y = 0; y < 22; y++) for (let x = 0; x < 19; x++) mask[y * 31 + x] = 1;
        mask[8 * 31 + 8] = 0;
        const traces = [[roi.x + 5, roi.y + 5], [roi.x, roi.y + roi.height - 1]];
        const options = { selectionSets: [[0], [1], [0, 1]] };
        const mono = runContribution(s, roi, mask, traces, options);
        const tiled = await runContributionTiled(s, roi, mask, traces, { ...options, limits: { tilePixels: roi.width * 6 } });
        for (const key of ['regions', 'total', 'finalT', 'rgba', 'winnerIds', 'selectedSums', 'stats', 'traces']) assert.deepEqual(tiled[key], mono[key], key);
        for (const key of Object.keys(mono.summary).filter(k => k !== 'elapsedMs')) assert.deepEqual(tiled.summary[key], mono.summary[key], key);
        assert.equal(tiled.summary.tiles, Math.ceil(roi.height / 6));
        for (let id = 0; id < 2; id++) assert.deepEqual(classifySupport([{ positive: tiled.stats.positive[id], negative: tiled.stats.negative[id] }]), classifySupport([{ positive: mono.stats.positive[id], negative: mono.stats.negative[id] }]));
    }
});

test('tiled fixed total/tile caps and cancellation never resolve partial evidence', async () => {
    const { runContributionTiled, IncompleteContributionError, TILED_CONTRIBUTION_LIMITS } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot(25, 25, 0x5000);
    const roi = { x: 0, y: 0, width: 25, height: 25 }, mask = new Uint8Array(625).fill(1);
    for (const limits of [{ pixels: 624 }, { tilePixels: 24 }, { records: 1249, tilePixels: 125 }, { tilePixels: 125, tileRecords: 249 }, { elapsedMs: 0 }, { tileElapsedMs: 0 }, { bytes: 1 }, { traceRecords: 1 }]) {
        await assert.rejects(runContributionTiled(s, roi, mask, [[12, 12]], { limits }), IncompleteContributionError);
    }
    const exact = await runContributionTiled(s, roi, mask, [[2, 2], [2, 7]], { limits: { records: 1250, tileRecords: 250, tilePixels: 125, traceRecords: 4, bytes: 43191 } });
    assert.equal(exact.summary.typedArrayBytes, 43191);
    assert.equal(exact.summary.records, 1250);
    await assert.rejects(runContributionTiled(s, roi, mask, [[2, 2], [2, 7]], { limits: { tilePixels: 125, traceRecords: 3 } }), IncompleteContributionError);
    for (const [key, value] of Object.entries(TILED_CONTRIBUTION_LIMITS)) {
        await assert.rejects(runContributionTiled(s, roi, mask, [], { limits: { [key]: value + 1 } }), /hard ceiling/);
        await assert.rejects(runContributionTiled(s, roi, mask, [], { limits: { [key]: NaN } }), /Invalid/);
    }
    const controller = new AbortController();
    controller.abort();
    await assert.rejects(runContributionTiled(s, roi, mask, [], { signal: controller.signal }), /Incomplete contribution.*cancel/);
    await assert.rejects(runContributionTiled(s, roi, mask, [], { isCurrent: () => false }), /Incomplete contribution.*stale/);
    // Timer must run at the first yield, even with just one (final) tile.
    for (const tilePixels of [125, 625]) {
        let current = true;
        setTimeout(() => { current = false; }, 0);
        await assert.rejects(runContributionTiled(s, roi, mask, [], { limits: { tilePixels }, isCurrent: () => current }), /Incomplete contribution.*stale/);
        const during = new AbortController();
        setTimeout(() => during.abort(), 0);
        await assert.rejects(runContributionTiled(s, roi, mask, [], { limits: { tilePixels }, signal: during.signal }), /Incomplete contribution.*cancel/);
    }
});

test('raw support crosses tile seams before classification; exact P=1 and ratio=.8 have no epsilon', async () => {
    const { runContributionTiled, classifySupport } = await import('../../src/experiments/native-contribution-reference.ts');
    const r = await runContributionTiled(snapshot(5, 6, 0x5000), { x: 0, y: 0, width: 5, height: 6 }, new Uint8Array(30).fill(1), [], { limits: { tilePixels: 15 }, selectionSets: [[0]] });
    assert.equal(r.summary.positivePixels, 2); // y=2 and y=3, one in each band
    const a = r.selectedSums[0][2 * 5 + 2], b = r.selectedSums[0][3 * 5 + 2];
    assert.ok(a > 0 && a < 1 && b > 0 && b < 1);
    assert.equal(classifySupport([{ positive: a, negative: 0 }]).selected, false);
    assert.equal(classifySupport([{ positive: b, negative: 0 }]).selected, false);
    assert.equal(r.stats.positive[0], a + b);
    assert.equal(classifySupport([{ positive: r.stats.positive[0], negative: r.stats.negative[0] }]).selected, true);
    assert.equal(classifySupport([{ positive: 1, negative: .25 }]).selected, true);
    assert.equal(classifySupport([{ positive: 1 - Number.EPSILON, negative: 0 }]).selected, false);
    assert.equal(classifySupport([{ positive: 1, negative: .25 + Number.EPSILON }]).selected, false);
    assert.equal(classifySupport([{ positive: .5, negative: .125 }, { positive: .5, negative: .125 }]).selected, true);
});

test('actual plate ROI sizes fit tiled bounds without lifting the monolithic ceiling', async () => {
    const { runContribution, runContributionTiled } = await import('../../src/experiments/native-contribution-reference.ts');
    for (const [width, height] of [[155, 124], [177, 220], [268, 231], [256, 256]]) {
        const s = snapshot(width, height);
        s.count = 0;
        const roi = { x: 0, y: 0, width, height }, mask = new Uint8Array(width * height);
        if (mask.length > 20000) assert.throws(() => runContribution(s, roi, mask, []), /Incomplete contribution.*pixel/);
        const r = await runContributionTiled(s, roi, mask, []);
        assert.equal(r.summary.processedPixels, width * height);
        assert.equal(r.summary.typedArrayBytes, 66 + width * height * 69);
        assert.ok(r.finalT.every(t => t === 1));
        assert.ok(r.total.every(t => t === 0));
    }
    await assert.rejects(runContributionTiled(snapshot(257, 256), { x: 0, y: 0, width: 257, height: 256 }, new Uint8Array(257 * 256), []), /Incomplete contribution.*pixel/);
});

test('tiled native identity checks, degenerates and fully occluded trace records remain complete', async () => {
    const { runContribution, runContributionTiled } = await import('../../src/experiments/native-contribution-reference.ts');
    const s = snapshot(5, 5, 0x5000), roi = { x: 0, y: 0, width: 5, height: 5 }, mask = new Uint8Array(25).fill(1);
    s.cacheB[1] = 0x5000 | (255 << 16);
    const r = await runContributionTiled(s, roi, mask, [[2, 2]], { limits: { tilePixels: 5 } });
    assert.equal(r.traces[0].contributors.length, 2);
    assert.equal(r.traces[0].contributors[1].w, 0);
    assert.deepEqual(r.stats, runContribution(s, roi, mask, [[2, 2]]).stats);
    s.order[1] = 0;
    await assert.rejects(runContributionTiled(s, roi, mask, [], { limits: { tilePixels: 5 } }), /duplicate order/);
    s.order[1] = 1;
    s.cacheB[1] = 255 << 16;
    const degenerate = await runContributionTiled(s, roi, mask, [], { limits: { tilePixels: 5 } });
    assert.deepEqual(degenerate.summary.degenerateEntries, [1]);
    assert.deepEqual(degenerate.stats, runContribution(s, roi, mask, []).stats);
});
