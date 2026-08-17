import { writeFile } from 'node:fs/promises';

/**
 * Ticket 22 locked-GPU browser regression for the current Final Spec path.
 *
 * Preconditions: a current `dist` server, locked Companion and CDP-enabled
 * Chromium are already running. The controlled-overlap fixture intentionally
 * exercises the valid Lift Readiness `not-ready` branch after production
 * Direct Evidence instead of fabricating a publishable Candidate.
 */

const cdpEndpoint = process.env.CDP_ENDPOINT ?? 'http://127.0.0.1:9223';
const serviceEndpoint =
    process.env.SELECTION_SERVICE_ENDPOINT ?? 'http://127.0.0.1:8787';
const editorOrigin = process.env.EDITOR_ORIGIN ?? 'http://127.0.0.1:3001';
const scenePath = process.env.AI_SELECT_SCENE;
if (!scenePath) {
    throw new Error(
        'AI_SELECT_SCENE must name the browser regression fixture.'
    );
}
const screenshotPath =
    process.env.AI_SELECT_SCREENSHOT ?? '/tmp/ticket22-final-spec-e2e.png';

const capabilities = await fetch(`${serviceEndpoint}/capabilities`, {
    headers: { Origin: editorOrigin }
}).then((response) => response.json());
if (
    capabilities.renderer?.status !== 'ready' ||
    capabilities.imageInstanceProvider?.status !== 'ready' ||
    capabilities.directEvidence?.status !== 'ready' ||
    capabilities.productionCandidateReLift?.status !== 'ready' ||
    capabilities.productionIdentity?.status !== 'ready'
) {
    throw new Error('The locked Final Spec v1.3 Runtime Profile is not ready.');
}
for (const retired of [
    'negativeBox',
    'promptBrush',
    'maskConstraints',
    'text'
]) {
    if (retired in capabilities.imageInstanceProvider.promptCapabilities) {
        throw new Error(`Retired Prompt capability leaked: ${retired}`);
    }
}
if ('referenceCandidateReLift' in capabilities) {
    throw new Error(
        'Reference Candidate remains a current Runtime Profile dependency.'
    );
}

class Cdp {
    constructor(socket) {
        this.socket = socket;
        this.nextId = 0;
        this.pending = new Map();
        this.events = new Map();
        socket.addEventListener('message', (event) => {
            const message = JSON.parse(event.data);
            if (message.id !== undefined) {
                const pending = this.pending.get(message.id);
                if (pending !== undefined) {
                    this.pending.delete(message.id);
                    clearTimeout(pending.timeout);
                    if (message.error)
                        pending.reject(new Error(message.error.message));
                    else pending.resolve(message.result);
                }
                return;
            }
            const events = this.events.get(message.method) ?? [];
            events.push(message.params);
            this.events.set(message.method, events);
        });
    }

    send(method, params = {}) {
        return new Promise((resolve, reject) => {
            this.nextId += 1;
            const id = this.nextId;
            const timeout = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`CDP command timed out: ${method}`));
            }, 300000);
            this.pending.set(id, { resolve, reject, timeout });
            this.socket.send(JSON.stringify({ id, method, params }));
        });
    }

    async evaluate(expression) {
        const result = await this.send('Runtime.evaluate', {
            expression,
            awaitPromise: true,
            returnByValue: true
        });
        if (result.exceptionDetails !== undefined) {
            throw new Error(result.exceptionDetails.text);
        }
        return result.result.value;
    }

    recorded(method) {
        return this.events.get(method) ?? [];
    }
}

