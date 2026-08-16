const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const {
    isCurrentTargetDependencyChange
} = require('../.test-dist/src/ai-select/target-dependency-routing.js');
test('render, transform, world-pose, and Delete/Separate routes reach dependency notification', () => {
    const splatSource = readFileSync('src/splat.ts', 'utf8');
    const transformSource = readFileSync(
        'src/splats-transform-handler.ts',
        'utf8'
    );
    const editorSource = readFileSync('src/editor.ts', 'utf8');

    assert.match(
        splatSource,
        /set visible[\s\S]*?aiSelectRenderStateRevision\+\+[\s\S]*?notifyAISelectDependencyChanged\(\)/
    );
    assert.match(
        splatSource,
        /move\([\s\S]*?aiSelectWorldTransformRevision\+\+[\s\S]*?notifyAISelectDependencyChanged\(\)/
    );
    assert.match(
        transformSource,
        /update\(transform: Transform\)[\s\S]*?markAISelectGeometryChanged\(\)/
    );
    const deletedStateRoute = splatSource.match(
        /if \(changedState & State\.deleted\) \{[\s\S]*?await this\.updateSorting\(\);/
    )?.[0];
    assert.ok(deletedStateRoute);
    assert.ok(
        deletedStateRoute.indexOf('notifyAISelectDependencyChanged()') <
            deletedStateRoute.indexOf('await this.updateSorting()'),
        'Delete/Separate membership must notify before asynchronous sorting'
    );
    assert.match(
        editorSource,
        /select\.delete[\s\S]*?new DeleteSelectionOp\(splat\)/
    );
    assert.match(
        editorSource,
        /func === 'separate'[\s\S]*?new DeleteSelectionOp\(splat\)/
    );
});

test('target routing accepts global/current changes and excludes unrelated Splats', () => {
    const target = {};
    const unrelated = {};

    assert.equal(isCurrentTargetDependencyChange(null), false);
    assert.equal(isCurrentTargetDependencyChange(target), true);
    assert.equal(isCurrentTargetDependencyChange(target, target), true);
    assert.equal(isCurrentTargetDependencyChange(target, unrelated), false);
});
