const assert = require('node:assert/strict');
const { readFileSync, readdirSync } = require('node:fs');
const test = require('node:test');

test('the Work Area releases permanent header and action-bar height to the image', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.doesNotMatch(dock, /ai-select-anchor-dock-header/);
    assert.doesNotMatch(dock, /ai-select-view-work-header/);
    assert.doesNotMatch(dock, /ai-select-anchor-dock-primary-actions/);
    assert.doesNotMatch(styles, /#ai-select-anchor-dock-header\s*\{/);
    assert.doesNotMatch(styles, /#ai-select-view-work-header\s*\{/);
    assert.doesNotMatch(styles, /#ai-select-anchor-dock-primary-actions\s*\{/);
    assert.match(
        styles,
        /#ai-select-view-work-canvas-row\s*\{[\s\S]*?flex:\s*1 1 auto;/
    );
});

test('compact canvas state actions overlay instead of reserving a bottom row', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(
        styles,
        /#ai-select-work-canvas-actions\s*\{[\s\S]*?position:\s*absolute;[\s\S]*?bottom:\s*12px;/
    );
});

test('Candidate operations belong to Toolbar while correction stays in the palette', () => {
    const toolbar = readFileSync('src/ui/ai-select-toolbar.ts', 'utf8');
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(toolbar, /ai-select-candidate-operation-group/);
    assert.match(toolbar, /ai-select-toolbar-candidate-\$\{operation\}/);
    assert.doesNotMatch(dock, /ai-select-apply-candidate-/);
    assert.doesNotMatch(dock, /ai-select-fix-candidate/);
    assert.doesNotMatch(dock, /ai-select-back-to-candidate/);
    assert.match(dock, /onContextAction:/);
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
    const workspace = styles.match(
        /#ai-select-anchor-dock-main\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(workspace, 'missing Dock workspace styles');
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
    assert.doesNotMatch(styles, /#ai-select-anchor-dock-availability\s*\{/);
});

test('single-result Mask authoring has no Proposal choice or acceptance UI', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.doesNotMatch(dock, /proposalSelect/);
    assert.doesNotMatch(dock, /proposalStepper/);
    assert.doesNotMatch(dock, /acceptProposalButton/);
    assert.doesNotMatch(dock, /\.ops\.acceptProposal\(/);
});

test('the compact canvas state has navigation only and no recovery Action Bar', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    assert.match(dock, /private readonly canvasStateActions:\s*Container;/);
    assert.match(dock, /this\.canvasStateActions\.hidden\s*=/);
    assert.match(
        dock,
        /this\.canvasStateActions\.append\(this\.selectedViewPrimaryButton\)/
    );
    assert.doesNotMatch(dock, /maskActions|retryMaskButton/);
});

test('obsolete planning and identical-input recovery commands are absent', () => {
    const anchor = readFileSync('src/ai-select/anchor-controller.ts', 'utf8');
    const generated = readFileSync(
        'src/ai-select/generated-view-controller.ts',
        'utf8'
    );
    const gallery = readFileSync(
        'src/ai-select/gallery-presentation.ts',
        'utf8'
    );
    const mask = readFileSync('src/ai-select/view-mask-session.ts', 'utf8');
    const maskController = readFileSync(
        'src/ai-select/mask-controller.ts',
        'utf8'
    );
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');

    assert.doesNotMatch(anchor, /retryAnchorPreview/);
    assert.doesNotMatch(
        generated,
        /retryViewRender|retryViewMask|refreshViewMask|regenerateViewPrompt|stopGeneration|generateMoreViews|regenerateViews/
    );
    assert.doesNotMatch(generated, /regenerate the Prompt/i);
    assert.match(generated, /retryPlanning\(\): void/);
    assert.doesNotMatch(gallery, /retryRender|regeneratePrompt|refreshMask/);
    assert.doesNotMatch(mask, /retryMaskRequest/);
    assert.doesNotMatch(maskController, /retryMaskRequest/);
    assert.doesNotMatch(
        dock,
        /retry-mask|mask\.showRetry|refreshGeneratedViewMask/
    );

    const obsoleteLocaleKeys = [
        'ai-select.retry',
        'ai-select.more',
        'ai-select.mask.retry',
        'ai-select.readiness.action.generate-more',
        'ai-select.views.planner.active',
        'ai-select.views.planner.more',
        'ai-select.views.planner.regenerate',
        'ai-select.views.planner.regenerate-confirm',
        'ai-select.views.planner.stop',
        'ai-select.views.planner.stopped',
        'ai-select.views.refresh-mask',
        'ai-select.views.retry-mask',
        'ai-select.views.retry-prompt',
        'ai-select.views.retry-render'
    ];
    for (const file of readdirSync('static/locales')) {
        const locale = JSON.parse(
            readFileSync(`static/locales/${file}`, 'utf8')
        );
        for (const key of obsoleteLocaleKeys) {
            assert.equal(locale[key], undefined, `${file} retains ${key}`);
        }
    }
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
    assert.match(palette, /readonly contextAction\?:/);
    assert.match(palette, /readonly canRestoreAutoMask:\s*boolean;/);
    assert.match(palette, /readonly onConfirmMask:\s*\(\) => void;/);
    assert.match(palette, /readonly onRestoreAutoMask:\s*\(\) => void;/);
    assert.match(
        palette,
        /historyGroup\.appendChild\(this\.confirmMaskButton\);[\s\S]*?historyGroup\.appendChild\(this\.contextButton\);[\s\S]*?historyGroup\.appendChild\(this\.clearButton\);/
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
    assert.match(dock, /'confirm-anchor': 'ai-select\.anchor\.confirm'/);
    assert.doesNotMatch(dock, /ai-select-anchor-dock-validate/);
    assert.doesNotMatch(dock, /ai-select-anchor-dock-confirm-anchor/);
});

test('Re-Lift is the sole emphasized target action in upper-right Work Area chrome', () => {
    const dock = readFileSync('src/ui/ai-select-anchor-dock.ts', 'utf8');
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(dock, /ai-select-work-area-re-lift/);
    assert.match(dock, /ai-select-re-lift\.svg/);
    assert.match(
        dock,
        /options\.tooltips\.register\([\s\S]*?this\.reLiftButton,/
    );
    assert.match(dock, /aria-description/);
    assert.match(
        styles,
        /#ai-select-work-area-controls\s*\{[\s\S]*?position:\s*absolute;[\s\S]*?top:\s*8px;[\s\S]*?right:\s*8px;/
    );
    assert.match(
        styles,
        /\.ai-select-re-lift-glyph\s*\{[\s\S]*?width:\s*19px;[\s\S]*?height:\s*19px;/
    );
    assert.match(
        styles,
        /#ai-select-work-area-controls[\s\S]*?min-width:\s*40px;[\s\S]*?min-height:\s*40px;/
    );
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
