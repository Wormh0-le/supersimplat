const assert = require('node:assert/strict');
const test = require('node:test');

const {
    PALETTE_BRUSH_SIZE_DEFAULT,
    PALETTE_BRUSH_SIZE_MAX,
    PALETTE_BRUSH_SIZE_MIN,
    PALETTE_EDIT_TOOLS,
    PALETTE_PROMPT_TOOLS,
    PALETTE_SNAP_PRIORITY,
    PALETTE_SNAP_THRESHOLD_PX,
    PALETTE_TOOLS,
    PALETTE_TOOL_SHORTCUTS,
    clampBrushSize,
    createFloatingPaletteState,
    dragPaletteTo,
    isPaletteEditTool,
    paletteToolForShortcutKey,
    placeBrushSizePopover,
    resetPalettePlacement,
    resolvePaletteRect,
    retargetFloatingPaletteState,
    setPaletteMode,
    snapPalette
} = require('../.test-dist/src/ai-select/floating-palette.js');

const SURFACE = { width: 400, height: 300 };
const PALETTE = { width: 200, height: 40 };

test('default placement is expanded, bottom edge, horizontally centered', () => {
    const state = createFloatingPaletteState('ctx-1');
    assert.equal(state.targetContextId, 'ctx-1');
    assert.equal(state.mode, 'expanded');
    assert.equal(state.edge, 'bottom');
    assert.equal(state.xRatio, 0.5);
    assert.equal(state.yRatio, 1);
});

test('palette state carries presentation only, never artifact identity', () => {
    const state = createFloatingPaletteState('ctx-1');
    assert.deepEqual(Object.keys(state).sort(), [
        'edge',
        'mode',
        'targetContextId',
        'xRatio',
        'yRatio'
    ]);
    // Temporary Space-hide is transient interaction, not stored state.
    assert.equal('hiddenWhileSpaceHeld' in state, false);
    assert.equal('hidden' in state, false);
});

test('the palette exposes exactly the current v1 Prompt/Edit tool set', () => {
    assert.deepEqual(PALETTE_PROMPT_TOOLS, [
        'positive-point',
        'negative-point',
        'positive-box'
    ]);
    assert.deepEqual(PALETTE_EDIT_TOOLS, ['paint', 'erase']);
    assert.deepEqual(PALETTE_TOOLS, [
        'positive-point',
        'negative-point',
        'positive-box',
        'paint',
        'erase'
    ]);
});

test('removed Prompt families are absent, not disabled placeholders', () => {
    const removed = [
        'negative-box',
        'prompt-brush',
        'text-prompt',
        'mask-constraints',
        'mask-constraint'
    ];
    for (const tool of removed) {
        assert.equal(PALETTE_TOOLS.includes(tool), false, tool);
        assert.equal(paletteToolForShortcutKey(tool), null, tool);
    }
    assert.equal(new Set(PALETTE_TOOLS).size, PALETTE_TOOLS.length);
});

test('keyboard tool mapping is deterministic and conflict audited', () => {
    assert.equal(paletteToolForShortcutKey('1'), 'positive-point');
    assert.equal(paletteToolForShortcutKey('2'), 'negative-point');
    assert.equal(paletteToolForShortcutKey('3'), 'positive-box');
    assert.equal(paletteToolForShortcutKey('b'), 'paint');
    assert.equal(paletteToolForShortcutKey('e'), 'erase');
    assert.equal(paletteToolForShortcutKey('B'), 'paint');
    assert.equal(paletteToolForShortcutKey('E'), 'erase');
    // Space is the temporary-hide gesture, never a tool shortcut.
    assert.equal(paletteToolForShortcutKey(' '), null);
    assert.equal(paletteToolForShortcutKey('x'), null);
    assert.equal(paletteToolForShortcutKey(''), null);
    const mapped = PALETTE_TOOL_SHORTCUTS.map((entry) => entry.tool).sort();
    assert.deepEqual(mapped, [...PALETTE_TOOLS].sort());
    const keys = PALETTE_TOOL_SHORTCUTS.map((entry) => entry.key);
    assert.equal(new Set(keys).size, keys.length);
});

test('resolved rect keeps the full palette inside the fitted surface', () => {
    const state = createFloatingPaletteState('ctx-1');
    const rect = resolvePaletteRect(state, SURFACE, PALETTE);
    assert.equal(rect.left, 100);
    assert.equal(rect.top, 260);
    assert.equal(rect.width, PALETTE.width);
    assert.equal(rect.height, PALETTE.height);
    assert.ok(rect.left >= 0 && rect.top >= 0);
    assert.ok(rect.left + rect.width <= SURFACE.width);
    assert.ok(rect.top + rect.height <= SURFACE.height);
});

test('resolved rect clamps when the palette exceeds the surface', () => {
    const state = createFloatingPaletteState('ctx-1');
    const rect = resolvePaletteRect(state, { width: 120, height: 30 }, PALETTE);
    assert.equal(rect.left, 0);
    assert.equal(rect.top, 0);
});

