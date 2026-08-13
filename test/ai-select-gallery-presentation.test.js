const assert = require('node:assert/strict');
const test = require('node:test');

const {
    filterGalleryViews,
    galleryCardPresentation,
    galleryViewRole,
    orderGalleryViews
} = require('../.test-dist/src/ai-select/gallery-presentation.js');
const {
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');

const rgbDigest = `sha256:${'a'.repeat(64)}`;
const stableMaskDigest = `sha256:${'b'.repeat(64)}`;

const assessment = (overrides = {}) => ({
    status: 'good',
    reasons: [],
    actionableReasons: [],
    policyVersion: aiSelectViewAssessmentPolicyVersion,
    inputIdentity: {
        rgbDigest,
        stableMaskDigest,
        assessmentPolicyVersion: aiSelectViewAssessmentPolicyVersion
    },
    diagnostics: {
        framePixels: 3072,
        foregroundPixels: 24,
        boundaryPixels: 0,
        boundaryContactRatio: 0,
        connectedComponents: 1,
        largestComponentRatio: 1,
        promptPointCount: 2,
        promptViolationCount: 0,
        boxSpillPixels: null,
        boxSpillRatio: null
    },
    ...overrides
});

const view = (overrides = {}) => ({
    viewId: 'view-1',
    source: 'auto-generated',
    cameraBinding: {},
    renderStatus: 'ready',
    rgbDigest,
    participation: 'included',
    promptStatus: 'ready',
    maskStatus: 'ready',
    maskQuality: 'auto-good',
    assessment: assessment(),
    evidenceStatus: 'not-requested',
    selected: false,
    ...overrides
});

const statusKeys = (presentation) =>
    presentation.lines
        .filter((line) => line.kind === 'status')
        .map((line) => line.key);
const detailTexts = (presentation) =>
    presentation.lines
        .filter((line) => line.kind === 'detail')
        .map((line) => line.text);

test('Render, Prompt, Mask, Review, Participation and Evidence stay separate', () => {
    const presentation = galleryCardPresentation(view(), 1);
    assert.deepEqual(statusKeys(presentation), [
        'ai-select.views.status.ready',
        'ai-select.views.status.prompt-ready',
        'ai-select.views.status.mask-ready',
        'ai-select.views.status.evidence-not-requested',
        'ai-select.review.quality.auto-good',
        'ai-select.participation.included'
    ]);
    assert.equal(presentation.role, 'generated');
    assert.equal(presentation.titleOrdinal, 1);
});

test('Prompt Ready is distinct from Prompt not started', () => {
    const ready = galleryCardPresentation(view({ promptStatus: 'ready' }), 1);
    const none = galleryCardPresentation(
        view({
            promptStatus: 'none',
            maskStatus: 'none',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.ok(
        statusKeys(ready).includes('ai-select.views.status.prompt-ready')
    );
    assert.ok(statusKeys(none).includes('ai-select.views.status.prompt-none'));
});

test('RGB Ready survives Mask pending and technical Mask failure', () => {
    const pending = galleryCardPresentation(
        view({
            promptStatus: 'ready',
            maskStatus: 'generating',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(statusKeys(pending)[0], 'ai-select.views.status.ready');
    assert.ok(
        statusKeys(pending).includes('ai-select.views.status.mask-generating')
    );

    const failed = galleryCardPresentation(
        view({
            maskStatus: 'failed',
            maskErrorMessage: 'transport 500',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(statusKeys(failed)[0], 'ai-select.views.status.ready');
    assert.ok(
        statusKeys(failed).includes('ai-select.views.status.mask-failed')
    );
    // A technical failure keeps its raw message as a detail, never a status.
    assert.deepEqual(detailTexts(failed), ['transport 500']);
    assert.ok(
        statusKeys(failed).includes('ai-select.review.mask-failure-options')
    );
});

test('semantic unavailable is not presented as technical inference failure', () => {
    const unavailable = galleryCardPresentation(
        view({
            maskStatus: 'unavailable',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.ok(
        statusKeys(unavailable).includes(
            'ai-select.views.status.mask-unavailable'
        )
    );
    assert.ok(
        !statusKeys(unavailable).includes('ai-select.views.status.mask-failed')
    );
    assert.ok(
        !statusKeys(unavailable).includes(
            'ai-select.review.mask-failure-options'
        )
    );
    assert.deepEqual(detailTexts(unavailable), []);
});

test('Prompt synthesis states are localized statuses; raw strings stay details', () => {
    const synthesizing = galleryCardPresentation(
        view({
            promptStatus: 'synthesizing',
            maskStatus: 'none',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.ok(
        statusKeys(synthesizing).includes(
            'ai-select.views.status.prompt-synthesizing'
        )
    );

    const limited = galleryCardPresentation(
        view({
            promptStatus: 'limited',
            promptDiagnostics: ['only one projected point'],
            maskStatus: 'unavailable',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.ok(
        statusKeys(limited).includes('ai-select.views.status.prompt-limited')
    );
    assert.deepEqual(detailTexts(limited), ['only one projected point']);

    const failed = galleryCardPresentation(
        view({
            promptStatus: 'failed',
            promptErrorMessage: 'geometry unavailable',
            maskStatus: 'none',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.ok(
        statusKeys(failed).includes('ai-select.views.status.prompt-failed')
    );
    assert.deepEqual(detailTexts(failed), ['geometry unavailable']);
    assert.ok(
        !statusKeys(failed).some((key) => key.includes('geometry unavailable'))
    );
});

test('Evidence status has a distinct localized line for every status', () => {
    for (const evidenceStatus of [
        'not-requested',
        'pending',
        'ready',
        'stale',
        'failed'
    ]) {
        const presentation = galleryCardPresentation(
            view({ evidenceStatus }),
            1
        );
        assert.ok(
            statusKeys(presentation).includes(
                `ai-select.views.status.evidence-${evidenceStatus}`
            ),
            `missing evidence line for ${evidenceStatus}`
        );
    }
});

test('Review Reasons map to corrective actions and stay evidence-backed', () => {
    const presentation = galleryCardPresentation(
        view({
            maskQuality: 'auto-review',
            participation: 'excluded',
            assessment: assessment({
                status: 'review',
                primaryReason: 'target-materially-clipped',
                reasons: ['target-materially-clipped'],
                actionableReasons: ['target-materially-clipped'],
                diagnostics: {
                    framePixels: 3072,
                    foregroundPixels: 24,
                    boundaryPixels: 15,
                    boundaryContactRatio: 15 / 64,
                    connectedComponents: 1,
                    largestComponentRatio: 1,
                    promptPointCount: 2,
                    promptViolationCount: 0,
                    boxSpillPixels: null,
                    boxSpillRatio: null
                }
            })
        }),
        1
    );
    const keys = statusKeys(presentation);
    assert.ok(
        keys.includes('ai-select.review.reason.target-materially-clipped')
    );
    assert.ok(keys.includes('ai-select.review.action.inspect-view'));
    assert.ok(keys.includes('ai-select.review.action.add-view'));
    assert.ok(keys.includes('ai-select.review.correction-options'));
});

test('role and Participation remain independent', () => {
    assert.equal(galleryViewRole('auto-generated'), 'generated');
    assert.equal(galleryViewRole('replacement'), 'generated');
    assert.equal(galleryViewRole('user-added'), 'user-added');
    const userAdded = galleryCardPresentation(
        view({ source: 'user-added', participation: 'excluded' }),
        2
    );
    assert.equal(userAdded.role, 'user-added');
    assert.equal(userAdded.titleOrdinal, 2);
    assert.ok(
        statusKeys(userAdded).includes('ai-select.participation.excluded')
    );
});

test('stable order: generated Views in creation order, then user-added Views', () => {
    const views = [
        view({ viewId: 'user-1', source: 'user-added' }),
        view({ viewId: 'gen-1' }),
        view({ viewId: 'gen-2', source: 'replacement' }),
        view({ viewId: 'user-2', source: 'user-added' }),
        view({ viewId: 'gen-3' })
    ];
    assert.deepEqual(
        orderGalleryViews(views).map((entry) => entry.viewId),
        ['gen-1', 'gen-2', 'gen-3', 'user-1', 'user-2']
    );
});

test('appending later Views never reorders prior completed Views', () => {
    const first = [view({ viewId: 'gen-1' }), view({ viewId: 'gen-2' })];
    const appended = [...first, view({ viewId: 'gen-3' })];
    assert.deepEqual(
        orderGalleryViews(appended).map((entry) => entry.viewId),
        ['gen-1', 'gen-2', 'gen-3']
    );
});

test('filters project presentation only and never mutate formal state', () => {
    const included = view({ viewId: 'gen-1', participation: 'included' });
    const excluded = view({ viewId: 'gen-2', participation: 'excluded' });
    const review = view({
        viewId: 'gen-3',
        participation: 'excluded',
        maskQuality: 'auto-review',
        assessment: assessment({
            status: 'review',
            primaryReason: 'severely-fragmented',
            reasons: ['severely-fragmented'],
            actionableReasons: ['severely-fragmented'],
            diagnostics: {
                framePixels: 3072,
                foregroundPixels: 200,
                boundaryPixels: 0,
                boundaryContactRatio: 0,
                connectedComponents: 3,
                largestComponentRatio: 0.5,
                promptPointCount: 2,
                promptViolationCount: 0,
                boxSpillPixels: null,
                boxSpillRatio: null
            }
        })
    });
    const confirmedReview = view({
        viewId: 'gen-4',
        participation: 'included',
        maskQuality: 'user-confirmed',
        assessment: review.assessment
    });
    const views = Object.freeze([included, excluded, review, confirmedReview]);
    const ids = (entries) => entries.map((entry) => entry.viewId);
    assert.deepEqual(ids(filterGalleryViews(views, 'all')), [
        'gen-1',
        'gen-2',
        'gen-3',
        'gen-4'
    ]);
    assert.deepEqual(ids(filterGalleryViews(views, 'included')), [
        'gen-1',
        'gen-4'
    ]);
    assert.deepEqual(ids(filterGalleryViews(views, 'excluded')), [
        'gen-2',
        'gen-3'
    ]);
    // User Confirmed authority settles the Review; it is no longer pending.
    assert.deepEqual(ids(filterGalleryViews(views, 'needs-review')), ['gen-3']);
    assert.equal(views.length, 4);
    assert.equal(views[0], included);
});

test('card actions carry no obsolete backend, tracker or prompt-family surface', () => {
    const presentation = galleryCardPresentation(view(), 1);
    assert.deepEqual(Object.keys(presentation.actions).sort(), [
        'confirmAsIs',
        'excludeView',
        'inspectCamera',
        'participationToggle',
        'refreshMask',
        'regeneratePrompt',
        'retryRender'
    ]);
    for (const key of statusKeys(presentation)) {
        assert.match(key, /^ai-select\.(views|review|participation)\./);
        assert.ok(!key.includes('route'));
        assert.ok(!key.includes('fallback'));
        assert.ok(!key.includes('tracker'));
        assert.ok(!key.includes('proposal'));
        assert.ok(!key.includes('brush-prompt'));
        assert.ok(!key.includes('negative-box'));
    }
    // The Anchor candidate choice is not duplicated into ordinary cards.
    assert.ok(!('proposalSelect' in presentation));
    assert.ok(!('proposalDecision' in presentation));
});

test('action visibility follows Render / Prompt / Mask / Review state', () => {
    const ready = galleryCardPresentation(view(), 1);
    // Successful Views are corrected on the selected image surface. Routine
    // Prompt/Mask reruns are not duplicated on every Gallery card.
    assert.equal(ready.actions.regeneratePrompt, false);
    assert.equal(ready.actions.refreshMask, false);

    const renderFailed = galleryCardPresentation(
        view({ renderStatus: 'failed', renderErrorMessage: 'oom' }),
        1
    );
    assert.equal(renderFailed.actions.retryRender, true);
    assert.equal(renderFailed.actions.regeneratePrompt, false);
    assert.equal(renderFailed.actions.refreshMask, false);
    assert.deepEqual(detailTexts(renderFailed), ['oom']);

    const promptFailed = galleryCardPresentation(
        view({
            promptStatus: 'failed',
            maskStatus: 'none',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(promptFailed.actions.regeneratePrompt, true);
    assert.equal(promptFailed.actions.refreshMask, false);

    const maskFailed = galleryCardPresentation(
        view({
            maskStatus: 'failed',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(maskFailed.actions.regeneratePrompt, false);
    assert.equal(maskFailed.actions.refreshMask, true);

    const maskUnavailable = galleryCardPresentation(
        view({
            maskStatus: 'unavailable',
            maskQuality: 'none',
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(maskUnavailable.actions.regeneratePrompt, false);
    assert.equal(maskUnavailable.actions.refreshMask, true);

    const reviewPending = galleryCardPresentation(
        view({
            maskQuality: 'auto-review',
            participation: 'excluded',
            assessment: assessment({
                status: 'review',
                primaryReason: 'prompt-inconsistent',
                reasons: ['prompt-inconsistent'],
                actionableReasons: ['prompt-inconsistent'],
                diagnostics: {
                    framePixels: 3072,
                    foregroundPixels: 24,
                    boundaryPixels: 0,
                    boundaryContactRatio: 0,
                    connectedComponents: 1,
                    largestComponentRatio: 1,
                    promptPointCount: 2,
                    promptViolationCount: 1,
                    boxSpillPixels: null,
                    boxSpillRatio: null
                }
            })
        }),
        1
    );
    assert.equal(reviewPending.actions.confirmAsIs, true);
    assert.equal(reviewPending.actions.participationToggle, null);

    const autoGood = galleryCardPresentation(view(), 1);
    assert.equal(autoGood.actions.confirmAsIs, false);
    assert.equal(autoGood.actions.participationToggle, 'exclude');
    assert.equal(autoGood.actions.inspectCamera, true);

    const userConfirmed = galleryCardPresentation(
        view({ maskQuality: 'user-confirmed', participation: 'excluded' }),
        1
    );
    assert.equal(userConfirmed.actions.participationToggle, 'include');
});

test('presentation output is frozen and selection projects through', () => {
    const presentation = galleryCardPresentation(view({ selected: true }), 1);
    assert.equal(presentation.selected, true);
    assert.ok(Object.isFrozen(presentation));
    assert.ok(Object.isFrozen(presentation.lines));
    assert.ok(Object.isFrozen(presentation.actions));
});

test('card selection owns Mask editing; a user View without a Mask offers only Exclude', () => {
    const noMask = galleryCardPresentation(
        view({
            viewId: 'user-view-1',
            source: 'user-added',
            promptStatus: 'none',
            maskStatus: 'none',
            maskQuality: 'none',
            stableMaskId: undefined,
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(noMask.role, 'user-added');
    assert.equal(noMask.actions.excludeView, true);
    assert.equal(noMask.actions.participationToggle, null);
    assert.equal(noMask.actions.regeneratePrompt, false);
    assert.equal(noMask.actions.refreshMask, false);
    assert.equal(noMask.actions.confirmAsIs, false);

    // A User Confirmed Stable Mask adds the Participation toggle. Selecting
    // the card, rather than a duplicate action, exposes later correction.
    const confirmed = galleryCardPresentation(
        view({
            viewId: 'user-view-2',
            source: 'user-added',
            promptStatus: 'none',
            maskStatus: 'ready',
            maskQuality: 'user-confirmed',
            stableMaskId: 'mask-1',
            assessment: undefined,
            participation: 'included'
        }),
        2
    );
    assert.equal(confirmed.actions.excludeView, false);
    assert.equal(confirmed.actions.participationToggle, 'exclude');

    // Generated Views are likewise selected to enter manual correction.
    const generated = galleryCardPresentation(view(), 3);
    assert.equal(generated.actions.excludeView, false);
});

test('a render-failed user-added View offers Retry and Exclude but no Mask choices', () => {
    const failed = galleryCardPresentation(
        view({
            viewId: 'user-view-3',
            source: 'user-added',
            renderStatus: 'failed',
            rgbDigest: undefined,
            promptStatus: 'none',
            maskStatus: 'none',
            maskQuality: 'none',
            stableMaskId: undefined,
            assessment: undefined,
            participation: 'excluded'
        }),
        1
    );
    assert.equal(failed.actions.retryRender, true);
    assert.equal(failed.actions.excludeView, true);
});
