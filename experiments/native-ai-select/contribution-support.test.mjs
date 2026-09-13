import assert from 'node:assert/strict';
import { test } from 'node:test';
import { checkSupportBudget, compactSupport, mergeSupport, SUPPORT_STORAGE_LIMITS } from '../../src/experiments/native-contribution-support.ts';
import { classifySupport } from '../../src/experiments/native-contribution-reference.ts';

const reserve = 4 * 1024 * 1024;
const stats = (length) => ({
    touched: new Uint8Array(length), sourceRows: new Uint32Array(length),
    positive: new Float64Array(length), negative: new Float64Array(length),
    visible: new Float64Array(length), target: new Float64Array(length)
});
const fixture = (rows) => {
    const result = stats(Math.max(-1, ...rows.map(r => r[0])) + 1);
    for (const [id, sourceRow, positive = 0, negative = 0, visible = 0, target = 0] of rows) {
        result.touched[id] = 1;
        result.sourceRows[id] = sourceRow;
        result.positive[id] = positive; result.negative[id] = negative;
        result.visible[id] = visible; result.target[id] = target;
    }
    return result;
};

test('68,497 touched identities survive bounded pages, including zero, N-only, weak and hidden support', () => {
    const input = stats(68498);
    input.touched.fill(1); input.touched[7] = 0;
    for (let id = 0; id < input.touched.length; id++) {
        input.sourceRows[id] = Math.floor(id / 2); // Different instances of the same source row.
        input.positive[id] = id % 4 === 0 ? 0.125 : 0;
        input.negative[id] = id % 4 === 1 ? 2 : 0;
        input.visible[id] = id % 4 === 2 ? 0 : 3;
        input.target[id] = id % 4 === 3 ? 0.0625 : 0;
    }
    const table = compactSupport(input);
    assert.equal(table.length, 68497);
    assert.equal(table.byteLength, 2739880);
    assert.ok(Object.isFrozen(table));
    let seen = 0;
    for (let offset = 0; offset < table.length; offset += 4096) {
        const page = table.page(offset);
        assert.ok(Object.isFrozen(page));
        assert.ok(page.length <= 4096);
        const roundTrip = JSON.parse(JSON.stringify(page));
        for (const row of roundTrip) {
            const id = seen < 7 ? seen : seen + 1;
            assert.deepEqual(row, { id, sourceRow: Math.floor(id / 2), positive: id % 4 === 0 ? 0.125 : 0,
                negative: id % 4 === 1 ? 2 : 0, visible: id % 4 === 2 ? 0 : 3, target: id % 4 === 3 ? 0.0625 : 0 });
            assert.equal(table.idAt(seen++), id);
        }
    }
    assert.equal(seen, 68497);
    const before = table.row(0);
    for (const array of Object.values(input)) array.fill(0);
    assert.deepEqual(table.row(0), before);
    assert.notEqual(table.row(0), before);
    assert.throws(() => { before.sourceRow = 100; }, TypeError);
    const page = table.page(0, 1);
    assert.throws(() => { page[0].positive = 999; }, TypeError);
    assert.throws(() => page.push(before), TypeError);
    assert.deepEqual(table.row(0), before);
    assert.ok(Object.values(table).every(value => !ArrayBuffer.isView(value)));
    assert.equal(table.toJSON, undefined);
});

test('budget accounts for retained tables, new columns and fixed export staging, with lower-only safe integers', () => {
    assert.deepEqual(SUPPORT_STORAGE_LIMITS, { bytes: 256 * 1024 * 1024, exportBytes: reserve, pageRows: 4096 });
    assert.ok(Object.isFrozen(SUPPORT_STORAGE_LIMITS));
    assert.deepEqual(checkSupportBudget(80, { retainedBytes: 120, byteLimit: reserve + 200 }), {
        retainedBytes: 120, additionalBytes: 80, exportReserveBytes: reserve, peakBytes: reserve + 200, byteLimit: reserve + 200
    });
    assert.throws(() => checkSupportBudget(81, { retainedBytes: 120, byteLimit: reserve + 200 }));
    for (const invalid of [-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, null, '40']) {
        assert.throws(() => checkSupportBudget(invalid));
        assert.throws(() => checkSupportBudget(0, { retainedBytes: invalid }));
        assert.throws(() => checkSupportBudget(0, { byteLimit: invalid }));
    }
    assert.throws(() => checkSupportBudget(0, { byteLimit: 256 * 1024 * 1024 + 1 }));
    assert.throws(() => checkSupportBudget(1, { retainedBytes: Number.MAX_SAFE_INTEGER }));
    assert.throws(() => compactSupport(stats(0), { byteLimit: reserve - 1 }));
    assert.equal(compactSupport(stats(0), { byteLimit: reserve }).byteLength, 0);
    assert.throws(() => compactSupport(fixture([[0, 0]]), { byteLimit: reserve + 39 }));
});