const targets = await fetch(`${cdpEndpoint}/json`).then((response) =>
    response.json()
);
const target = targets.find((entry) => entry.type === 'page');
if (!target) throw new Error('No CDP page target is available.');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
});
const cdp = new Cdp(socket);
await cdp.send('Runtime.enable');
await cdp.send('Page.enable');
await cdp.send('DOM.enable');
await cdp.send('Network.enable');
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
await cdp.send('Network.setBypassServiceWorker', { bypass: true });
await cdp.send('Browser.setPermission', {
    permission: { name: 'loopback-network' },
    setting: 'granted',
    origin: editorOrigin,
    embeddedOrigin: serviceEndpoint
});
if (process.env.INSPECT_ONLY === '1') {
    if (process.env.ACCEPT_WARNING === '1') {
        await cdp.evaluate(`(() => {
            const button = [...document.querySelectorAll('#popup-buttons .popup-button')]
                .find((candidate) => candidate.textContent.trim() === 'Yes');
            button?.click();
        })()`);
        await new Promise((resolve) => setTimeout(resolve, 3000));
    }
    console.log(
        JSON.stringify(
            await cdp.evaluate(`(() => ({
                bodyText: document.body.innerText,
                availability: document.querySelector('.status-bar-availability-dot')?.className,
                validation: document.getElementById('ai-select-anchor-dock-validation-status')?.textContent,
                maskStatus: document.getElementById('ai-select-anchor-dock-mask-status')?.textContent,
                promptStatus: document.getElementById('ai-select-anchor-dock-prompt-status')?.textContent,
                technical: document.querySelector('#ai-select-anchor-technical-details pre')?.textContent,
                canvasState: document.getElementById('ai-select-work-canvas-state')?.textContent,
                issues: document.getElementById('ai-select-selected-view-issues')?.textContent,
                paletteConfirm: (() => {
                    const button = document.querySelector('.palette-confirm-mask');
                    return button ? {
                        hidden: button.hidden,
                        disabled: button.disabled,
                        title: button.title
                    } : null;
                })(),
                reLift: (() => {
                    const button = document.getElementById('ai-select-work-area-re-lift');
                    return button ? {
                        hidden: button.hidden,
                        disabled: button.disabled,
                        title: button.title
                    } : null;
                })()
            }))()`),
            null,
            2
        )
    );
    socket.close();
    process.exit(0);
}
await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
    source: `
        Object.defineProperty(window, 'showOpenFilePicker', {
            configurable: true,
            value: undefined
        });
        localStorage.setItem('i18nextLng', 'en');
    `
});

