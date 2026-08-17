const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = (relativePath) =>
    fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');

test('readiness cannot render the Dock before suspension elements initialize', () => {
    const dock = source('src/ui/ai-select-anchor-dock.ts');
    const suspensionInitialization = dock.indexOf(
        'this.suspendedSurface = new Container'
    );
    const readinessSubscription = dock.indexOf(
        'options.readiness.subscribe((readinessState)'
    );

    assert.ok(suspensionInitialization >= 0);
    assert.ok(readinessSubscription >= 0);
    assert.ok(
        suspensionInitialization < readinessSubscription,
        'the eager readiness subscription must follow render-owned DOM initialization'
    );
});

test('production transport and Companion server expose no legacy session routes', () => {
    const browserTransport = source('src/selection-service-fetch-adapter.ts');
    const companionServer = source(
        'selection-service-companion/src/selection_service_companion/server.py'
    );

    for (const retiredRoute of [
        '/object-selection-sessions',
        '/frame-sets/',
        '/ai-select/generated-view-masks'
    ]) {
        assert.doesNotMatch(browserTransport, new RegExp(retiredRoute));
        assert.doesNotMatch(companionServer, new RegExp(retiredRoute));
    }
});

test('browser product sources no longer contain ObjectSelectionSession', () => {
    for (const relativePath of [
        'src/main.ts',
        'src/selection-service-fetch-adapter.ts',
        'src/selection-service-readiness.ts'
    ]) {
        assert.doesNotMatch(source(relativePath), /ObjectSelectionSession/);
    }
});
