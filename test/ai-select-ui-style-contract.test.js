const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

test('the View Action Bar stays fixed and never scrolls the image or actions', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const block = styles.match(
        /#ai-select-anchor-dock-primary-actions\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(block, 'missing View Action Bar styles');
    assert.match(block, /box-sizing:\s*border-box;/);
    assert.match(block, /flex-direction:\s*row;/);
    assert.match(block, /flex:\s*0 0 auto;/);
    assert.match(block, /min-height:\s*46px;/);
    assert.match(block, /justify-content:\s*flex-end;/);
    assert.match(block, /overflow:\s*hidden;/);
    assert.doesNotMatch(block, /overflow-[xy]:\s*auto;/);
    assert.match(block, /> \.pcui-container:not\(\.pcui-hidden\)/);
});

test('bottom action groups use responsive button grids', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(
        styles,
        /#ai-select-anchor-dock-primary-actions[\s\S]*?> \.pcui-container[\s\S]*?grid-template-columns:\s*repeat\(auto-fit, minmax\(120px, 1fr\)\);/
    );
});

test('Candidate operations belong to Toolbar while correction stays in Dock', () => {
    const toolbar = readFileSync('src/ui/ai-select-toolbar.ts', 'utf8');
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(toolbar, /ai-select-candidate-operation-group/);
    assert.match(toolbar, /ai-select-toolbar-candidate-\$\{operation\}/);
    assert.doesNotMatch(dock, /ai-select-apply-candidate-/);
    assert.match(dock, /ai-select-fix-candidate/);
    assert.match(dock, /ai-select-back-to-candidate/);
});

test('Navigator and View Action Bar expose the accepted keyboard and ownership seams', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /setAttribute\('role', 'listbox'\)/);
    assert.match(dock, /setAttribute\('role', 'option'\)/);
    assert.match(dock, /event\.key === 'ArrowDown'/);
    assert.match(dock, /event\.key === 'Enter'/);
    assert.match(dock, /ai-select-proposal-stepper/);
    assert.match(dock, /selectedViewPrimaryAction/);
});

test('Candidate shader state is independent and explicitly released', () => {
    const splat = readFileSync('src/splat.ts', 'utf8');
    const shader = readFileSync('src/shaders/splat-shader.ts', 'utf8');
    assert.match(splat, /setDefine\('AI_CANDIDATE_OVERLAY', true\)/);
    assert.match(splat, /setParameter\('candidateState', texture\)/);
    assert.match(splat, /deleteParameter\('candidateState'\)/);
    assert.match(shader, /uniform sampler2D candidateState/);
    assert.match(shader, /candidateStateValue == 1u/);
    assert.match(shader, /candidateStateValue == 2u/);
});