const waitUntil = async (expression, timeoutMs = 120000) => {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
        if (await cdp.evaluate(expression)) return;
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out waiting for: ${expression}`);
};

const clickPoint = async ({ x, y }) => {
    await cdp.send('Input.dispatchMouseEvent', {
        type: 'mousePressed',
        x,
        y,
        button: 'left',
        clickCount: 1
    });
    await cdp.send('Input.dispatchMouseEvent', {
        type: 'mouseReleased',
        x,
        y,
        button: 'left',
        clickCount: 1
    });
};

const clickSelector = async (selector) => {
    const rect = await cdp.evaluate(`(() => {
        const element = document.querySelector(${JSON.stringify(selector)});
        if (!element || element.hidden || element.disabled) return null;
        const rect = element.getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
    })()`);
    if (rect === null) throw new Error(`Click target unavailable: ${selector}`);
    await clickPoint({
        x: rect.x + rect.width / 2,
        y: rect.y + rect.height / 2
    });
};

const requestsFor = (suffix) =>
    cdp
        .recorded('Network.requestWillBeSent')
        .filter((event) => event.request.url.endsWith(suffix));

const requestCount = (suffix) => requestsFor(suffix).length;

const retiredRequests = () =>
    cdp
        .recorded('Network.requestWillBeSent')
        .filter((event) =>
            /object-selection-sessions|frame-sets|generated-view-masks/.test(
                event.request.url
            )
        );

const waitForRequest = async (suffix, prior = 0, timeoutMs = 180000) => {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
        const requests = requestsFor(suffix);
        if (requests.length > prior) {
            const request = requests.at(-1);
            const response = cdp
                .recorded('Network.responseReceived')
                .find((event) => event.requestId === request.requestId);
            const finished = cdp
                .recorded('Network.loadingFinished')
                .some((event) => event.requestId === request.requestId);
            if (response && finished) {
                if (response.response.status >= 400) {
                    throw new Error(
                        `${suffix} returned HTTP ${response.response.status}`
                    );
                }
                return request;
            }
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`No completed request observed: ${suffix}`);
};

const loadPrior = cdp.recorded('Page.loadEventFired').length;
await cdp.send('Page.navigate', {
    url: `${editorOrigin}/?ticket22=${Date.now()}`
});
while (cdp.recorded('Page.loadEventFired').length <= loadPrior) {
    await new Promise((resolve) => setTimeout(resolve, 100));
}
await waitUntil("document.querySelector('#file-selector') !== null");
const documentNode = await cdp.send('DOM.getDocument');
const fileSelector = await cdp.send('DOM.querySelector', {
    nodeId: documentNode.root.nodeId,
    selector: '#file-selector'
});
await cdp.send('DOM.setFileInputFiles', {
    files: [scenePath],
    nodeId: fileSelector.nodeId
});
await waitUntil(
    "Number(document.body.innerText.match(/Splats\\s+([\\d,]+)/)?.[1]?.replaceAll(',', '') ?? 0) > 0",
    60000
);
try {
    await waitUntil(
        "document.querySelector('.status-bar-availability-dot')?.classList.contains('availability-available') === true",
        30000
    );
} catch (error) {
    console.error(
        await cdp.evaluate(`Promise.all([
            Promise.race([
                fetch('http://127.0.0.1:8787/health', {
                    mode: 'cors', credentials: 'omit', cache: 'no-store'
                }).then((response) => response.json()),
                new Promise((resolve) => setTimeout(() => resolve('health-timeout'), 5000))
            ]),
            navigator.permissions.query({ name: 'loopback-network' })
                .then((permission) => permission.state)
                .catch((reason) => String(reason))
        ])`)
    );
    console.error(
        JSON.stringify(
            {
                failed: cdp.recorded('Network.loadingFailed'),
                console: cdp
                    .recorded('Runtime.consoleAPICalled')
                    .slice(-12)
                    .map((entry) => ({
                        type: entry.type,
                        values: entry.args.map(
                            (arg) => arg.value ?? arg.description
                        )
                    })),
                responses: cdp
                    .recorded('Network.responseReceived')
                    .filter((entry) => entry.response.url.includes('8787'))
                    .map((entry) => ({
                        url: entry.response.url,
                        status: entry.response.status
                    }))
            },
            null,
            2
        )
    );
    console.error(
        await cdp.evaluate(`(() => {
            const dot = document.querySelector('.status-bar-availability-dot');
            return {
                dotClass: dot?.className,
                dotTitle: dot?.title,
                bodyText: document.body.innerText,
                network: performance.getEntriesByType('resource')
                    .map((entry) => entry.name)
                    .filter((name) => name.includes('8787'))
            };
        })()`)
    );
    throw error;
}
await clickSelector('#bottom-toolbar-ai-select');
await waitUntil(
    "document.getElementById('ai-select-anchor-dock-image')?.src?.startsWith('data:image/png') === true",
    180000
);
await waitUntil(
    "document.getElementById('ai-select-floating-palette')?.style.display !== 'none'"
);

const legacyBefore = retiredRequests();
if (legacyBefore.length !== 0) {
    throw new Error('The browser issued a retired product request.');
}

await clickSelector('.palette-tool[data-tool="positive-point"]');
const imageRect = await cdp.evaluate(`(() => {
    const rect = document.getElementById('ai-select-anchor-dock-image-wrap')
        .getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
})()`);
const point = {
    x: imageRect.x + imageRect.width * 0.5,
    y: imageRect.y + imageRect.height * 0.5
};
const proposalPrior = requestCount('/ai-select/mask-proposals');
await clickPoint(point);
await waitForRequest('/ai-select/mask-proposals', proposalPrior, 240000);
await waitUntil(
    "document.getElementById('ai-select-anchor-dock-mask-overlay')?.hidden === false",
    30000
);

const geometryPrior = requestCount('/ai-select/target-geometry-hints');
const planPrior = requestCount('/ai-select/local-key-view-plans');
await clickSelector('.palette-confirm-mask');
await waitUntil(
    "document.getElementById('popup')?.hidden === false && document.getElementById('popup-header')?.textContent === 'Confirm Anchor'",
    30000
);
const warningAccepted = await cdp.evaluate(`(() => {
    const button = [...document.querySelectorAll('#popup-buttons .popup-button')]
        .find((candidate) => candidate.textContent.trim() === 'Yes');
    if (!button) return false;
    button.click();
    return true;
})()`);
if (!warningAccepted)
    throw new Error('Confirm Anchor warning action is missing.');
await waitForRequest('/ai-select/target-geometry-hints', geometryPrior, 180000);
await waitForRequest('/ai-select/local-key-view-plans', planPrior, 60000);

await waitUntil(
    "document.getElementById('ai-select-work-area-re-lift')?.disabled === false",
    120000
);
const evidencePrior = requestCount('/ai-select/direct-evidence');
const liftPrior = requestCount('/ai-select/candidate-re-lifts');
await cdp.evaluate(`(() => {
    window.__ticket22CandidateResponse = null;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const response = await originalFetch(...args);
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        if (url.endsWith('/ai-select/candidate-re-lifts')) {
            window.__ticket22CandidateResponse = await response.clone().json();
        }
        return response;
    };
})()`);
await clickSelector('#ai-select-work-area-re-lift');
await waitForRequest('/ai-select/direct-evidence', evidencePrior, 180000);
let candidateStatus;
const liftDeadline = Date.now() + 120000;
while (Date.now() < liftDeadline && candidateStatus === undefined) {
    if (requestCount('/ai-select/candidate-re-lifts') > liftPrior) {
        await waitForRequest(
            '/ai-select/candidate-re-lifts',
            liftPrior,
            120000
        );
        await waitUntil('window.__ticket22CandidateResponse !== null', 30000);
        const candidateResponse = await cdp.evaluate(
            'window.__ticket22CandidateResponse'
        );
        if (!['complete', 'not-ready'].includes(candidateResponse.status)) {
            throw new Error(
                `Candidate Re-Lift returned invalid status: ${candidateResponse.status}`
            );
        }
        candidateStatus = candidateResponse.status;
        break;
    }
    const preflightNotReady = await cdp.evaluate(
        "document.querySelector('#ai-select-anchor-technical-details pre')?.textContent.includes('Lift Readiness is Not Ready') === true"
    );
    if (preflightNotReady) {
        candidateStatus = 'not-ready-preflight';
        break;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
}
if (candidateStatus === undefined) {
    throw new Error(
        'Candidate Re-Lift produced neither publication nor Not Ready.'
    );
}

const legacyAfter = retiredRequests();
if (legacyAfter.length !== 0) {
    throw new Error('A retired request appeared during the Final Spec flow.');
}
const screenshot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false
});
await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'));
console.log(
    JSON.stringify(
        {
            status: 'passed',
            screenshotPath,
            productionIdentityDigest:
                capabilities.productionIdentity.record.identityDigest,
            candidateStatus,
            requests: {
                anchor: requestCount('/ai-select/anchor-renders'),
                mask: requestCount('/ai-select/mask-proposals'),
                geometry: requestCount('/ai-select/target-geometry-hints'),
                plan: requestCount('/ai-select/local-key-view-plans'),
                generatedMask: requestCount('/ai-select/image-instance-masks'),
                review: requestCount('/ai-select/image-instance-mask-reviews'),
                directEvidence: requestCount('/ai-select/direct-evidence'),
                candidate: requestCount('/ai-select/candidate-re-lifts')
            }
        },
        null,
        2
    )
);
socket.close();
