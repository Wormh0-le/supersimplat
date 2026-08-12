// 04C cross-runtime wire-shape audit — TypeScript side.
// Part A (mode=emit): writes /tmp/04c_ts_payload.json with editor-produced
//   PromptState v2 / capability record / PreviousPredictionLogitsRef.
// Part B (mode=validate): validates Companion-produced fixtures from
//   /tmp/04c_py_fixtures.json with the real editor validators.
const assert = require('node:assert/strict');
const fs = require('node:fs');

const ROOT = '/home/ubuntu/orca/workspaces/supersimplat/houndshark';
const promptStateModule = require(
    `${ROOT}/.test-dist/src/ai-select/prompt-state.js`
);
const logitsRefModule = require(
    `${ROOT}/.test-dist/src/ai-select/previous-logits-ref.js`
);
const maskService = require(`${ROOT}/.test-dist/src/ai-select/mask-service.js`);
const maskProposal = require(
    `${ROOT}/.test-dist/src/ai-select/mask-proposal.js`
);
const { sha256Digest } = require(
    `${ROOT}/.test-dist/src/scene-snapshot-binary.js`
);

const CAPABILITY_PAYLOAD = {
    positivePoints: true,
    negativePoints: true,
    positiveInstanceBox: true,
    previousLogitsRefinement: true,
    singlePointMultimask: true,
    negativeBox: false,
    promptBrush: false,
    maskConstraints: false,
    text: false,
    compilerPolicyVersion: 'sam3-image-instance-compiler/v1'
};

const mode = process.argv[2];

if (mode === 'emit') {
    const rgbPng = Buffer.from('\x89PNG\r\n\x1a\nanchor-rgb-frame', 'binary');
    const rgbDigest = sha256Digest(rgbPng);
    const capabilities =
        promptStateModule.createPromptAdapterCapabilities(CAPABILITY_PAYLOAD);
    const empty = promptStateModule.createEmptyPromptState(
        'anchor-view',
        rgbDigest
    );
    const pointState = promptStateModule.revisePromptState(empty, {
        points: [{ promptId: 'prompt-1', polarity: 'include', xPx: 1, yPx: 0 }]
    });
    const boxState = promptStateModule.revisePromptState(empty, {
        points: [{ promptId: 'prompt-1', polarity: 'include', xPx: 1, yPx: 0 }],
        boxes: [
            {
                promptId: 'prompt-2',
                polarity: 'include',
                x0Px: 0,
                y0Px: 0,
                x1Px: 2,
                y1Px: 2
            }
        ]
    });
    const zeroLogitsDigest = sha256Digest(Buffer.alloc(288 * 288 * 4));
    const refPayload = {
        schemaVersion: 1,
        companionInstanceId: 'instance-A',
        stateId: 'logits-ts-1',
        targetContextId: 'context-1',
        viewId: 'anchor-view',
        rgbDigest,
        sourceInferenceAttemptId: 'attempt-1',
        sourceCandidateId: 'proposal-0',
        adapterRuntimeDigest: `sha256:${'ab'.repeat(32)}`,
        shape: [1, 288, 288],
        dtype: 'float32',
        dataDigest: zeroLogitsDigest
    };
    const ref = {
        ...refPayload,
        refDigest: logitsRefModule.previousPredictionLogitsRefDigest(refPayload)
    };
    assert.ok(logitsRefModule.isPreviousPredictionLogitsRef(ref));
    fs.writeFileSync(
        '/tmp/04c_ts_payload.json',
        JSON.stringify({
            capabilities,
            pointState,
            boxState,
            ref,
            rgb: {
                pngBase64: rgbPng.toString('base64'),
                digest: rgbDigest,
                width: 2,
                height: 2
            }
        })
    );
    console.log('TS payload written:', rgbDigest);
} else if (mode === 'validate') {
    const fixtures = JSON.parse(
        fs.readFileSync('/tmp/04c_py_fixtures.json', 'utf8')
    );
    // Capability digest parity.
    const pythonCaps = fixtures.capabilities;
    const { capabilityDigest: pythonDigest, ...pythonPayload } = pythonCaps;
    const rebuilt =
        promptStateModule.createPromptAdapterCapabilities(pythonPayload);
    assert.equal(rebuilt.capabilityDigest, pythonDigest);
    assert.ok(promptStateModule.isPromptAdapterCapabilities(pythonCaps));

    for (const [name, pair] of Object.entries(fixtures.exchanges)) {
        // The wire body flattens target.splatId to targetSplatId; rebuild the
        // editor-internal request shape the validators operate on.
        const editorRequest = {
            ...pair.request,
            target: { splatId: pair.request.targetSplatId }
        };
        assert.ok(
            maskService.isAIViewMaskRequest(editorRequest),
            `${name}: request must pass isAIViewMaskRequest`
        );
        assert.ok(
            maskService.isMaskResultResponse(pair.response),
            `${name}: response must pass isMaskResultResponse`
        );
        assert.ok(
            maskService.maskResponseMatchesRequest(
                pair.response,
                editorRequest
            ),
            `${name}: response must echo the request identity`
        );
        assert.ok(
            maskProposal.isAutoMaskProposalSet(pair.response.proposalSet),
            `${name}: proposal set must validate`
        );
        for (const proposal of pair.response.proposalSet.proposals) {
            if (proposal.logitsRef !== undefined) {
                assert.ok(
                    logitsRefModule.isPreviousPredictionLogitsRef(
                        proposal.logitsRef
                    ),
                    `${name}: proposal logitsRef must validate (refDigest recompute)`
                );
            }
        }
    }
    assert.equal(
        fixtures.exchanges.refinement.response.proposalSet.diagnostics
            ?.refinementFallback,
        undefined,
        'refinement with a valid ref must not fall back'
    );
    assert.equal(
        fixtures.exchanges.fallback.response.proposalSet.diagnostics
            ?.refinementFallback,
        true,
        'unknown-stateId ref must fall back with a diagnostic'
    );
    console.log(
        'Cross-runtime validation passed for',
        Object.keys(fixtures.exchanges).join(', ')
    );
} else {
    throw new Error('usage: node 04c-cross-check-node.cjs emit|validate');
}