test('resolved rect never produces negative or non-finite coordinates', () => {
    const state = {
        ...createFloatingPaletteState('ctx-1'),
        xRatio: 4,
        yRatio: -2
    };
    const rect = resolvePaletteRect(state, SURFACE, PALETTE);
    assert.equal(rect.left, 200);
    assert.equal(rect.top, 0);
    const collapsed = resolvePaletteRect(
        state,
        { width: 0, height: 0 },
        PALETTE
    );
    assert.equal(collapsed.left, 0);
    assert.equal(collapsed.top, 0);
});

test('drag clamps continuously to the fitted rect and frees the edge', () => {
    const state = createFloatingPaletteState('ctx-1');
    const dragged = dragPaletteTo(state, SURFACE, PALETTE, -50, 1000);
    assert.equal(dragged.edge, 'free');
    assert.equal(dragged.xRatio, 0);
    assert.equal(dragged.yRatio, 1);
    const rect = resolvePaletteRect(dragged, SURFACE, PALETTE);
    assert.equal(rect.left, 0);
    assert.equal(rect.top, 260);
});

test('drag converts a free position into deterministic ratios', () => {
    const state = createFloatingPaletteState('ctx-1');
    const dragged = dragPaletteTo(state, SURFACE, PALETTE, 50, 65);
    assert.equal(dragged.xRatio, 0.25);
    assert.equal(dragged.yRatio, 0.25);
    assert.equal(dragged.mode, 'expanded');
});

test('drag with invalid geometry leaves the state untouched', () => {
    const state = createFloatingPaletteState('ctx-1');
    assert.equal(dragPaletteTo(state, SURFACE, PALETTE, Number.NaN, 10), state);
    assert.equal(
        dragPaletteTo(state, { width: 0, height: 300 }, PALETTE, 10, 10),
        state
    );
    assert.equal(
        dragPaletteTo(state, SURFACE, { width: 0, height: 40 }, 10, 10),
        state
    );
});

test('release within the snap threshold anchors the nearest edge exactly', () => {
    const state = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        12,
        65
    );
    const snapped = snapPalette(state, SURFACE, PALETTE);
    assert.equal(snapped.edge, 'left');
    assert.equal(snapped.xRatio, 0);
    assert.equal(snapped.yRatio, 0.25);
});

test('release outside the snap threshold keeps free placement', () => {
    const left = PALETTE_SNAP_THRESHOLD_PX + 10;
    const state = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        left,
        130
    );
    const snapped = snapPalette(state, SURFACE, PALETTE);
    assert.equal(snapped.edge, 'free');
    assert.equal(snapped.xRatio, state.xRatio);
    assert.equal(snapped.yRatio, state.yRatio);
});

test('snap ties resolve through the versioned priority order', () => {
    assert.deepEqual(PALETTE_SNAP_PRIORITY, ['top', 'right', 'bottom', 'left']);
    const distance = PALETTE_SNAP_THRESHOLD_PX - 4;
    const state = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        distance,
        distance
    );
    const snapped = snapPalette(state, SURFACE, PALETTE);
    assert.equal(snapped.edge, 'top');
    assert.equal(snapped.yRatio, 0);
    // The losing axis keeps its dragged ratio.
    assert.equal(snapped.xRatio, state.xRatio);
});

test('snap reaches the bottom and right edges', () => {
    const bottom = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        50,
        250
    );
    const snappedBottom = snapPalette(bottom, SURFACE, PALETTE);
    assert.equal(snappedBottom.edge, 'bottom');
    assert.equal(snappedBottom.yRatio, 1);
    const right = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        195,
        130
    );
    const snappedRight = snapPalette(right, SURFACE, PALETTE);
    assert.equal(snappedRight.edge, 'right');
    assert.equal(snappedRight.xRatio, 1);
});

test('collapse and expand preserve position, edge and never author anything', () => {
    const dragged = dragPaletteTo(
        createFloatingPaletteState('ctx-1'),
        SURFACE,
        PALETTE,
        160,
        208
    );
    const collapsed = setPaletteMode(dragged, 'collapsed');
    assert.equal(collapsed.mode, 'collapsed');
    assert.equal(collapsed.xRatio, dragged.xRatio);
    assert.equal(collapsed.yRatio, dragged.yRatio);
    assert.equal(collapsed.edge, dragged.edge);
    // The collapsed capsule reclamps inside the same surface.
    const capsule = { width: 48, height: 36 };
    const rect = resolvePaletteRect(collapsed, SURFACE, capsule);
    assert.ok(rect.left >= 0 && rect.top >= 0);
    assert.ok(rect.left + rect.width <= SURFACE.width);
    assert.ok(rect.top + rect.height <= SURFACE.height);
    const expanded = setPaletteMode(collapsed, 'expanded');
    assert.equal(expanded.mode, 'expanded');
    assert.equal(expanded.xRatio, dragged.xRatio);
    assert.equal(expanded.yRatio, dragged.yRatio);
});

