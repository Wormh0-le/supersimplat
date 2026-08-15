const assert = require('node:assert/strict');
const Module = require('node:module');
const test = require('node:test');

class UnusedPlayCanvasType {}

const originalModuleLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (request === 'playcanvas') {
        return new Proxy(
            {},
            {
                get: () => UnusedPlayCanvasType
            }
        );
    }
    return originalModuleLoad.call(this, request, parent, isMain);
};

const {
    CandidateViewportOverlay
} = require('../.test-dist/src/ai-select-candidate-viewport-overlay.js');
Module._load = originalModuleLoad;

const state = (revision, selectedVisible = true) => ({
    revision,
    membership:
        revision === null
            ? null
            : {
                  selectedStableGaussianIds: [1],
                  uncertainStableGaussianIds: [2]
              },
    selectedVisible,
    uncertainVisible: false,
    treatment: revision === null ? null : 'current'
});

class OverlaySource {
    constructor(initial) {
        this.current = initial;
        this.listeners = new Set();
    }

    subscribe(listener) {
        this.listeners.add(listener);
        listener(this.current);
        return () => this.listeners.delete(listener);
    }

    publish(next) {
        this.current = next;
        this.listeners.forEach((listener) => listener(next));
    }
}

test('viewport adapter reuses one revision texture and disposes every attachment', () => {
    const source = new OverlaySource(state('candidate-a'));
    const textures = [];
    const calls = [];
    const splat = {
        setCandidateOverlay(texture, options) {
            calls.push({ type: 'set', texture, options });
        },
        clearCandidateOverlay() {
            calls.push({ type: 'clear' });
        }
    };
    const adapter = new CandidateViewportOverlay(source, {
        getTarget: () => ({ splat, stableIds: {} }),
        createTexture: () => {
            const texture = {
                destroyed: false,
                destroy() {
                    this.destroyed = true;
                }
            };
            textures.push(texture);
            return texture;
        }
    });

    source.publish(state('candidate-a', false));
    assert.equal(textures.length, 1);
    assert.equal(calls.filter((call) => call.type === 'set').length, 2);

    source.publish(state('candidate-b'));
    assert.equal(textures.length, 2);
    assert.equal(textures[0].destroyed, true);
    assert.equal(calls.filter((call) => call.type === 'clear').length, 1);

    source.publish(state(null));
    assert.equal(textures[1].destroyed, true);
    assert.equal(calls.filter((call) => call.type === 'clear').length, 2);

    adapter.destroy();
    assert.equal(calls.filter((call) => call.type === 'clear').length, 2);
});

test('viewport adapter reports allocation failure and recovery without leaking', () => {
    const source = new OverlaySource(state('candidate-a'));
    let shouldFail = true;
    let failures = 0;
    let recoveries = 0;
    let sets = 0;
    const adapter = new CandidateViewportOverlay(source, {
        getTarget: () => ({
            splat: {
                setCandidateOverlay() {
                    sets += 1;
                },
                clearCandidateOverlay() {}
            },
            stableIds: {}
        }),
        createTexture: () => {
            if (shouldFail) {
                throw new Error('allocation failed');
            }
            return { destroy() {} };
        },
        onFailure: () => {
            failures += 1;
        },
        onRecovered: () => {
            recoveries += 1;
        }
    });

    assert.equal(failures, 1);
    assert.equal(sets, 0);
    shouldFail = false;
    source.publish(state('candidate-b'));
    assert.equal(sets, 1);
    assert.equal(recoveries, 1);
    adapter.destroy();
});
