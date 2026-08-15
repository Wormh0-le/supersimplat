const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

test('the bottom action well grows within a bounded scrollable footprint', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    const block = styles.match(
        /#ai-select-anchor-dock-primary-actions\s*\{(?<body>[\s\S]*?)\n\}/
    )?.groups?.body;
    assert.ok(block, 'missing primary action well styles');
    assert.match(block, /box-sizing:\s*border-box;/);
    assert.match(block, /flex:\s*0 1 auto;/);
    assert.match(block, /min-height:\s*46px;/);
    assert.match(block, /max-height:\s*min\(40%, 176px\);/);
    assert.doesNotMatch(block, /height:\s*96px;/);
    assert.match(block, /justify-content:\s*flex-start;/);
    assert.match(block, /overflow-y:\s*auto;/);
    assert.match(block, /overflow-x:\s*hidden;/);
});

test('bottom action groups use responsive button grids', () => {
    const styles = readFileSync('src/ui/scss/ai-select.scss', 'utf8');
    assert.match(
        styles,
        /#ai-select-anchor-dock-primary-actions[\s\S]*?> \.pcui-container[\s\S]*?grid-template-columns:\s*repeat\(auto-fit, minmax\(120px, 1fr\)\);/
    );
});
