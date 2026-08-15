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

test('AI View Dock uses the full Dock width and gives ultrawide space to useful sidebars', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const header = styles.match(
        /#ai-select-anchor-dock-header\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    const workspace = styles.match(
        /#ai-select-anchor-dock-main\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(header, 'missing compact Dock header styles');
    assert.ok(workspace, 'missing Dock workspace styles');
    assert.match(header, /display:\s*flex;/);
    assert.match(header, /height:\s*48px;/);
    assert.doesNotMatch(header, /max-width:\s*1440px;/);
    assert.doesNotMatch(header, /margin-inline:\s*auto;/);
    assert.match(
        header,
        /#ai-select-candidate-actions\.pcui-hidden[\s\S]*?#ai-select-navigator-toggle[\s\S]*?margin-left:\s*auto;/
    );
    assert.doesNotMatch(workspace, /max-width:\s*1440px;/);
    assert.doesNotMatch(workspace, /margin-inline:\s*auto;/);
    assert.match(
        styles,
        /#ai-select-anchor-dock-main\[data-spacious='true'\][\s\S]*?#ai-select-view-navigator[\s\S]*?width:\s*28%;[\s\S]*?#ai-select-view-inspector[\s\S]*?width:\s*34%;/
    );
    assert.match(
        styles,
        /#ai-select-anchor-dock-availability\s*\{[\s\S]*?display:\s*flex;/
    );
});

test('Proposal navigation overlays the image only for a real multi-proposal choice', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    const stepper = styles.match(
        /#ai-select-proposal-stepper\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(stepper, 'missing proposal stepper styles');
    assert.match(stepper, /position:\s*absolute;/);
    assert.match(stepper, /inset:\s*0;/);
    assert.match(stepper, /opacity:\s*0;/);
    assert.match(
        dock,
        /this\.imageSurface\.appendChild\(this\.proposalStepper\.dom\)/
    );
    assert.match(
        dock,
        /this\.imageSurface\.appendChild\(this\.acceptProposalButton\.dom\)/
    );
    assert.doesNotMatch(
        dock,
        /primaryActions\.append\(this\.proposalStepper\)/
    );
    assert.doesNotMatch(
        dock,
        /primaryActions\.append\(this\.acceptProposalButton\)/
    );
    assert.match(
        dock,
        /this\.proposalStepper\.hidden\s*=\s*proposalIds\.length\s*<=\s*1/
    );
});

test('the View Action Bar releases image height when there is no primary action', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /private readonly primaryActions:\s*Container;/);
    assert.match(dock, /this\.primaryActions\.hidden\s*=/);
    assert.match(
        dock,
        /this\.maskActions\.hidden\s*=\s*!mask\.showConfirm\s*&&\s*!mask\.showRetry;/
    );
});

test('a short ultrawide Dock uses the compact two-dimensional Tool Rail', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(
        styles,
        /#ai-select-anchor-dock-main\[data-compact-tools='true'\][\s\S]*?#ai-select-view-work-canvas-row[\s\S]*?align-items:\s*center;/
    );
    assert.match(
        styles,
        /#ai-select-anchor-dock-main\[data-short-tools='true'\][\s\S]*?\.palette-history-group[\s\S]*?flex-direction:\s*row;/
    );
    assert.match(
        styles,
        /#ai-select-anchor-dock-main\[data-short-tools='true'\][\s\S]*?\.palette-tool[\s\S]*?width:\s*38px;[\s\S]*?height:\s*38px;/
    );
});

test('Navigator remains useful with an Anchor before generated Views exist', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /const showGallery = this\.state\.context !== null;/);
    assert.doesNotMatch(
        dock,
        /const showGallery =[\s\S]{0,180}generated\.plannerStatus !== 'idle'/
    );
});

test('Inspector restores the accepted assessment, participation, and Mask hierarchy', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /ai-select-inspector-assessment-group/);
    assert.match(dock, /ai-select-inspector-mask-group/);
    assert.match(dock, /ai-select-inspector-recovery-group/);
});
