const assert = require('node:assert/strict');
const test = require('node:test');

const {
    clampAIViewDockHeight,
    resolveAIViewDockColumns,
    resolveAIViewWorkAreaWidth
} = require('../.test-dist/src/ai-select/ai-view-dock-layout.js');

test('AI View Dock column defaults follow the accepted viewport matrix', () => {
    assert.deepEqual(resolveAIViewDockColumns(1280), {
        navigator: true,
        inspector: true
    });
    assert.deepEqual(resolveAIViewDockColumns(1024), {
        navigator: true,
        inspector: false
    });
    assert.deepEqual(resolveAIViewDockColumns(760), {
        navigator: false,
        inspector: false
    });
});

test('explicit sidebar expansion pushes the Work Area even below its default breakpoint', () => {
    assert.deepEqual(
        resolveAIViewDockColumns(1024, {
            navigator: true,
            inspector: true
        }),
        { navigator: true, inspector: true }
    );
    assert.deepEqual(
        resolveAIViewDockColumns(760, {
            navigator: true,
            inspector: false
        }),
        { navigator: true, inspector: false }
    );
});

test('Work Area ideal width comes from authoritative RGB aspect and usable height', () => {
    assert.equal(
        resolveAIViewWorkAreaWidth({
            availableWidth: 900,
            availableHeight: 360,
            imageWidth: 1600,
            imageHeight: 900
        }),
        640
    );
    assert.equal(
        resolveAIViewWorkAreaWidth({
            availableWidth: 480,
            availableHeight: 360,
            imageWidth: 1600,
            imageHeight: 900
        }),
        480
    );
    assert.equal(
        resolveAIViewWorkAreaWidth({
            availableWidth: 900,
            availableHeight: 360,
            imageWidth: 900,
            imageHeight: 1600
        }),
        203
    );
});

test('Dock height defaults to 420 and clamps to 300 and editor height minus 160', () => {
    assert.equal(clampAIViewDockHeight(undefined, 900), 420);
    assert.equal(clampAIViewDockHeight(120, 900), 300);
    assert.equal(clampAIViewDockHeight(900, 900), 740);
    assert.equal(clampAIViewDockHeight(420, 520), 360);
});
