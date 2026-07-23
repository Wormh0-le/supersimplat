const assert = require('node:assert/strict');
const test = require('node:test');

const {
    BottomPanelController
} = require('../.test-dist/src/ui/bottom-panel-controller.js');

test('keeps the AI Select panel collapsed by default and lets the user toggle it', () => {
    const controller = new BottomPanelController();

    assert.equal(controller.activePanel, null);

    controller.toggle('aiSelect');
    assert.equal(controller.activePanel, 'aiSelect');

    controller.toggle('aiSelect');
    assert.equal(controller.activePanel, null);
});

test('publishes one exclusive bottom panel state for AI Select activation', () => {
    const controller = new BottomPanelController();
    const observed = [];
    controller.subscribe(panel => observed.push(panel));

    controller.setActivePanel('splatData');
    controller.setActivePanel('aiSelect');
    controller.setActivePanel(null);

    assert.deepEqual(observed, [null, 'splatData', 'aiSelect', null]);
});
