// Phased browser evidence: inspect A before review-a; inspect B before review-b.
// PLAYWRIGHT_MODULE points to an external playwright-core installation.
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const [phase, outputArg, note] = process.argv.slice(2);
if (!['a', 'review-a', 'review-b', 'identity', 'screenshot', 'guards'].includes(phase) || !outputArg) {
    throw new Error('Usage: run-browser.mjs a|review-a|review-b|identity|screenshot|guards EXTERNAL_OUTPUT [review note]');
}
const output = resolve(outputArg);
if (output.startsWith(resolve('.') + '/')) throw new Error('Evidence must remain outside the repo');
await mkdir(output, { recursive: true });
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser = await chromium.connectOverCDP(process.env.CDP_URL ?? 'http://127.0.0.1:9333');
const context = browser.contexts()[0];
let page = context.pages().filter(p => p.url().startsWith('http://localhost:3187/?nativeMaskDiagnostic')).at(-1);
const errors = [];
const expectedErrors = [];
if (phase === 'a') {
    if (page) await page.close();
    page = await context.newPage();
}
if (!page) throw new Error('Run phase a first in the same browser');
page.on('pageerror', error => { errors.push(String(error)); console.error(error); });
page.on('console', message => {
    if (message.type() !== 'error') return;
    const value = message.text();
    if (phase === 'guards' && value.includes('CommandQueue task failed') && value.includes('Scene changed during Mask decoding; evidence rejected')) expectedErrors.push(value);
    else errors.push(value);
    console.error(value);
});
page.setDefaultTimeout(120000);
const call = (name, ...args) => page.evaluate(async ({ name, args }) => {
    return await window.scene.events.invoke('nativeMaskDiagnostic')[name](...args);
}, { name, args });
const save = async (name, result) => {
    for (const key of ['png', 'alignment']) {
        if (result[key]) await writeFile(resolve(output, `${name}.${key}.png`), Buffer.from(result[key].split(',')[1], 'base64'));
    }
    console.log(name, result.record);
};
try {
    if (phase === 'a') {
        await page.setViewportSize({ width: 1380, height: 980 });
        await page.goto('http://localhost:3187/?nativeMaskDiagnostic');
        await page.waitForFunction(() => window.scene?.events.functions.has('nativeMaskDiagnostic'));
        const gpu = await page.evaluate(() => {
            const device = window.scene.graphicsDevice;
            device.wgpu.lost.then(info => console.error(`GPU device lost: ${info.reason}: ${info.message}`));
            device.wgpu.addEventListener('uncapturederror', event => console.error(`GPU validation: ${event.error.message}`));
            const a = device.gpuAdapter;
            return { vendor: a.info.vendor, architecture: a.info.architecture, device: a.info.device, description: a.info.description,
                maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize };
        });
        await writeFile(resolve(output, 'gpu.json'), JSON.stringify(gpu, null, 2));
        console.log('loaded', await call('load', '/bundle/', '/point_cloud.ply'));
        await save('A.native', await call('capture', 'A'));
    } else if (phase === 'review-a') {
        if (!note) throw new Error('Supply an actual visual alignment review note');
        await call('review', 'A', note);
        console.log('A-only', await call('map', 'A'));
        const ids = await call('ids', 'A');
        await save('A.A-only', await call('capture', 'A', ids));
        await save('B.native', await call('capture', 'B'));
    } else if (phase === 'review-b') {
        if (!note) throw new Error('Supply an actual visual alignment review note');
        await call('review', 'B', note);
        console.log('B addition', await call('map', 'B'));
        const ids = await call('ids', 'AB');
        await save('A.AB', await call('capture', 'A', ids));
        await save('B.AB', await call('capture', 'B', ids));
        await save('C.native', await call('capture', 'C'));
        await save('C.A-only', await call('capture', 'C', await call('ids', 'A')));
        await save('C.AB', await call('capture', 'C', ids));
        if (JSON.stringify(ids) !== JSON.stringify(await call('ids', 'AB'))) throw new Error('C changed fusion IDs');
    } else if (phase === 'identity') {
        const statsBefore = await page.locator('.status-bar-stat-value').allTextContents();
        const identity = await call('checkIdentity');
        const statsAfter = await page.locator('.status-bar-stat-value').allTextContents();
        const ui = { before: statsBefore, after: statsAfter, unchanged: JSON.stringify(statsBefore) === JSON.stringify(statsAfter) };
        await writeFile(resolve(output, 'identity-ui.json'), JSON.stringify(ui, null, 2));
        console.log(JSON.stringify(identity, null, 2));
        if (!identity.passed) throw new Error('Identity fixture failed');
        if (!ui.unchanged || statsBefore.length !== 4) throw new Error('Identity fixture changed editor status bar');
    } else if (phase === 'guards') {
        const result = await page.evaluate(async () => {
            const scene = window.scene, api = scene.events.invoke('nativeMaskDiagnostic');
            const rejects = async fn => { try { await fn(); return false; } catch { return true; } };
            const before = JSON.stringify(api.ids('AB'));
            const cRejected = await rejects(() => api.map('C'));
            const badOverlayRejected = await rejects(() => scene.projectedSplatRenderer.setDiagnosticOverlay(api.splat(), [-1]));
            await api.capture('C', api.ids('AB'));
            const invalidOverlayPreservedCandidate = before === JSON.stringify(api.ids('AB'));
            await api.capture('A');
            const recaptureRequiresReview = await rejects(() => api.map('A'));
            const originalFetch = window.fetch;
            let started, release;
            const start = new Promise(resolve => { started = resolve; });
            const gate = new Promise(resolve => { release = resolve; });
            window.fetch = async (...args) => {
                if (String(args[0]).includes('A.easy-apple.mask.png')) { started(); await gate; }
                return originalFetch(...args);
            };
            let lateCaptureRejected;
            try {
                const pending = rejects(() => api.capture('A'));
                await start;
                scene.events.fire('pivot.started');
                release();
                lateCaptureRejected = await pending;
            } finally { window.fetch = originalFetch; }
            const noLateCandidate = api.ids('AB').length === 0 && await rejects(() => api.map('A'));
            const flagsUnchanged = api.splat().instances.flags.every(value => value === 0);
            const oldTool = scene.events.invoke('tool.active');
            scene.events.fire('tool.sphereBrushSelection');
            const sphereBrushAvailable = scene.events.invoke('tool.active') === 'sphereBrushSelection';
            if (oldTool) scene.events.fire(`tool.${oldTool}`); else scene.events.fire('tool.deactivate');
            return { cRejected, badOverlayRejected, invalidOverlayPreservedCandidate, recaptureRequiresReview, lateCaptureRejected, noLateCandidate, flagsUnchanged, sphereBrushAvailable };
        });
        await writeFile(resolve(output, 'guards.json'), JSON.stringify(result, null, 2));
        console.log(result);
        if (Object.values(result).some(value => value !== true)) throw new Error('Diagnostic guard failed');
        // Preserve the frozen A+B report; the adversarial checks deliberately invalidate their session.
    } else {
        await call('overlay', 'AB');
        await call('focus');
        await page.waitForTimeout(500);
        await page.screenshot({ path: resolve(output, 'browser.png') });
    }
    const report = await call('report');
    const adapter = await page.evaluate(async () => {
        const a = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
        return { vendor: a.info.vendor, architecture: a.info.architecture, device: a.info.device, description: a.info.description, limits: { maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize } };
    });
    if (phase !== 'guards') await writeFile(resolve(output, 'report.json'), JSON.stringify({
        ...report, browser: browser.version(), adapter,
        sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
        dirty: execFileSync('git', ['diff', '--name-only'], { encoding: 'utf8' }).trim(),
        executedAt: new Date().toISOString()
    }, null, 2) + '\n');
} finally {
    await writeFile(resolve(output, `${phase}.errors.json`), JSON.stringify({ unexpected: errors, expected: expectedErrors }, null, 2) + '\n');
    if (errors.length) process.exitCode = 1;
    await browser.close();
}