test('dimensions, typed columns and all nonnegative finite input sums are validated', () => {
    for (const key of ['touched', 'sourceRows', 'positive', 'negative', 'visible', 'target']) {
        const input = fixture([[0, 0], [1, 0]]);
        input[key] = new input[key].constructor(1);
        assert.throws(() => compactSupport(input));
        input[key] = [0, 0];
        assert.throws(() => compactSupport(input));
    }
    for (const key of ['positive', 'negative', 'visible', 'target']) {
        for (const invalid of [NaN, Infinity, -Infinity, -0.01]) {
            const input = stats(1); // Untouched data is validated too.
            input[key][0] = invalid;
            assert.throws(() => compactSupport(input));
        }
    }
    const maximum = compactSupport(fixture([[0, 0xffffffff]]));
    assert.equal(maximum.row(0).sourceRow, 0xffffffff);
});

test('row and page indices are bounded integers; empty and end pages are valid', () => {
    const table = compactSupport(fixture([[2, 9], [5, 10]]));
    assert.deepEqual(table.page(), [table.row(0), table.row(1)]);
    assert.deepEqual(table.page(2), []);
    assert.deepEqual(table.page(0, 0), []);
    assert.deepEqual(compactSupport(stats(0)).page(), []);
    for (const index of [-1, 0.5, 2, NaN, Infinity, Number.MAX_SAFE_INTEGER]) {
        assert.throws(() => table.row(index));
        assert.throws(() => table.idAt(index));
    }
    for (const offset of [-1, 0.5, 3, NaN, Infinity]) assert.throws(() => table.page(offset));
    for (const count of [-1, 0.5, 4097, NaN, Infinity]) assert.throws(() => table.page(0, count));
});

test('merge sums raw float64 before frozen classification without losing zero or duplicate-source instances', () => {
    const a = compactSupport(fixture([[0, 8, 0.5, 0.125, 2, 1], [2, 8, 0, 2], [3, 9],
        [4, 10, 1, 0, 1 + 2 ** -40], [5, 11, 0.5], [6, 12, 1, 1], [7, 13, 1, 0.25 + 2 ** -40]]));
    const b = compactSupport(fixture([[0, 8, 0.5, 0.125, 3, 2], [1, 8, 0.125], [4, 10, 0, 0, 2 ** -40], [5, 11, 0.5 - 2 ** -52]]));
    const merged = mergeSupport(a, b, { retainedBytes: a.byteLength + b.byteLength });
    assert.equal(merged.length, 8); assert.equal(merged.byteLength, 320);
    assert.deepEqual(merged.page().map(r => r.id), [0, 1, 2, 3, 4, 5, 6, 7]);
    assert.deepEqual(merged.row(0), { id: 0, sourceRow: 8, positive: 1, negative: 0.25, visible: 5, target: 3 });
    assert.equal(merged.row(4).visible, 1 + 2 ** -39);
    assert.equal(merged.row(5).positive, 1 - 2 ** -52);
    assert.deepEqual(merged.page().map(r => classifySupport([r]).selected), [true, false, false, false, true, false, false, false]);
    assert.deepEqual(merged.page().map(r => classifySupport([r]).status === 'unknown'), [false, true, false, true, false, true, false, false]);
    assert.equal(classifySupport([merged.row(6)]).conflict, true);
    assert.equal(classifySupport([merged.row(0)]).ratio, 0.8);
    assert.equal(merged.row(2).negative, 2);
    assert.equal(merged.row(3).visible, 0);
    assert.throws(() => mergeSupport(a, a));
    assert.throws(() => mergeSupport(a, compactSupport(fixture([[0, 99]]))));
    for (const key of ['positive', 'negative', 'visible', 'target']) {
        const input = fixture([[0, 0]]); input[key][0] = Number.MAX_VALUE;
        assert.throws(() => mergeSupport(compactSupport(input), compactSupport(input)));
    }
    const empty = compactSupport(stats(0));
    assert.deepEqual(mergeSupport(empty, a).page(), a.page());
});

