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

test('Navigator selection owns both image selection and camera navigation', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /setAttribute\('role', 'listbox'\)/);
    assert.match(dock, /setAttribute\('role', 'option'\)/);
    assert.match(dock, /event\.key === 'ArrowDown'/);
    assert.match(dock, /event\.key === 'Enter'/);
    assert.doesNotMatch(dock, /ai-select-proposal-stepper/);
    assert.match(dock, /selectedViewPrimaryAction/);
    assert.match(
        dock,
        /private selectGeneratedView[\s\S]*?this\.generatedViews\.selectView\(viewId\);[\s\S]*?this\.onInspectCamera\(viewId\);/
    );
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

test('AI View Dock caps semantic sidebars and gives surplus width to the Work Area', () => {
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
    assert.doesNotMatch(workspace, /max-width:\s*1440px;/);
    assert.doesNotMatch(workspace, /margin-inline:\s*auto;/);
    assert.match(
        styles,
        /#ai-select-view-navigator\s*\{[\s\S]*?width:\s*clamp\(240px, 14vw, 280px\);/
    );
    assert.match(
        styles,
        /#ai-select-view-inspector\s*\{[\s\S]*?width:\s*clamp\(280px, 16vw, 320px\);/
    );
    assert.doesNotMatch(styles, /data-spacious/);
    assert.match(
        styles,
        /#ai-select-anchor-dock-availability\s*\{[\s\S]*?display:\s*flex;/
    );
});

test('single-result Mask authoring has no Proposal choice or acceptance UI', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.doesNotMatch(dock, /proposalSelect/);
    assert.doesNotMatch(dock, /proposalStepper/);
    assert.doesNotMatch(dock, /acceptProposalButton/);
    assert.doesNotMatch(dock, /\.ops\.acceptProposal\(/);
});

test('the View Action Bar releases image height when there is no primary action', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /private readonly primaryActions:\s*Container;/);
    assert.match(dock, /this\.primaryActions\.hidden\s*=/);
    assert.match(dock, /this\.maskActions\.hidden\s*=\s*!mask\.showRetry;/);
});

test('the draggable snap palette stays inside the image instead of a Tool Rail', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(
        styles,
        /#ai-select-floating-palette\s*\{[\s\S]*?position:\s*absolute;/
    );
    assert.doesNotMatch(dock, /toolRail/);
    assert.match(dock, /this\.imageSurface\.appendChild\(this\.palette\.dom\)/);
});

test('Mask and Generated View confirmation share the compact palette action', () => {
    const palette = readFileSync(
        'src/ui/ai-select-floating-palette.ts',
        'utf8'
    );
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(palette, /readonly canConfirmMask:\s*boolean;/);
    assert.match(palette, /readonly canRestoreAutoMask:\s*boolean;/);
    assert.match(palette, /readonly onConfirmMask:\s*\(\) => void;/);
    assert.match(palette, /readonly onRestoreAutoMask:\s*\(\) => void;/);
    assert.match(
        palette,
        /historyGroup\.appendChild\(this\.confirmMaskButton\);[\s\S]*?historyGroup\.appendChild\(this\.clearButton\);/
    );
    assert.doesNotMatch(dock, /confirmMaskButton/);
    assert.doesNotMatch(dock, /restoreAutoButton/);
    assert.match(
        dock,
        /onConfirmMask:[\s\S]{0,120}this\.runPaletteConfirmAction\(/
    );
    assert.match(
        dock,
        /private runPaletteConfirmAction[\s\S]*?this\.confirmCurrentMask\([\s\S]*?this\.confirmGeneratedReview\(/
    );
    assert.doesNotMatch(dock, /case 'confirm-as-is'/);
    assert.match(dock, /onRestoreAutoMask:/);
});

test('confirming the Anchor Mask continues through Anchor confirmation', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(
        dock,
        /private async confirmCurrentMask[\s\S]*?authoring\.ops\.confirmEditingMask\(\);[\s\S]*?await onConfirmAnchor\(\);/
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
    assert.doesNotMatch(
        dock,
        /recoveryGroup\.append\(this\.restoreAutoButton\)/
    );
    assert.doesNotMatch(dock, /ai-select-anchor-dock-adjust-anchor/);
    assert.doesNotMatch(dock, /ai-select-selected-view-inspect-camera/);
});

test('Navigator controls do not overlap cards and Inspector status can wrap', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(
        styles,
        /#ai-select-view-gallery-filters\s*\{[\s\S]*?flex:\s*0 0 auto;/
    );
    assert.match(
        styles,
        /#ai-select-view-gallery-cards\s*\{[\s\S]*?flex:\s*1 1 0;/
    );
    assert.match(
        styles,
        /\.ai-select-view-card\s*\{[\s\S]*?min-height:\s*74px;/
    );
    assert.doesNotMatch(
        styles,
        /#ai-select-view-gallery-cards:not\(\.pcui-hidden\)[\s\S]*?grid-template-columns/
    );
    assert.match(
        styles,
        /#ai-select-selected-view-assessment,[\s\S]*?#ai-select-selected-view-participation[\s\S]*?white-space:\s*pre-line;/
    );
});

test('Dock sidebar controls stay adjacent to the sidebar they control', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /import arrowSvg from '\.\/svg\/arrow\.svg';/);
    assert.match(dock, /import collapseSvg from '\.\/svg\/collapse\.svg';/);
    assert.match(dock, /aria-expanded/);
    assert.match(dock, /navigatorHeader\.append\(navigatorCollapse\)/);
    assert.match(dock, /inspectorHeader\.append\(inspectorCollapse\)/);
    assert.match(dock, /workArea\.append\(navigatorReveal\)/);
    assert.match(dock, /workArea\.append\(inspectorReveal\)/);
    assert.doesNotMatch(dock, /header\.append\(navigator/);
    assert.doesNotMatch(dock, /header\.append\(inspector/);
    assert.match(dock, /icon\.setAttribute\('aria-hidden', 'true'\)/);
    assert.match(dock, /'ai-select\.dock\.hide-navigator'/);
    assert.match(dock, /'ai-select\.dock\.show-inspector'/);
});
