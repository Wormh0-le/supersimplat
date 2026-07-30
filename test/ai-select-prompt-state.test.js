const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createEmptyPromptState,
    createPromptAdapterCapabilities,
    isPromptAdapterCapabilities,
    isPromptState,
    promptToolCapabilityReason,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');

const digest = `sha256:${'a'.repeat(64)}`;

test('PromptState is immutable-by-revision, RGB-bound, and digest-bound', () => {
    const empty = createEmptyPromptState('anchor-view', digest);
    const revised = revisePromptState(empty, {
        points: [
            {
                promptId: 'point-1',
                polarity: 'include',
                xPx: 3,
                yPx: 4
            }
        ]
    });

    assert.equal(empty.revision, 0);
    assert.equal(empty.points.length, 0);
    assert.equal(revised.revision, 1);
    assert.equal(revised.rgbDigest, digest);
    assert.notEqual(revised.digest, empty.digest);
    assert.equal(isPromptState(revised), true);
    assert.equal(
        isPromptState({ ...revised, rgbDigest: `sha256:${'b'.repeat(64)}` }),
        false
    );
    assert.throws(() => revised.points.push({}));
});

test('PromptState validates distinct point, box, mask, and text payloads', () => {
    const state = revisePromptState(
        createEmptyPromptState('anchor-view', digest),
        {
            boxes: [
                {
                    promptId: 'box-1',
                    polarity: 'exclude',
                    x0Px: 1,
                    y0Px: 2,
                    x1Px: 5,
                    y1Px: 6
                }
            ],
            textPrompts: [
                {
                    promptId: 'text-1',
                    polarity: 'include',
                    text: 'chair',
                    locale: 'en'
                }
            ]
        }
    );
    assert.equal(isPromptState(state), true);
    assert.equal(
        isPromptState({
            ...state,
            boxes: [{ ...state.boxes[0], x1Px: 1 }]
        }),
        false
    );
});

test('capability identity is computed from every explicit prompt flag', () => {
    const capability = createPromptAdapterCapabilities({
        points: true,
        negativePoints: true,
        boxes: false,
        negativeBoxes: false,
        maskInput: false,
        negativeMaskConstraints: false,
        text: false,
        negativeText: false,
        multiCandidateOutput: false,
        compilerPolicyVersion: 'point-mask-compiler/v1',
        unsupportedPromptReasons: {
            'positive-box': 'The adapter supports Points only.',
            'negative-box': 'The adapter supports Points only.',
            'positive-mask-constraint': 'The adapter supports Points only.',
            'negative-mask-constraint': 'The adapter supports Points only.',
            'positive-text': 'The adapter supports Points only.',
            'negative-text': 'The adapter supports Points only.'
        }
    });
    assert.equal(isPromptAdapterCapabilities(capability), true);
    assert.equal(
        isPromptAdapterCapabilities({
            ...capability,
            unsupportedPromptReasons: {
                ...capability.unsupportedPromptReasons,
                'positive-box': undefined
            }
        }),
        false
    );
    assert.equal(
        isPromptAdapterCapabilities({ ...capability, boxes: true }),
        false
    );
    assert.equal(
        promptToolCapabilityReason('negative-point', capability),
        null
    );
    assert.match(
        promptToolCapabilityReason('positive-box', capability),
        /Points only/
    );
});

test('visual adapter capability identity binds compiler policy and disabled-family reasons', () => {
    const capabilities = createPromptAdapterCapabilities({
        points: true,
        negativePoints: true,
        boxes: true,
        negativeBoxes: false,
        maskInput: true,
        negativeMaskConstraints: false,
        text: false,
        negativeText: false,
        multiCandidateOutput: true,
        compilerPolicyVersion: 'sam3.1-visual-prompt-compiler/v1',
        unsupportedPromptReasons: {
            'negative-box':
                'The locked SAM 3.1 adapter has no validated negative Box composition.',
            'negative-mask-constraint':
                'The locked SAM 3.1 adapter has no validated negative Mask constraint composition.',
            'positive-text': 'Text prompts are not enabled by this adapter.',
            'negative-text': 'Text prompts are not enabled by this adapter.'
        }
    });

    assert.equal(
        capabilities.compilerPolicyVersion,
        'sam3.1-visual-prompt-compiler/v1'
    );
    assert.match(
        promptToolCapabilityReason('negative-box', capabilities),
        /no validated negative Box composition/
    );

    const changedCompiler = createPromptAdapterCapabilities({
        ...capabilities,
        compilerPolicyVersion: 'sam3.1-visual-prompt-compiler/v2'
    });
    assert.notEqual(
        capabilities.capabilityDigest,
        changedCompiler.capabilityDigest
    );
});