test('reset placement restores the default geometry but keeps the mode', () => {
    const dragged = dragPaletteTo(
        setPaletteMode(createFloatingPaletteState('ctx-1'), 'collapsed'),
        SURFACE,
        PALETTE,
        0,
        0
    );
    const reset = resetPalettePlacement(dragged);
    assert.equal(reset.edge, 'bottom');
    assert.equal(reset.xRatio, 0.5);
    assert.equal(reset.yRatio, 1);
    assert.equal(reset.mode, 'collapsed');
    assert.equal(reset.targetContextId, 'ctx-1');
});

test('palette state is target-local and resets on context rotation', () => {
    const moved = dragPaletteTo(
        setPaletteMode(createFloatingPaletteState('ctx-1'), 'collapsed'),
        SURFACE,
        PALETTE,
        0,
        0
    );
    assert.equal(retargetFloatingPaletteState(moved, 'ctx-1'), moved);
    const rotated = retargetFloatingPaletteState(moved, 'ctx-2');
    assert.deepEqual(rotated, createFloatingPaletteState('ctx-2'));
    // Disposal (empty context) also resets.
    const disposed = retargetFloatingPaletteState(moved, '');
    assert.deepEqual(disposed, createFloatingPaletteState(''));
});

test('a surface resize reclamps through resolve without mutating state', () => {
    const state = createFloatingPaletteState('ctx-1');
    const before = resolvePaletteRect(state, SURFACE, PALETTE);
    const after = resolvePaletteRect(
        state,
        { width: 240, height: 120 },
        PALETTE
    );
    assert.equal(before.top, 260);
    assert.equal(after.top, 80);
    assert.equal(after.left, 20);
    assert.ok(after.top + after.height <= 120);
    assert.equal(state.xRatio, 0.5);
    assert.equal(state.yRatio, 1);
    assert.equal(state.mode, 'expanded');
});

test('brush size clamps to the shared Paint/Erase range', () => {
    assert.equal(clampBrushSize(8), 8);
    assert.equal(clampBrushSize(0), PALETTE_BRUSH_SIZE_MIN);
    assert.equal(clampBrushSize(500), PALETTE_BRUSH_SIZE_MAX);
    assert.equal(clampBrushSize(7.6), 8);
    assert.equal(clampBrushSize(Number.NaN), PALETTE_BRUSH_SIZE_DEFAULT);
    assert.equal(
        clampBrushSize(Number.POSITIVE_INFINITY),
        PALETTE_BRUSH_SIZE_DEFAULT
    );
});

test('brush popover prefers above the anchor and clamps horizontally', () => {
    const anchor = { left: 100, top: 200, width: 30, height: 30 };
    const placed = placeBrushSizePopover(
        anchor,
        { width: 160, height: 36 },
        SURFACE
    );
    assert.equal(placed.placement, 'above');
    assert.equal(placed.top, 200 - 6 - 36);
    assert.equal(placed.left, 100 + 15 - 80);
    assert.ok(placed.left >= 0);
    assert.ok(placed.left + 160 <= SURFACE.width);
});

test('brush popover keeps the fitting side even with more room elsewhere', () => {
    // Above fits; below has more room — fit wins over room.
    const placed = placeBrushSizePopover(
        { left: 100, top: 100, width: 30, height: 30 },
        { width: 160, height: 36 },
        { width: 400, height: 400 }
    );
    assert.equal(placed.placement, 'above');
    assert.equal(placed.top, 100 - 6 - 36);
});

test('the edit-tool guard matches exactly Paint and Erase', () => {
    for (const tool of PALETTE_TOOLS) {
        assert.equal(
            isPaletteEditTool(tool),
            PALETTE_EDIT_TOOLS.includes(tool)
        );
    }
    assert.equal(isPaletteEditTool('paint'), true);
    assert.equal(isPaletteEditTool('erase'), true);
    assert.equal(isPaletteEditTool('positive-box'), false);
});

test('brush popover flips below when there is no room above', () => {
    const anchor = { left: 20, top: 4, width: 30, height: 30 };
    const placed = placeBrushSizePopover(
        anchor,
        { width: 160, height: 36 },
        SURFACE
    );
    assert.equal(placed.placement, 'below');
    assert.equal(placed.top, 4 + 30 + 6);
    assert.ok(placed.top + 36 <= SURFACE.height);
});

test('brush popover stays fully clamped on degenerate geometry', () => {
    const placed = placeBrushSizePopover(
        { left: 390, top: 290, width: 30, height: 30 },
        { width: 500, height: 400 },
        SURFACE
    );
    assert.equal(placed.left, 0);
    assert.equal(placed.top, 0);
    // Ties prefer the primary (above) side deterministically.
    assert.equal(
        placeBrushSizePopover(
            { left: 0, top: 0, width: 10, height: 10 },
            { width: 10, height: 10 },
            { width: 0, height: 0 }
        ).placement,
        'above'
    );
});