test('failed replacement, abort and stale checks leave every previously published table readable', () => {
    const a = compactSupport(fixture([[0, 1, 1]]));
    const b = compactSupport(fixture([[1, 1, 0, 2]]));
    let published = mergeSupport(a, b);
    const old = published;
    const retainedBytes = a.byteLength + b.byteLength + old.byteLength;
    assert.throws(() => { published = mergeSupport(a, b, { retainedBytes, byteLimit: reserve + retainedBytes + 79 }); });
    assert.equal(published, old);
    const controller = new AbortController(); controller.abort();
    for (const options of [{ signal: controller.signal }, { isCurrent: () => false }]) {
        assert.throws(() => checkSupportBudget(0, options));
        assert.throws(() => compactSupport(fixture([[0, 1]]), options));
        assert.throws(() => { published = mergeSupport(a, b, options); });
        assert.equal(published, old);
    }
    let calls = 0;
    assert.throws(() => compactSupport(fixture([[0, 1]]), { isCurrent: () => ++calls < 2 }));
    calls = 0;
    assert.throws(() => { published = mergeSupport(a, b, { isCurrent: () => ++calls < 3 }); });
    assert.equal(published, old);
    assert.deepEqual(a.row(0), old.row(0));
    assert.deepEqual(b.row(0), old.row(1));
    published = mergeSupport(a, b, { retainedBytes, byteLimit: reserve + retainedBytes + 80 });
    assert.notEqual(published, old);
    assert.deepEqual(published.page(), old.page());
});

test('large interleaved merge retains every identity and validates external stream contracts', () => {
    const left = stats(68497), right = stats(68497);
    for (let id = 0; id < 68497; id++) {
        const input = id % 2 ? right : left;
        input.touched[id] = 1; input.sourceRows[id] = 17;
    }
    const a = compactSupport(left), b = compactSupport(right);
    const table = mergeSupport(a, b, { retainedBytes: a.byteLength + b.byteLength });
    assert.equal(table.length, 68497); assert.equal(table.byteLength, 2739880);
    for (let i = 0; i < table.length; i++) {
        assert.equal(table.idAt(i), i);
        assert.deepEqual(table.row(i), { id: i, sourceRow: 17, positive: 0, negative: 0, visible: 0, target: 0 });
    }
    const empty = compactSupport(stats(0));
    const validRow = { id: 0, sourceRow: 0, positive: 0, negative: 0, visible: 0, target: 0 };
    const external = rows => ({ length: rows.length, byteLength: rows.length * 40, row: i => rows[i], idAt: i => rows[i].id });
    for (const id of [-1, 0.5, NaN, Infinity, 0x100000000]) {
        assert.throws(() => mergeSupport(external([{ ...validRow, id }]), empty));
        assert.throws(() => mergeSupport(external([{ ...validRow, sourceRow: id }]), empty));
    }
    assert.throws(() => mergeSupport(external([validRow, validRow]), empty));
    assert.throws(() => mergeSupport(external([{ ...validRow, id: 2 }, validRow]), empty));
    assert.throws(() => mergeSupport({ ...external([validRow]), byteLength: 39 }, empty));
    assert.throws(() => mergeSupport({ ...external([validRow]), length: 0.5 }, empty));
    assert.throws(() => mergeSupport({ ...external([validRow]), idAt: () => 2 }, empty));
    for (const key of ['positive', 'negative', 'visible', 'target']) {
        for (const invalid of [-1, NaN, Infinity]) {
            assert.throws(() => mergeSupport(external([{ ...validRow, [key]: invalid }]), empty));
        }
    }
});
