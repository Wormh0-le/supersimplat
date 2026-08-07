const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createThumbnailCache
} = require('../.test-dist/src/ai-select/thumbnail-cache.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

test('a cached thumbnail round-trips by RGB digest', () => {
    const cache = createThumbnailCache({ capacity: 4 });
    assert.equal(cache.get(digest('a')), undefined);
    cache.set(digest('a'), 'data:image/png;base64,aaa');
    assert.equal(cache.get(digest('a')), 'data:image/png;base64,aaa');
    assert.equal(cache.size, 1);
});

test('capacity bounds the cache and evicts the least recently used entry', () => {
    const cache = createThumbnailCache({ capacity: 3 });
    cache.set(digest('a'), 'A');
    cache.set(digest('b'), 'B');
    cache.set(digest('c'), 'C');
    cache.set(digest('d'), 'D');
    assert.equal(cache.size, 3);
    assert.equal(cache.get(digest('a')), undefined);
    assert.deepEqual(
        ['b', 'c', 'd'].map((letter) => cache.get(digest(letter))),
        ['B', 'C', 'D']
    );
});

test('reads and rewrites refresh recency', () => {
    const cache = createThumbnailCache({ capacity: 3 });
    cache.set(digest('a'), 'A');
    cache.set(digest('b'), 'B');
    cache.set(digest('c'), 'C');
    // Refresh `a` by reading it, then `b` by rewriting it.
    assert.equal(cache.get(digest('a')), 'A');
    cache.set(digest('b'), 'B2');
    cache.set(digest('d'), 'D');
    assert.equal(cache.get(digest('c')), undefined);
    assert.equal(cache.get(digest('a')), 'A');
    assert.equal(cache.get(digest('b')), 'B2');
    assert.equal(cache.size, 3);
});

test('a twenty-view Gallery stays inside the resource bound', () => {
    const cache = createThumbnailCache({ capacity: 24 });
    for (let index = 0; index < 20; index += 1) {
        cache.set(digest(String(index).padStart(2, '0')), `T${index}`);
    }
    assert.equal(cache.size, 20);
    cache.set(digest('z'.slice(0, 1)), 'TZ');
    assert.equal(cache.size, 21);
    assert.ok(cache.size <= 24);
});

test('capacity must be a positive integer', () => {
    assert.throws(() => createThumbnailCache({ capacity: 0 }));
    assert.throws(() => createThumbnailCache({ capacity: 1.5 }));
});
