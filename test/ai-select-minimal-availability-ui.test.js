const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');

const repositoryRoot = join(__dirname, '..');

test('AI Select availability stays status-only without manual recovery controls', () => {
    const dock = readFileSync(
        join(repositoryRoot, 'src/ui/ai-select-anchor-dock.ts'),
        'utf8'
    );
    const composition = readFileSync(
        join(repositoryRoot, 'src/main.ts'),
        'utf8'
    );

    for (const forbidden of [
        'ai-select-anchor-dock-retry',
        'ai-select-anchor-dock-reconnect',
        'ai-select-anchor-dock-settings'
    ]) {
        assert.equal(
            dock.includes(`'${forbidden}'`) ||
                composition.includes(`'${forbidden}'`),
            false,
            `ordinary AI Select UI must not expose ${forbidden}`
        );
    }
    for (const forbidden of ['onReconnect', 'onOpenSettings']) {
        assert.equal(
            dock.includes(forbidden) || composition.includes(forbidden),
            false,
            `ordinary AI Select composition must not expose ${forbidden}`
        );
    }
});
