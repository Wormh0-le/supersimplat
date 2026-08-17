const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createEmptyPromptState,
    createPromptAdapterCapabilities,
    isPromptAdapterCapabilities,
    isPromptState,
    promptStateHasConstraints,
    promptToolCapabilityReason,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');

const digest = `sha256:${'a'.repeat(64)}`;

const sam3ImageCapabilityInput = {
    positivePoints: true,
    negativePoints: true,
    positiveInstanceBox: true,
    previousLogitsRefinement: true,
    singlePointMultimask: true,
    compilerPolicyVersion: 'sam3-image-instance-compiler/v1'
};

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

    assert.equal(empty.schemaVersion, 2);
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

test('PromptState v2 validates point and positive instance box payloads', () => {
    const state = revisePromptState(
        createEmptyPromptState('anchor-view', digest),
        {
            boxes: [
                {
                    promptId: 'box-1',
                    polarity: 'include',
                    x0Px: 1,
                    y0Px: 2,
                    x1Px: 5,
                    y1Px: 6
                }
            ]
        }
    );
    assert.equal(isPromptState(state), true);
    assert.equal(promptStateHasConstraints(state), true);
    // Degenerate box area fails closed.
    assert.equal(
        isPromptState({
            ...state,
            boxes: [{ ...state.boxes[0], x1Px: 1 }]
        }),
        false
    );
    // Negative Box polarity is not part of the v2 instance contract.
    assert.equal(
        isPromptState({
            ...state,
            boxes: [{ ...state.boxes[0], polarity: 'exclude' }]
        }),
        false
    );
});

test('adding a Box replaces any existing Box', () => {
    const first = revisePromptState(
        createEmptyPromptState('anchor-view', digest),
        {
            boxes: [
                {
                    promptId: 'box-1',
                    polarity: 'include',
                    x0Px: 1,
                    y0Px: 1,
                    x1Px: 4,
                    y1Px: 4
                }
            ]
        }
    );
    const second = revisePromptState(first, {
        boxes: [
            {
                promptId: 'box-2',
                polarity: 'include',
                x0Px: 2,
                y0Px: 2,
                x1Px: 8,
                y1Px: 8
            }
        ]
    });
    assert.equal(second.boxes.length, 1);
    assert.equal(second.boxes[0].promptId, 'box-2');
    assert.equal(isPromptState(second), true);
    // A second box smuggled past the constructor fails validation.
    assert.equal(
        isPromptState({
            ...second,
            boxes: [...second.boxes, { ...second.boxes[0], promptId: 'box-3' }]
        }),
        false
    );
});

test('v1 PromptState artifacts fail closed', () => {
    const v2 = revisePromptState(
        createEmptyPromptState('anchor-view', digest),
        {
            points: [
                { promptId: 'point-1', polarity: 'include', xPx: 1, yPx: 1 }
            ]
        }
    );
    // Removed v1 fields are rejected by exact-key validation.
    assert.equal(
        isPromptState({ ...v2, maskConstraints: [], textPrompts: [] }),
        false
    );
    // The v1 schema version is rejected even with v2-shaped keys.
    assert.equal(isPromptState({ ...v2, schemaVersion: 1 }), false);
    // A Mask constraint payload has no place in the v2 schema.
    assert.equal(
        isPromptState({
            ...v2,
            maskConstraints: [
                {
                    promptId: 'brush-1',
                    polarity: 'include',
                    artifact: {
                        encoding: 'bitset-lsb-v1',
                        width: 2,
                        height: 2,
                        data: 'AA==',
                        digest
                    }
                }
            ]
        }),
        false
    );
});

test('capability identity binds only current flags and compiler policy version', () => {
    const capability = createPromptAdapterCapabilities(
        sam3ImageCapabilityInput
    );
    assert.equal(isPromptAdapterCapabilities(capability), true);
    assert.match(capability.capabilityDigest, /^sha256:[a-f0-9]{64}$/);
    // The digest is stable for identical input.
    assert.equal(
        createPromptAdapterCapabilities(sam3ImageCapabilityInput)
            .capabilityDigest,
        capability.capabilityDigest
    );
    // Removed Prompt families cannot re-enter the capability record even as
    // false placeholders.
    assert.equal(
        isPromptAdapterCapabilities({ ...capability, negativeBox: false }),
        false
    );
    // A compiler policy change rotates the digest.
    const changedCompiler = createPromptAdapterCapabilities({
        ...sam3ImageCapabilityInput,
        compilerPolicyVersion: 'sam3-image-instance-compiler/v2'
    });
    assert.notEqual(
        capability.capabilityDigest,
        changedCompiler.capabilityDigest
    );
    // The removed v1 record shape (extra keys) fails closed.
    assert.equal(
        isPromptAdapterCapabilities({
            ...capability,
            unsupportedPromptReasons: {}
        }),
        false
    );
    // Missing keys fail closed.
    const { positivePoints: _positivePoints, ...missingPositivePoints } =
        capability;
    assert.equal(isPromptAdapterCapabilities(missingPositivePoints), false);
});

test('prompt tool support follows the advertised flags', () => {
    const capability = createPromptAdapterCapabilities(
        sam3ImageCapabilityInput
    );
    assert.equal(
        promptToolCapabilityReason('positive-point', capability),
        null
    );
    assert.equal(
        promptToolCapabilityReason('negative-point', capability),
        null
    );
    assert.equal(promptToolCapabilityReason('positive-box', capability), null);

    const pointsOnly = createPromptAdapterCapabilities({
        ...sam3ImageCapabilityInput,
        positiveInstanceBox: false
    });
    assert.match(
        promptToolCapabilityReason('positive-box', pointsOnly),
        /does not support positive-box/
    );
});
