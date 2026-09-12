// Phased browser evidence: inspect A before review-a; inspect B before review-b.
// PLAYWRIGHT_MODULE points to an external playwright-core installation.
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const [phase, outputArg, note] = process.argv.slice(2);
const target = process.env.TASK_ID ?? 'easy-apple';
if (!['easy-apple', 'medium-plate'].includes(target)) throw new Error('Unsupported TASK_ID');
const methods = ['M0', 'M2'];
if (!['a', 'review-a', 'review-b', 'contribution-a', 'contribution-review-a', 'contribution-review-b', 'identity', 'screenshot', 'guards', 'target-guards'].includes(phase) || !outputArg) {
    throw new Error('Usage: run-browser.mjs [contribution-]a|[contribution-]review-a|[contribution-]review-b|identity|screenshot|guards EXTERNAL_OUTPUT [review note]');
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
if (phase === 'a' || phase === 'contribution-a') {
    if (page) await page.close();
    page = await context.newPage();
}
if (!page) throw new Error('Run phase a first in the same browser');
page.on('pageerror', error => { errors.push(String(error)); console.error(error); });
page.on('console', message => {
    if (message.type() !== 'error') return;
    const value = message.text();
    const guardErrors = ['Scene changed during Mask decoding; evidence rejected', 'Contribution capture requires raw appearance and no native selection or pending grade', 'Freeze A contribution rule before B/C capture', 'Trace must pass; use reviewed A/B only', 'Incomplete contribution:', 'Scene changed during contribution analysis', 'Queued diagnostic invalidated before execution'];
    if (['guards', 'target-guards'].includes(phase) && value.includes('CommandQueue task failed') && guardErrors.some(expected => value.includes(expected))) expectedErrors.push(value);
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
const evaluate = async (role, mode) => {
    const result = await call('evaluateContribution', role, mode, methods);
    for (let i = 0; i < result.comparison.length; i++) await writeFile(resolve(output, `${role}.${result.comparison[i].name}.${mode}.q.png`), Buffer.from(result.qImages[i].split(',')[1], 'base64'));
    console.log(role, mode, result.comparison.map(m => ({ method: m.name, instances: m.ids.length, ...m.metrics })), result.summary);
};
const overlays = async (role, mode) => {
    for (const method of methods) {
        const { ids } = await call('contributionIds', method, mode);
        await save(`${role}.${method}.${mode}`, await call('capture', role, ids));
    }
};
try {
    if (phase === 'a' || phase === 'contribution-a') {
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
        await call('setTarget', target);
        await save('A.native', await call('capture', 'A', null, phase === 'contribution-a'));
        if ((await call('report')).taskId !== target) throw new Error('Runner target differs from live session');
    } else if (phase === 'contribution-review-a') {
        if ((await call('report')).taskId !== target) throw new Error('Runner target differs from live session');
        if (!note) throw new Error('Supply actual A visual alignment review');
        await call('review', 'A', note);
        await call('map', 'A');
        const trace = await call('trace');
        await writeFile(resolve(output, 'contribution-trace.json'), JSON.stringify(trace, null, 2));
        if (!trace.passed) throw new Error('Native contribution reconstruction gate FAILED; no selection comparison permitted');
        const first = await call('analyze', 'A');
        console.log('A analysis', first.summary);
        const tiling = await call('checkTiling', 'A');
        await writeFile(resolve(output, 'A.tiling-check.json'), JSON.stringify(tiling, null, 2));
        if (!tiling.passed) throw new Error('A monolithic/tiled mismatch');
        const warm = [first.summary];
        for (let i = 0; i < 3; i++) warm.push((await call('analyze', 'A')).summary);
        await writeFile(resolve(output, 'A.warm.json'), JSON.stringify(warm, null, 2));
        await evaluate('A', 'A');
        await overlays('A', 'A');
        console.log('frozen', await call('freezeContribution'));
        await save('B.native', await call('capture', 'B', null, true));
    } else if (phase === 'contribution-review-b') {
        if ((await call('report')).taskId !== target) throw new Error('Runner target differs from live session');
        if (!note) throw new Error('Supply actual B visual alignment review');
        await call('review', 'B', note);
        await call('map', 'B');
        if (!(await call('trace', 'B')).passed) throw new Error('B native numerical regression failed');
        const first = await call('analyze', 'B');
        console.log('B analysis', first.summary);
        if (target === 'easy-apple') {
            const tiling = await call('checkTiling', 'B');
            await writeFile(resolve(output, 'B.tiling-check.json'), JSON.stringify(tiling, null, 2));
            if (!tiling.passed) throw new Error('B monolithic/tiled mismatch');
        }
        const warm = [first.summary];
        for (let i = 0; i < 3; i++) warm.push((await call('analyze', 'B')).summary);
        await writeFile(resolve(output, 'B.warm.json'), JSON.stringify(warm, null, 2));
        await call('contributionPositions');
        await evaluate('A', 'AB'); await evaluate('B', 'A'); await evaluate('B', 'AB');
        await overlays('A', 'AB'); await overlays('B', 'A'); await overlays('B', 'AB');
        await call('releaseSnapshot', 'A'); await call('releaseSnapshot', 'B');
        const before = await call('contributionIds', 'M2', 'AB');
        await save('C.native', await call('capture', 'C', null, true));
        if (!(await call('trace', 'C')).passed) throw new Error('C native numerical regression failed');
        await evaluate('C', 'A'); await evaluate('C', 'AB');
        await overlays('C', 'A'); await overlays('C', 'AB');
        if (JSON.stringify(before) !== JSON.stringify(await call('contributionIds', 'M2', 'AB'))) throw new Error('C changed contribution fusion');
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
    } else if (phase === 'target-guards') {
        const result = await page.evaluate(async () => {
            const d = window.scene.events.invoke('nativeMaskDiagnostic');
            const originalTarget = d.report().taskId;
            const other = originalTarget === 'easy-apple' ? 'medium-plate' : 'easy-apple';
            const rejected = async (fn, pattern) => { try { await fn(); return false; } catch (error) { return pattern.test(String(error)); } };
            let queuedSwitchRejected = true, queuedCancelRejected = true;
            for (const ids of [null, [0]]) {
                const switched = rejected(() => d.capture('A', ids), /Queued diagnostic invalidated/);
                d.setTarget(other);
                queuedSwitchRejected &&= await switched;
                d.setTarget(originalTarget);
                const cancelled = rejected(() => d.capture('A', ids), /Queued diagnostic invalidated/);
                d.cancel();
                queuedCancelRejected &&= await cancelled;
            }
            await d.capture('A', null, true);
            d.review('A', 'Guard fixture only: replay of previously visually inspected A input; not User Confirmed');
            d.map('A');
            if (!(await d.trace('A')).passed) throw new Error('Guard source trace failed');
            await d.analyze('A');
            const complete = JSON.stringify(d.report().contributions.A), ids = JSON.stringify(d.ids('A'));
            const capacityRejected = await rejected(() => d.analyze('A', { tilePixels: 512, records: 1 }), /Incomplete contribution.*record/);
            const capacityPreservesComplete = complete === JSON.stringify(d.report().contributions.A) && ids === JSON.stringify(d.ids('A'));
            const pending = rejected(() => d.analyze('A', { tilePixels: 512 }), /Incomplete contribution.*stale|Scene changed during contribution analysis/);
            setTimeout(() => d.setTarget(other), 0);
            const lateAnalysisRejected = await pending;
            const r = d.report();
            const switchClearsTargetEvidence = r.taskId === other && d.ids('AB').length === 0 && !r.contributions.A && !r.contributionTrace && !r.contributionFreeze && Object.keys(r.reviews).length === 0 && Object.keys(r.captures).length === 0 && r.renderedOverlays.length === 0 && Object.keys(r.contributionEvaluations ?? {}).length === 0;
            const oldReviewRejected = await rejected(() => d.map('A'), /Only reviewed A\/B/);
            const originalFetch = window.fetch;
            let started, release;
            const start = new Promise(resolve => { started = resolve; });
            const gate = new Promise(resolve => { release = resolve; });
            const path = r.input.masks.find(m => m.role === 'A' && m.task === other).path;
            window.fetch = async (...args) => { if (String(args[0]).endsWith(path)) { started(); await gate; } return originalFetch(...args); };
            let lateMaskRejected;
            try {
                const late = rejected(() => d.capture('A'), /Scene changed during Mask decoding/);
                await start; d.setTarget(originalTarget); release(); lateMaskRejected = await late;
            } finally { window.fetch = originalFetch; release?.(); }
            const noPartialPublication = d.ids('AB').length === 0 && Object.keys(d.report().captures).length === 0;
            return { queuedSwitchRejected, queuedCancelRejected, capacityRejected, capacityPreservesComplete, lateAnalysisRejected, switchClearsTargetEvidence, oldReviewRejected, lateMaskRejected, noPartialPublication, flagsUnchanged: d.splat().instances.flags.every(v => v === 0) };
        });
        await writeFile(resolve(output, 'target-guards.json'), JSON.stringify(result, null, 2));
        console.log(result);
        if (Object.values(result).some(v => v !== true)) throw new Error('Target guard failed');
    } else if (phase === 'identity') {
        const statsBefore = await page.locator('.status-bar-stat-value').allTextContents();
        const identity = await call('checkIdentity');
        const statsAfter = await page.locator('.status-bar-stat-value').allTextContents();
        const ui = { before: statsBefore, after: statsAfter, unchanged: JSON.stringify(statsBefore) === JSON.stringify(statsAfter) };
        await writeFile(resolve(output, 'identity-ui.json'), JSON.stringify(ui, null, 2));
        await writeFile(resolve(output, 'identity.json'), JSON.stringify(identity, null, 2));
        console.log(JSON.stringify(identity, null, 2));
        if (!identity.passed) throw new Error('Identity fixture failed');
        if (!ui.unchanged || statsBefore.length !== 4) throw new Error('Identity fixture changed editor status bar');
    } else if (phase === 'guards') {
        const result = await page.evaluate(async () => {
            const scene = window.scene, api = scene.events.invoke('nativeMaskDiagnostic');
            const rejects = async fn => { try { await fn(); return false; } catch { return true; } };
            const before = JSON.stringify(api.ids('AB'));
            const cRejected = await rejects(() => api.map('C'));
            const contributionGuards = {};
            if (api.report().contributions) {
                const beforeContribution = JSON.stringify(api.contributionIds('M2', 'AB'));
                const raw = api.support('B');
                contributionGuards.rawSupportImmutable = Object.isFrozen(raw.rows) && raw.rows.every(Object.isFrozen) && Object.isFrozen(raw.winnerIds);
                contributionGuards.cCannotAnalyze = await rejects(() => api.analyze('C'));
                contributionGuards.cCannotFuse = await rejects(() => api.contributionIds('M2', 'C'));
                contributionGuards.tintedCannotCaptureEvidence = await rejects(() => api.capture('A', [0], true));
                contributionGuards.invalidCallsPreserveFusion = beforeContribution === JSON.stringify(api.contributionIds('M2', 'AB'));
            }
            const badOverlayRejected = await rejects(() => scene.projectedSplatRenderer.setDiagnosticOverlay(api.splat(), [-1]));
            await api.capture('C', api.ids('AB'));
            const invalidOverlayPreservedCandidate = before === JSON.stringify(api.ids('AB'));
            if (Object.keys(contributionGuards).length) {
                const aBefore = JSON.stringify(api.report().contributions.A);
                await api.capture('B', null, true);
                const refreshed = api.report();
                contributionGuards.bRecaptureInvalidatesExports = !refreshed.contributions.B && !refreshed.contributionChecks.B && !refreshed.contributionChecks.C && !refreshed.contributionPositions &&
                    Object.keys(refreshed.contributionEvaluations).every(key => key === 'A.A') && await rejects(() => api.contributionIds('M2', 'AB'));
                contributionGuards.bRecapturePreservesA = aBefore === JSON.stringify(refreshed.contributions.A) && api.contributionIds('M2', 'A').ids.length > 0;
            }
            await api.capture('A');
            const recaptureRequiresReview = await rejects(() => api.map('A'));
            if (Object.keys(contributionGuards).length) {
                contributionGuards.recaptureInvalidatesContribution = await rejects(() => api.contributionIds('M2', 'AB'));
                api.review('A', 'Guard fixture: previously inspected unchanged A alignment');
                api.map('A');
                contributionGuards.bRequiresAFrozen = await rejects(() => api.capture('B', null, true));
            }
            const originalFetch = window.fetch;
            let started, release;
            const start = new Promise(resolve => { started = resolve; });
            const gate = new Promise(resolve => { release = resolve; });
            window.fetch = async (...args) => {
                if (String(args[0]).endsWith(api.report().input.masks.find(m => m.role === 'A' && m.task === api.report().taskId).path)) { started(); await gate; }
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
            return { ...contributionGuards, cRejected, badOverlayRejected, invalidOverlayPreservedCandidate, recaptureRequiresReview, lateCaptureRejected, noLateCandidate, flagsUnchanged, sphereBrushAvailable };
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
    if (!['guards', 'target-guards', 'identity'].includes(phase)) await writeFile(resolve(output, 'report.json'), JSON.stringify({
        ...report, browser: browser.version(), adapter,
        sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
        dirty: execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim(),
        executedAt: new Date().toISOString()
    }, null, 2) + '\n');
} catch (error) {
    await writeFile(resolve(output, `${phase}.failure.json`), JSON.stringify({
        error: String(error), phase, taskId: target, report: await call('report'),
        sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
        dirty: execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim()
    }, null, 2));
    throw error;
} finally {
    await writeFile(resolve(output, `${phase}.errors.json`), JSON.stringify({ unexpected: errors, expected: expectedErrors }, null, 2) + '\n');
    if (errors.length) process.exitCode = 1;
    await browser.close();
}
