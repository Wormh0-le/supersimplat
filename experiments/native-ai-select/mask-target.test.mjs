import assert from 'node:assert/strict';
import { test } from 'node:test';
import { maskInputs, taskId } from '../../src/experiments/native-mask-target.ts';

const bundle = () => ({ masks: ['easy-apple', 'medium-plate'].flatMap(task => ['A', 'B', 'C'].map(role => ({
    task, role, path: `${role}.${task}.version-2.png`, sha256: 'a'.repeat(64), provenance: role === 'C' ? 'assistant-polygon-draft' : 'publisher-test-mask'
}))) });

test('only apple and plate target identities are accepted', () => {
    assert.equal(taskId('easy-apple'), 'easy-apple');
    assert.equal(taskId('medium-plate'), 'medium-plate');
    for (const value of ['hard-glass', '', null, {}, 1]) assert.throws(() => taskId(value));
});

test('Mask paths and all six hashes come from the manifest, not reconstructed filenames', () => {
    const source = bundle();
    const inputs = maskInputs(source);
    assert.equal(inputs.length, 6);
    assert.equal(inputs[5].path, 'C.medium-plate.version-2.png');
    assert.equal(inputs[5].sha256, 'a'.repeat(64));
    source.masks[5].path = 'changed.png';
    assert.equal(inputs[5].path, 'C.medium-plate.version-2.png');
    assert.ok(Object.isFrozen(inputs) && inputs.every(Object.isFrozen));
});

test('ambiguous, missing, malformed and escaping Mask records fail before acquisition', () => {
    const duplicate = bundle(); duplicate.masks.push(duplicate.masks[0]);
    assert.throws(() => maskInputs(duplicate));
    const missing = bundle(); missing.masks.pop(); assert.throws(() => maskInputs(missing));
    for (const path of ['../escape.png', '/root.png', 'https://host/mask.png', 'mask.png?query']) {
        const source = bundle(); source.masks[0].path = path; assert.throws(() => maskInputs(source));
    }
    for (const sha256 of ['', 'a'.repeat(63), 'z'.repeat(64), null]) {
        const source = bundle(); source.masks[0].sha256 = sha256; assert.throws(() => maskInputs(source));
    }
    for (const value of [null, {}, { masks: [null] }]) assert.throws(() => maskInputs(value));
});
