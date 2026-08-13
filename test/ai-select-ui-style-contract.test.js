const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

test('the bottom action well has a fixed footprint and stable row origin', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const block = styles.match(
        /#ai-select-anchor-dock-primary-actions\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(block, 'missing primary action well styles');
    assert.match(block, /box-sizing:\s*border-box;/);
    assert.match(block, /flex:\s*0 0 96px;/);
    assert.match(block, /height:\s*96px;/);
    assert.match(block, /max-height:\s*96px;/);
    assert.match(block, /justify-content:\s*flex-start;/);
});
