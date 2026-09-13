import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import test from 'node:test';

// Node24 strips the actual app modules; resolve their bundler-style local imports.
const hook = registerHooks({
    resolve(specifier, context, nextResolve) {
        if (specifier.startsWith('./native-contribution-') && !specifier.endsWith('.ts')) {
            return nextResolve(`${specifier}.ts`, context);
        }
        return nextResolve(specifier, context);
    }
});
const { analyzeContribution } = await import('../../src/experiments/native-contribution-diagnostic.ts');
hook.deregister();

// Canvas is an external browser boundary: encode its actual RGBA bytes, not a PNG oracle.
globalThis.ImageData = class {
    constructor(width, height) {
        this.data = new Uint8ClampedArray(width * height * 4);
    }
};
globalThis.document = { createElement() {
    let image;
    return { getContext: () => ({ putImageData(value) {
        image = value;
    } }), toDataURL: () => Buffer.from(image.data).toString('base64') };
} };
const fixture = () => ({
    snapshot: {
        cacheA: new Uint32Array([0, 0x3f800000, 1023, 0x5000, 0, 0x3f800000, 1023 << 10, 0x5000]),
        cacheB: new Uint32Array([0x5000 | (204 << 16), 0x5000 | (10 << 16)]),
        order: new Uint32Array([0, 1]),
        count: 2,
        entryBase: 0,
        instanceBase: 0,
        sourceRows: new Uint32Array([90, 30]),
        width: 25,
        height: 25
    },
    mask: Uint8Array.from({ length: 625 }, (_, p) => +(p % 25 >= 10 && p % 25 <= 14 && Math.floor(p / 25) >= 10 && Math.floor(p / 25) <= 14)),
    rgb: new Uint8Array(2500),
    nativeHalf: new Uint16Array(2500)
});

test('metrics-only keeps full-scene Q and denominators without allocating irrelevant support', async () => {
    const frame = fixture(), sets = [[0], [0, 1]];
    const full = await analyzeContribution(frame, sets);
    assert.equal(full.support.length, 2);
    const metrics = await analyzeContribution(frame, sets, { output: 'metrics', supportStorage: { byteLimit: 0 } });
    assert.equal(metrics.support, undefined);
    assert.equal(metrics.winnerIds, undefined);
    assert.equal(metrics.supportBytes, 0);
    for (const key of ['roi', 'metrics', 'qImages', 'conservationError', 'maxRGBA8Error', 'meanRGBA8Error']) assert.deepEqual(metrics[key], full[key], key);
    assert.ok(metrics.metrics[0].targetSelected < metrics.metrics[1].targetSelected);
    assert.equal(metrics.metrics[1].targetSelected, metrics.metrics[1].target);
    assert.equal(metrics.metrics[1].negativeSelected, metrics.metrics[1].negative);
    await assert.rejects(analyzeContribution(frame, sets, { supportStorage: { byteLimit: 0 } }), /[Bb]udget|byte/);
    await assert.rejects(analyzeContribution(frame, sets, { output: 'metrics', limits: { records: 1 } }), /Incomplete contribution/);
    await assert.rejects(analyzeContribution(frame, sets, { output: 'metrics', isCurrent: () => false }), /stale/);
    const controller = new AbortController(); controller.abort();
    await assert.rejects(analyzeContribution(frame, sets, { output: 'metrics', signal: controller.signal }), /cancelled/);
});

test('full and Q-only output retain 70,000 touched hidden identities without the historical row ceiling', async () => {
    const n = 70000;
    const cacheA = new Uint32Array(n * 4), cacheB = new Uint32Array(n);
    for (let id = 0; id < n; id++) {
        cacheA[id * 4 + 1] = 0x3f800000; cacheA[id * 4 + 3] = 0x3c00;
        cacheB[id] = 0x3c00 | (255 << 16);
    }
    const frame = { snapshot: { cacheA, cacheB, order: Uint32Array.from({ length: n }, (_, id) => id), count: n, entryBase: 0, instanceBase: 0, sourceRows: new Uint32Array(n).fill(77), width: 1, height: 1 }, mask: new Uint8Array([1]), rgb: new Uint8Array(4), nativeHalf: new Uint16Array(4) };
    const sets = [[n - 1], [0]];
    const full = await analyzeContribution(frame, sets);
    const metrics = await analyzeContribution(frame, sets, { output: 'metrics', supportStorage: { byteLimit: 0 } });
    assert.equal(full.support.length, n);
    assert.deepEqual(full.support.row(0), { id: 0, sourceRow: 77, positive: 0, negative: 0, visible: 0, target: 0 });
    assert.equal(full.support.row(n - 1).visible, 1);
    assert.equal(metrics.support, undefined);
    assert.deepEqual(metrics.metrics, full.metrics);
    assert.deepEqual(metrics.qImages, full.qImages);
    assert.equal(metrics.metrics[0].targetSelected, 1);
    assert.equal(metrics.metrics[1].targetSelected, 0);
    assert.equal(metrics.metrics[0].negativeRatio, null);
    assert.equal(metrics.summary.records, n);
});
