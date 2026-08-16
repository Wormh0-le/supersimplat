const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AI_VIEW_DOCK_DEFAULT_PREFERENCES,
    clampAIViewDockHeight,
    parseAIViewDockPreferences,
    resizeAIViewDockSidebar,
    resolveAIViewDockColumns,
    resolveAIViewDockLayout,
    resolveAIViewImageRect,
    serializeAIViewDockPreferences,
    setAIViewDockSidebarExpanded,
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

test('constrained layouts collapse Inspector before Navigator despite saved expansion', () => {
    assert.deepEqual(
        resolveAIViewDockColumns(1024, {
            navigator: true,
            inspector: true
        }),
        { navigator: true, inspector: false }
    );
    assert.deepEqual(
        resolveAIViewDockColumns(760, {
            navigator: true,
            inspector: true
        }),
        { navigator: false, inspector: false }
    );
});

test('wide and 1024px layouts reserve surplus width for the resident Work Area', () => {
    assert.deepEqual(resolveAIViewDockLayout(1280), {
        navigator: true,
        navigatorWidth: 220,
        inspector: true,
        inspectorWidth: 280,
        workAreaWidth: 764
    });
    assert.deepEqual(resolveAIViewDockLayout(1024), {
        navigator: true,
        navigatorWidth: 220,
        inspector: false,
        inspectorWidth: 0,
        workAreaWidth: 796
    });
});

test('sidebar device preferences clamp supported widths and reject corrupt values', () => {
    assert.deepEqual(
        parseAIViewDockPreferences(
            JSON.stringify({
                navigatorWidth: 90,
                inspectorWidth: 999,
                navigatorExpanded: false,
                inspectorExpanded: true
            })
        ),
        {
            navigatorWidth: 180,
            inspectorWidth: 360,
            navigatorExpanded: false,
            inspectorExpanded: true
        }
    );
    assert.deepEqual(
        parseAIViewDockPreferences(
            JSON.stringify({
                navigatorWidth: 'wide',
                inspectorWidth: null,
                navigatorExpanded: 'yes'
            })
        ),
        AI_VIEW_DOCK_DEFAULT_PREFERENCES
    );
    assert.deepEqual(
        parseAIViewDockPreferences('{not-json'),
        AI_VIEW_DOCK_DEFAULT_PREFERENCES
    );
    const saved = {
        navigatorWidth: 236,
        inspectorWidth: 304,
        navigatorExpanded: true,
        inspectorExpanded: false
    };
    assert.deepEqual(
        parseAIViewDockPreferences(serializeAIViewDockPreferences(saved)),
        saved
    );
    const collapsed = setAIViewDockSidebarExpanded(
        AI_VIEW_DOCK_DEFAULT_PREFERENCES,
        'inspector',
        false
    );
    assert.equal(collapsed.inspectorExpanded, false);
    assert.equal(
        setAIViewDockSidebarExpanded(collapsed, 'inspector', true)
            .inspectorExpanded,
        true
    );
    assert.equal(
        resizeAIViewDockSidebar(collapsed, 'navigator', 999).navigatorWidth,
        280
    );
    assert.equal(
        resizeAIViewDockSidebar(collapsed, 'inspector', 1).inspectorWidth,
        240
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

test('automatic image fit has a safety margin and manual zoom survives resize until reset', () => {
    const automatic = resolveAIViewImageRect(
        {
            viewportWidth: 800,
            viewportHeight: 450,
            imageWidth: 1600,
            imageHeight: 900
        },
        { mode: 'auto' }
    );
    assert.deepEqual(automatic, {
        left: 22,
        top: 12,
        width: 757,
        height: 426
    });
    const manual = {
        mode: 'manual',
        width: automatic.width * 1.5
    };
    const resized = resolveAIViewImageRect(
        {
            viewportWidth: 620,
            viewportHeight: 360,
            imageWidth: 1600,
            imageHeight: 900
        },
        manual
    );
    assert.equal(resized.width, manual.width);
    assert.equal(resized.height, manual.width * (900 / 1600));
    const switchedAspect = resolveAIViewImageRect(
        {
            viewportWidth: 620,
            viewportHeight: 360,
            imageWidth: 900,
            imageHeight: 1600
        },
        manual
    );
    assert.equal(switchedAspect.width, manual.width);
    assert.equal(switchedAspect.height, manual.width * (1600 / 900));
    const reset = resolveAIViewImageRect(
        {
            viewportWidth: 620,
            viewportHeight: 360,
            imageWidth: 1600,
            imageHeight: 900
        },
        { mode: 'auto' }
    );
    assert.ok(reset.width <= 596);
    assert.ok(reset.height <= 336);
});

test('Dock height defaults to 420 and clamps to 300 and editor height minus 160', () => {
    assert.equal(clampAIViewDockHeight(undefined, 900), 420);
    assert.equal(clampAIViewDockHeight(120, 900), 300);
    assert.equal(clampAIViewDockHeight(900, 900), 740);
    assert.equal(clampAIViewDockHeight(420, 520), 360);
});
