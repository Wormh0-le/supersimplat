const assert = require('node:assert/strict');
const test = require('node:test');

const {
    aiSelectImageInstancePromptSynthesisPolicyVersion,
    isGeneratedViewPromptSynthesisRequest
} = require('../.test-dist/src/ai-select/generated-view-service.js');

test('Route B exposes a versioned prompt-synthesis contract', () => {
    assert.equal(
        aiSelectImageInstancePromptSynthesisPolicyVersion,
        'image-instance-prompt-synthesis/v1'
    );
    assert.equal(typeof isGeneratedViewPromptSynthesisRequest, 'function');
});
