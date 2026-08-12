import { writeFile } from 'node:fs/promises';

const endpoint = process.env.CDP_ENDPOINT ?? 'http://127.0.0.1:9223';
const serviceEndpoint =
    process.env.SELECTION_SERVICE_ENDPOINT ?? 'http://127.0.0.1:8787';
const scenePath = process.env.AI_SELECT_SCENE;
if (!scenePath) {
    throw new Error(
        'AI_SELECT_SCENE must name the real browser validation fixture.'
    );
}
const screenshotPath =
    process.env.AI_SELECT_SCREENSHOT ?? '/tmp/07a-breakroom-anchor.png';
const resultScreenshotPath =
    process.env.AI_SELECT_RESULT_SCREENSHOT ??
    '/tmp/07a-breakroom-mask-result.png';
const failureScreenshotPath =
    process.env.AI_SELECT_FAILURE_SCREENSHOT ??
    '/tmp/07a-breakroom-mask-failure.png';
const capabilities = await fetch(`${serviceEndpoint}/capabilities`, {
    headers: { Origin: 'http://localhost:3000' }
}).then((response) => response.json());
const modelManifestId = capabilities.modelManifests?.[0]?.digest;
if (typeof modelManifestId !== 'string') {
    throw new Error('The Companion did not advertise a model manifest.');
}

class Cdp {
    constructor(socket) {
        this.socket = socket;
        this.nextId = 0;
        this.pending = new Map();
        this.eventWaiters = new Map();
        this.events = new Map();
        socket.addEventListener('message', (event) => {
            const message = JSON.parse(event.data);
            if (message.id !== undefined) {
                const request = this.pending.get(message.id);
                if (request !== undefined) {
                    this.pending.delete(message.id);
                    clearTimeout(request.timeout);
                    if (message.error) {
                        request.reject(new Error(message.error.message));
                    } else {
                        request.resolve(message.result);
                    }
                }
                return;
            }
            const events = this.events.get(message.method) ?? [];
            events.push(message.params);
            this.events.set(message.method, events);
            const waiters = this.eventWaiters.get(message.method) ?? [];
            this.eventWaiters.delete(message.method);
            waiters.forEach((resolve) => resolve(message.params));
        });
    }

    recordedEvents(method) {
        return this.events.get(method) ?? [];
    }

    send(method, params = {}) {
        return new Promise((resolve, reject) => {
            this.nextId += 1;
            const requestId = this.nextId;
            const timeout = setTimeout(() => {
                this.pending.delete(requestId);
                reject(new Error(`CDP command timed out: ${method}`));
            }, 240000);
            this.pending.set(requestId, { resolve, reject, timeout });
            this.socket.send(JSON.stringify({ id: requestId, method, params }));
        });
    }

