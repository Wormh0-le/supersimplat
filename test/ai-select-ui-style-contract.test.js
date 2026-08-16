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

test('viewport Toolbar is icon-only with two normal-mode split actions', () => {
    const toolbar = readFileSync('src/ui/ai-select-toolbar.ts', 'utf8');
    assert.match(toolbar, /ai-select-toolbar-adjust-anchor/);
    assert.match(toolbar, /ai-select-toolbar-add-view-group/);
    assert.match(toolbar, /ai-select-toolbar-add-current-view/);
    assert.match(toolbar, /ai-select-toolbar-adjust-new-view/);
    assert.match(toolbar, /ai-select-add-view\.svg/);
    assert.match(toolbar, /ai-select-new-pose\.svg/);
    assert.doesNotMatch(toolbar, /ai-select-toolbar-tool/);
    assert.doesNotMatch(toolbar, /ai-select-toolbar-status/);
    assert.doesNotMatch(toolbar, /ai-select-toolbar-more/);
    assert.doesNotMatch(toolbar, /ai-select-toolbar-overflow/);
    assert.doesNotMatch(toolbar, /onRestart|onExit|onRetryPreview/);
    assert.doesNotMatch(toolbar, /[◆＋−∩◉⋯▾]/u);
});

test('viewport Toolbar operations have custom SVG, hit targets and accessible state', () => {
    const toolbar = readFileSync('src/ui/ai-select-toolbar.ts', 'utf8');
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    for (const icon of [
        'anchor-adjust',
        'move',
        'rotate',
        'reset',
        'cancel',
        'overlay',
        'set',
        'add',
        'remove',
        'intersect'
    ]) {
        assert.match(toolbar, new RegExp(`ai-select-${icon}\\.svg`));
    }
    assert.match(styles, /\.pcui-button\s*\{[\s\S]*?min-width:\s*40px;/);
    assert.match(styles, /\.pcui-button\s*\{[\s\S]*?min-height:\s*40px;/);
    assert.match(toolbar, /button\.dom\.title\s*=/);
    assert.match(toolbar, /setAttribute\('aria-label', label\)/);
    assert.match(toolbar, /setAttribute\(\s*'aria-pressed'/);
    assert.match(toolbar, /event\.key === 'ArrowDown'/);
    assert.match(toolbar, /event\.key !== 'Escape'/);
    assert.match(toolbar, /aria-description/);
    assert.match(
        toolbar,
        /if \(!candidatePresentation\.toolbar\.operationsEnabled\)\s*\{\s*return;/
    );
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
        /#ai-select-view-navigator\s*\{[\s\S]*?width:\s*220px;[\s\S]*?min-width:\s*180px;[\s\S]*?max-width:\s*280px;/
    );
    assert.match(
        styles,
        /#ai-select-view-inspector\s*\{[\s\S]*?width:\s*280px;[\s\S]*?min-width:\s*240px;[\s\S]*?max-width:\s*360px;/
    );
    assert.match(styles, /\.ai-select-sidebar-resize-handle\s*\{/);
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
    assert.match(dock, /this\.gallery\.hidden = false;/);
    assert.match(dock, /'ai-select\.views\.no-target'/);
    assert.match(dock, /this\.anchorCard\.anchorPin\.hidden = false;/);
});

test('Inspector restores the accepted assessment, participation, and Mask hierarchy', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /ai-select-inspector-assessment-group/);
    assert.match(dock, /ai-select-inspector-mask-group/);
    assert.match(dock, /ai-select-inspector-technical-group/);
    assert.doesNotMatch(dock, /ai-select-inspector-recovery-group/);
    assert.doesNotMatch(dock, /ai-select-selected-view-retry-render/);
    assert.match(
        dock,
        /selectedViewParticipation\.dom\.setAttribute\([\s\S]{0,80}'aria-pressed'/
    );
    assert.match(dock, /selectedViewParticipation\.on\('click'/);
    assert.match(dock, /participationIcon\.setAttribute\('aria-hidden'/);
    assert.doesNotMatch(dock, /participation\.icon === 'included' \? '✓'/);
    assert.doesNotMatch(dock, /ai-select-view-card-participation/);
    assert.match(
        dock,
        /const editing =\s*maskState\.hasUnconfirmedMaskChanges &&\s*maskState\.editingMask !== null;/
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
        /\.ai-select-view-card\s*\{[\s\S]*?aspect-ratio:\s*16 \/ 9;/
    );
    assert.doesNotMatch(
        styles,
        /\.ai-select-view-card[\s\S]*?&\.selected\s*\{[\s\S]*?order:\s*-1;/
    );
    assert.doesNotMatch(
        styles,
        /#ai-select-view-gallery-cards:not\(\.pcui-hidden\)[\s\S]*?grid-template-columns/
    );
    assert.match(
        styles,
        /#ai-select-selected-view-assessment,[\s\S]*?#ai-select-selected-view-issues[\s\S]*?white-space:\s*pre-line;/
    );
    assert.match(
        styles,
        /#ai-select-anchor-technical-details[\s\S]*?> pre\s*\{[^}]*overflow:\s*visible;/
    );
    assert.doesNotMatch(
        styles,
        /#ai-select-anchor-technical-details[\s\S]*?> pre\s*\{[^}]*max-height:/
    );
});

test('Navigator uses one filter-sort popover and compact prioritized badges', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(dock, /import pinSvg from '\.\/svg\/pin\.svg';/);
    assert.match(dock, /anchorPin\.appendChild\(createSvg\(pinSvg\)\)/);
    assert.match(dock, /ai-select-view-gallery-filter-trigger/);
    assert.match(dock, /role', 'radiogroup'/);
    assert.match(dock, /nextRadioChoice/);
    assert.match(
        dock,
        /button\.dom\.tabIndex = filter === this\.galleryFilter \? 0 : -1;/
    );
    assert.match(
        dock,
        /button\.dom\.tabIndex = sort === this\.gallerySort \? 0 : -1;/
    );
    assert.match(
        dock,
        /window\.addEventListener\(\s*'pointerdown',[\s\S]{0,500}?\s+true\s*\);/
    );
    assert.match(
        styles,
        /#ai-select-view-gallery-filter-popover[\s\S]*?overflow-y:\s*auto;/
    );
    assert.match(dock, /projectNavigatorViews/);
    assert.match(dock, /navigatorBadgePresentation/);
    assert.match(styles, /\.ai-select-view-card-badge/);
    assert.match(styles, /&\.excluded/);
    assert.doesNotMatch(dock, /ai-select-view-gallery-planner-stop/);
    assert.doesNotMatch(dock, /ai-select-view-gallery-planner-more/);
    assert.doesNotMatch(dock, /ai-select-view-gallery-planner-regenerate/);
});

test('compact retry and fit controls use SVG assets with tooltip and accessible names', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(
        dock,
        /import cameraResetSvg from '\.\/svg\/camera-reset\.svg';/
    );
    assert.match(dock, /import redoSvg from '\.\/svg\/redo\.svg';/);
    assert.match(dock, /setSvgButtonIcon/);
    assert.match(dock, /button\.dom\.title = label;/);
    assert.match(dock, /button\.dom\.setAttribute\('aria-label', label\);/);
    assert.match(dock, /setSvgButtonLabel\([\s\S]*?i18n\.onChange/);
    assert.doesNotMatch(dock, /text:\s*'[↻↺]'/);
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
    assert.match(dock, /supersplat\.ai-select\.view-dock-layout/);
    assert.match(dock, /serializeAIViewDockPreferences/);
    assert.match(dock, /bindSidebarResize/);
    assert.match(dock, /navigatorResizeHandle/);
    assert.match(dock, /inspectorResizeHandle/);
    assert.match(
        dock,
        /navigatorResizeHandle\.setAttribute\([\s\S]*?'aria-labelledby'/
    );
    assert.match(
        dock,
        /inspectorResizeHandle\.setAttribute\([\s\S]*?'aria-labelledby'/
    );
    assert.match(dock, /revealButton\.hidden = expanded \|\| !canExpand;/);
    assert.doesNotMatch(
        dock,
        /view\.selected && visible[\s\S]{0,100}scrollIntoView/
    );
});
