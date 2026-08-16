const assert = require('node:assert/strict');
const test = require('node:test');

const {
    viewInspectorPresentation
} = require('../.test-dist/src/ai-select/view-inspector-presentation.js');

const mask = (maskId, digest, status) => ({
    maskId,
    viewId: 'view-1',
    status,
    source: 'single-frame-sam',
    createdFromRgbDigest: 'sha256:rgb',
    artifact: { digest }
});

const maskState = (overrides = {}) => ({
    viewId: 'view-1',
    editingMask: null,
    stableMask: null,
    editingMaskIssue: null,
    promptState: null,
    publishedPromptState: null,
    requestStatus: 'idle',
    hasUnconfirmedPromptChanges: false,
    hasUnconfirmedMaskChanges: false,
    ...overrides
});

test('Inspector presentation has three compact sections and collapsed technical details', () => {
    const stable = mask('mask-stable', 'sha256:same', 'user-confirmed');
    const editing = mask('mask-editing', 'sha256:same', 'draft');
    const result = viewInspectorPresentation({
        viewId: 'view-1',
        rgbDigest: 'sha256:rgb',
        quality: 'user-confirmed',
        participation: 'included',
        participationToggle: 'exclude',
        actionableIssues: [],
        maskState: maskState({ editingMask: editing, stableMask: stable })
    });

    assert.deepEqual(result.sectionOrder, [
        'assessment-and-review',
        'prompt-and-mask',
        'technical-details'
    ]);
    assert.equal(result.assessment.issueReasons.length, 0);
    assert.equal(result.assessment.participation.icon, 'included');
    assert.equal(result.assessment.participation.pressed, true);
    assert.equal(result.promptAndMask.mask.status, 'confirmed');
    assert.equal(result.promptAndMask.mask.published.maskId, 'mask-stable');
    assert.equal(result.promptAndMask.mask.editing, null);
    assert.equal(result.technicalDetails.collapsedByDefault, true);
    assert.equal(
        result.technicalDetails.rows.some(
            (row) =>
                row.label === 'stable-mask-id' && row.value === 'mask-stable'
        ),
        true
    );
});

test('Inspector exposes editing versions and only real actionable issue rows', () => {
    const stable = mask('mask-stable', 'sha256:old', 'user-confirmed');
    const editing = mask('mask-editing', 'sha256:new', 'draft');
    const prompt = {
        revision: 3,
        digest: 'sha256:prompt-new',
        points: [{ polarity: 'include' }, { polarity: 'exclude' }],
        boxes: [{}]
    };
    const result = viewInspectorPresentation({
        viewId: 'view-1',
        quality: 'auto-review',
        participation: 'excluded',
        participationToggle: 'include',
        actionableIssues: ['target-materially-clipped'],
        maskState: maskState({
            editingMask: editing,
            stableMask: stable,
            promptState: prompt,
            publishedPromptState: { ...prompt, revision: 2 },
            hasUnconfirmedPromptChanges: true,
            hasUnconfirmedMaskChanges: true
        })
    });

    assert.deepEqual(result.assessment.issueReasons, [
        'target-materially-clipped'
    ]);
    assert.equal(result.assessment.participation.pressed, false);
    assert.equal(result.promptAndMask.prompt.positivePointCount, 1);
    assert.equal(result.promptAndMask.prompt.negativePointCount, 1);
    assert.equal(result.promptAndMask.prompt.boxCount, 1);
    assert.equal(result.promptAndMask.prompt.published.revision, 2);
    assert.equal(result.promptAndMask.prompt.editing.revision, 3);
    assert.equal(result.promptAndMask.mask.status, 'draft');
    assert.equal(result.promptAndMask.mask.editing.maskId, 'mask-editing');
});

test('Inspector shows the planner-published Prompt before explicit correction starts', () => {
    const result = viewInspectorPresentation({
        viewId: 'view-1',
        quality: 'auto-good',
        participation: 'included',
        participationToggle: 'exclude',
        actionableIssues: [],
        maskState: maskState({
            promptState: {
                revision: 0,
                digest: 'sha256:empty-session-prompt',
                points: [],
                boxes: []
            },
            publishedPromptState: {
                revision: 0,
                digest: 'sha256:empty-session-prompt',
                points: [],
                boxes: []
            }
        }),
        generatedPrompt: {
            artifactDigest: 'sha256:planner-prompt',
            positivePoints: [{ xPx: 1, yPx: 2 }],
            negativePoints: [{ xPx: 3, yPx: 4 }],
            positiveBox: { x0Px: 0, y0Px: 0, x1Px: 5, y1Px: 6 }
        }
    });

    assert.equal(result.promptAndMask.prompt.positivePointCount, 1);
    assert.equal(result.promptAndMask.prompt.negativePointCount, 1);
    assert.equal(result.promptAndMask.prompt.boxCount, 1);
    assert.equal(
        result.promptAndMask.prompt.published.digest,
        'sha256:planner-prompt'
    );
    assert.equal(result.promptAndMask.prompt.editing, null);
});

test('invalid Editing identity fails closed and becomes an actionable issue', () => {
    const result = viewInspectorPresentation({
        viewId: 'view-1',
        quality: 'user-confirmed',
        participation: 'included',
        participationToggle: 'exclude',
        actionableIssues: [],
        maskState: maskState({
            stableMask: mask('mask-stable', 'sha256:stable', 'user-confirmed'),
            editingMaskIssue: 'stable-base-mismatch',
            hasUnconfirmedMaskChanges: true
        })
    });

    assert.equal(result.promptAndMask.mask.status, 'invalid-editing');
    assert.deepEqual(result.assessment.issueReasons, [
        'editing-mask-state-invalid'
    ]);
    assert.equal(result.promptAndMask.hasUnconfirmedChanges, true);
});