    event(method) {
        return new Promise((resolve) => {
            const waiters = this.eventWaiters.get(method) ?? [];
            waiters.push(resolve);
            this.eventWaiters.set(method, waiters);
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
}

const targets = await fetch(`${endpoint}/json`).then((response) =>
    response.json()
);
const target = targets.find((entry) => entry.type === 'page');
if (!target) {
    throw new Error('No CDP page target is available.');
}
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
await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
    source: `
        Object.defineProperty(window, 'showOpenFilePicker', {
            configurable: true,
            value: undefined
        });
        localStorage.setItem('i18nextLng', 'en');
    `
});
const progress = (message) => console.error(`[07A browser] ${message}`);

const waitUntil = async (expression, timeoutMs = 30000) => {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
        if (await cdp.evaluate(expression)) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out waiting for: ${expression}`);
};

const clickRect = async (expression) => {
    const rect = await cdp.evaluate(expression);
    if (rect === null) {
        throw new Error(`Click target is unavailable: ${expression}`);
    }
    const x = rect.x + rect.width / 2;
    const y = rect.y + rect.height / 2;
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

const reloaded = cdp.event('Page.loadEventFired');
progress('reloading editor');
await cdp.send('Page.reload', { ignoreCache: true });
await reloaded;
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
progress('loading scene fixture');
await waitUntil(
    "Number(document.body.innerText.match(/Splats\\s+([\\d,]+)/)?.[1]?.replaceAll(',', '') ?? 0) > 0",
    60000
);

await cdp.evaluate(
    "document.querySelector('.selection-service-readiness-check')?.click()"
);
progress('negotiating Companion readiness');
await waitUntil(
    `document.getElementById(${JSON.stringify(modelManifestId)}) !== null`,
    10000
);
await cdp.evaluate(`(() => {
    document.querySelectorAll('.selection-service-readiness-select .pcui-select-input-value')[1].click();
    document.getElementById(${JSON.stringify(modelManifestId)}).click();
    document.querySelector('.selection-service-readiness-check').click();
})()`);
progress('rendering authoritative Anchor RGB');
await waitUntil(
    "document.querySelector('.selection-service-readiness-status')?.textContent.trim() === 'Object Selection: ready'",
    10000
);

await cdp.evaluate(`(() => {
    const button = document.getElementById('bottom-toolbar-ai-select');
    if (!button.classList.contains('active')) button.click();
})()`);
await waitUntil(
    "document.getElementById('ai-select-anchor-dock-image')?.src?.startsWith('data:image/png')",
    60000
);

const screenshot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false
});
await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'));

const layout = await cdp.evaluate(`(() => {
    const rect = (selector) => {
        const element = document.querySelector(selector);
        if (element === null) return null;
        const value = element.getBoundingClientRect();
        return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    return {
        splatText: document.body.innerText.match(/Splats\\s+([\\d,]+)/)?.[1],
        dock: rect('#ai-select-anchor-dock'),
        main: rect('#ai-select-anchor-dock-main'),
        viewport: rect('#ai-select-anchor-dock-image-viewport'),
        imageWrap: rect('#ai-select-anchor-dock-image-wrap'),
        image: rect('#ai-select-anchor-dock-image'),
        overlay: rect('#ai-select-anchor-dock-mask-overlay'),
        toolActions: rect('#ai-select-anchor-dock-tools'),
        information: rect('#ai-select-anchor-dock-information'),
        primaryActions: rect('#ai-select-anchor-dock-primary-actions'),
        resizeHandle: rect('#ai-select-panel-resize-handle'),
        bodyText: document.getElementById('ai-select-anchor-dock')?.innerText
    };
})()`);

const initialDockHeight = layout.dock.height;
progress('resizing Dock and checking fitted layout');
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: layout.resizeHandle.x + layout.resizeHandle.width / 2,
    y: layout.resizeHandle.y + layout.resizeHandle.height / 2,
    button: 'left',
    clickCount: 1
});
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x: layout.resizeHandle.x + layout.resizeHandle.width / 2,
    y: layout.resizeHandle.y - 80,
    button: 'left'
});
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: layout.resizeHandle.x + layout.resizeHandle.width / 2,
    y: layout.resizeHandle.y - 80,
    button: 'left',
    clickCount: 1
});
await waitUntil(
    `document.getElementById('ai-select-anchor-dock').getBoundingClientRect().height > ${initialDockHeight + 60}`
);
const resizedLayout = await cdp.evaluate(`(() => {
    const read = (id) => {
        const value = document.getElementById(id).getBoundingClientRect();
        return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    return {
        dock: read('ai-select-anchor-dock'),
        viewport: read('ai-select-anchor-dock-image-viewport'),
        imageWrap: read('ai-select-anchor-dock-image-wrap'),
        image: read('ai-select-anchor-dock-image'),
        overlay: read('ai-select-anchor-dock-mask-overlay'),
        toolActions: read('ai-select-anchor-dock-tools'),
        information: read('ai-select-anchor-dock-information'),
        primaryActions: read('ai-select-anchor-dock-primary-actions')
    };
})()`);

await cdp.evaluate(`(() => {
    if (window.__aiSelectFetchWrapped) return;
    window.__aiSelectFetchWrapped = true;
    window.__maskCapture = null;
    window.__maskRequestCount = 0;
    const original = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const response = await original(...args);
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        if (url.includes('/ai-select/mask-proposals')) {
            window.__maskRequestCount += 1;
            window.__maskCapture = {
                request: args[1]?.body ?? null,
                status: response.status,
                response: await response.clone().text()
            };
        }
        return response;
    };
})()`);

await clickRect(`(() => {
    const value = document.getElementById('ai-select-anchor-tool-negative-point')?.getBoundingClientRect();
    return value ? { x: value.x, y: value.y, width: value.width, height: value.height } : null;
})()`);
progress('checking toolbar pointer isolation');
await new Promise((resolve) => setTimeout(resolve, 300));
const toolbarIsolation = await cdp.evaluate(`({
    requestCount: window.__maskRequestCount,
    promptSummary: document.getElementById('ai-select-anchor-dock-prompt-status')?.textContent,
    promptSummaryHidden: document.getElementById('ai-select-anchor-dock-prompt-status')?.hidden
})`);
if (toolbarIsolation.requestCount !== 0) {
    throw new Error(
        `A contextual toolbar click leaked into image authoring: ${JSON.stringify(toolbarIsolation)}`
    );
}
await clickRect(`(() => {
    const value = document.getElementById('ai-select-anchor-tool-positive-point')?.getBoundingClientRect();
    return value ? { x: value.x, y: value.y, width: value.width, height: value.height } : null;
})()`);

const pointX = resizedLayout.imageWrap.x + resizedLayout.imageWrap.width * 0.45;
const pointY =
    resizedLayout.imageWrap.y + resizedLayout.imageWrap.height * 0.12;
const eventOffsets = {
    request: cdp.recordedEvents('Network.requestWillBeSent').length,
    response: cdp.recordedEvents('Network.responseReceived').length,
    finished: cdp.recordedEvents('Network.loadingFinished').length
};
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: pointX,
    y: pointY,
    button: 'left',
    clickCount: 1
});
progress('waiting for real positive-point proposal');
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: pointX,
    y: pointY,
    button: 'left',
    clickCount: 1
});
const requestDeadline = Date.now() + 120000;
let proposalRequest;
let proposalResponse;
while (Date.now() < requestDeadline) {
    proposalRequest = cdp
        .recordedEvents('Network.requestWillBeSent')
        .slice(eventOffsets.request)
        .find((event) =>
            event.request.url.endsWith('/ai-select/mask-proposals')
        );
    if (proposalRequest !== undefined) {
        proposalResponse = cdp
            .recordedEvents('Network.responseReceived')
            .slice(eventOffsets.response)
            .find((event) => event.requestId === proposalRequest.requestId);
        const finished = cdp
            .recordedEvents('Network.loadingFinished')
            .slice(eventOffsets.finished)
            .some((event) => event.requestId === proposalRequest.requestId);
        if (proposalResponse !== undefined && finished) break;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
}
if (proposalRequest === undefined || proposalResponse === undefined) {
    throw new Error(
        'No completed /ai-select/mask-proposals request was observed.'
    );
}
await waitUntil('window.__maskCapture !== null', 120000);
const maskCapture = await cdp.evaluate('window.__maskCapture');
await waitUntil(
    "document.getElementById('ai-select-anchor-dock-mask-overlay').hidden === false",
    10000
);
const uiAfterPoint = await cdp.evaluate(
    "document.getElementById('ai-select-anchor-dock')?.innerText"
);
const resultLayout = await cdp.evaluate(`(() => {
    const read = (id) => {
        const value = document.getElementById(id).getBoundingClientRect();
        return { x: value.x, y: value.y, width: value.width, height: value.height };
    };
    return {
        imageWrap: read('ai-select-anchor-dock-image-wrap'),
        image: read('ai-select-anchor-dock-image'),
        overlay: read('ai-select-anchor-dock-mask-overlay'),
        toolActions: read('ai-select-anchor-dock-tools'),
        information: read('ai-select-anchor-dock-information'),
        primaryActions: read('ai-select-anchor-dock-primary-actions')
    };
})()`);
const responseBody = JSON.parse(maskCapture.response);
const closeEnough = (left, right) => Math.abs(left - right) < 0.01;
const sameRect = (left, right) =>
    ['x', 'y', 'width', 'height'].every((key) =>
        closeEnough(left[key], right[key])
    );
if (
    !sameRect(resultLayout.imageWrap, resultLayout.image) ||
    !sameRect(resultLayout.imageWrap, resultLayout.overlay)
) {
    throw new Error(
        'RGB, Mask canvas, and interaction surface do not share one rect.'
    );
}
if (
    !closeEnough(
        resultLayout.imageWrap.width / resultLayout.imageWrap.height,
        1440 / 824
    )
) {
    throw new Error('The fitted authoritative RGB aspect ratio changed.');
}
if (
    resultLayout.toolActions.x < resultLayout.imageWrap.x ||
    resultLayout.toolActions.y < resultLayout.imageWrap.y ||
    resultLayout.toolActions.x + resultLayout.toolActions.width >
        resultLayout.imageWrap.x + resultLayout.imageWrap.width ||
    resultLayout.toolActions.y + resultLayout.toolActions.height >
        resultLayout.imageWrap.y + resultLayout.imageWrap.height
) {
    throw new Error(
        'The contextual toolbar is not contained by the image surface.'
    );
}
if (
    responseBody.proposalSet.proposals.length === 0 ||
    uiAfterPoint.includes('invalid Mask artifact') ||
    /[□▧#]/u.test(uiAfterPoint)
) {
    throw new Error(
        'The normal positive-point proposal result did not harden cleanly.'
    );
}
const resultScreenshot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false
});
await writeFile(
    resultScreenshotPath,
    Buffer.from(resultScreenshot.data, 'base64')
);
await cdp.evaluate(`(() => {
    const successfulFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const response = await successfulFetch(...args);
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        if (!url.includes('/ai-select/mask-proposals')) return response;
        const body = await response.clone().json();
        body.proposalSet.digest = 'sha256:${'0'.repeat(64)}';
        return new Response(JSON.stringify(body), {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers
        });
    };
    document.getElementById('ai-select-anchor-tool-positive-point').click();
})()`);
progress('checking single localized failure with collapsed technical details');
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: resizedLayout.imageWrap.x + resizedLayout.imageWrap.width * 0.4,
    y: resizedLayout.imageWrap.y + resizedLayout.imageWrap.height * 0.2,
    button: 'left',
    clickCount: 1
});
await cdp.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: resizedLayout.imageWrap.x + resizedLayout.imageWrap.width * 0.4,
    y: resizedLayout.imageWrap.y + resizedLayout.imageWrap.height * 0.2,
    button: 'left',
    clickCount: 1
});
const localizedFailure =
    'The Mask result could not be verified. Retry the proposal.';
await waitUntil(
    `document.getElementById('ai-select-anchor-dock-mask-status')?.textContent === ${JSON.stringify(localizedFailure)}`,
    120000
);
const failureState = await cdp.evaluate(`(() => {
    const dock = document.getElementById('ai-select-anchor-dock');
    const details = document.getElementById('ai-select-anchor-technical-details');
    const message = ${JSON.stringify(localizedFailure)};
    return {
        messageCount: dock.innerText.split(message).length - 1,
        promptSummary: document.getElementById('ai-select-anchor-dock-prompt-status')?.textContent,
        details: {
            hidden: details.hidden,
            open: details.open,
            summary: details.querySelector('summary')?.textContent,
            body: details.querySelector('pre')?.textContent
        }
    };
})()`);
if (
    failureState.messageCount !== 1 ||
    failureState.details.hidden ||
    failureState.details.open ||
    failureState.details.summary !== 'Technical details' ||
    !failureState.details.body.includes('invalid Mask artifact') ||
    /[+−□▧#]/u.test(failureState.promptSummary)
) {
    throw new Error(
        `Failure presentation was not hardened: ${JSON.stringify(failureState)}`
    );
}
const failureScreenshot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false
});
await writeFile(
    failureScreenshotPath,
    Buffer.from(failureScreenshot.data, 'base64')
);
console.log(
    JSON.stringify(
        {
            screenshotPath,
            resultScreenshotPath,
            failureScreenshotPath,
            layout,
            resizedLayout,
            resultLayout,
            point: { x: pointX, y: pointY },
            toolbarIsolation,
            modelManifestId,
            request: JSON.parse(maskCapture.request),
            response: {
                status: maskCapture.status,
                body: responseBody
            },
            uiAfterPoint,
            failureState
        },
        null,
        2
    )
);
socket.close();
