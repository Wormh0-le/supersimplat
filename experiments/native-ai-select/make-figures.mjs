import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [outputArg, bundleArg] = process.argv.slice(2);
const output = resolve(outputArg);
if (output.startsWith(resolve('.') + '/')) throw new Error('Evidence must remain external');
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser = await chromium.connectOverCDP(process.env.CDP_URL ?? 'http://127.0.0.1:9333');
const page = await browser.contexts()[0].newPage();
const uri = async path => `data:image/png;base64,${(await readFile(path)).toString('base64')}`;
const report = JSON.parse(await readFile(resolve(output, 'report.json'), 'utf8'));
const panels = [
    { file: '01-alignment.png', title: '1. Fixed native RGB and source Mask alignment', roles: ['A','B'], variants: ['native.png', 'native.alignment'], labels: ['Native RGB', 'Source Mask boundary (magenta)'] },
    { file: '02-a-only.png', title: `2. A-only native 3D Overlay — ${report.mappings.A.instances} instances`, roles: ['A'], variants: ['native.png', 'A-only.png'], labels: ['Native RGB', 'A-only Gaussian tint (cyan)'] },
    { file: '03-ab.png', title: `3. A union B — ${report.unionInstances} instances; alpha threshold fixed at ${report.alphaThreshold}`, roles: ['A','B'], variants: ['native.png', 'AB.png'], labels: ['Native RGB', 'A+B Gaussian tint (cyan)'] },
    { file: '04-c-inspection.png', title: '4. C inspection only — never used in mapping or threshold tuning', roles: ['C'], variants: ['native.alignment', 'A-only.png', 'AB.png'], labels: ['C + draft boundary (not certified GT)', 'A-only seen from C', 'A+B seen from C'] }
];
if (report.contributions) {
    panels.splice(1);
    for (const mode of ['A', 'AB']) for (const kind of ['overlay', 'q']) {
        panels.push({ file: `contribution-${mode}-${kind}.png`,
            title: `${mode === 'A' ? 'A only' : 'A+B fixed fusion'}: M0 / M1 / M2 ${kind}; C regression only, draft mask is NOT ground truth`,
            roles: ['A', 'B', 'C'],
            variants: [0, 1, 2].map(i => `M${i}.${mode}.${kind === 'q' ? 'q' : 'png'}`),
            labels: ['M0: alpha >= .1 frontmost', 'M1: maximum w per mask pixel', 'M2: local support ratio >= .8'],
            kind });
    }
}
try {
    for (const panel of panels) {
        const rows = [];
        for (const role of panel.roles) {
            rows.push({ role, mask: await uri(resolve(bundleArg, `${role}.easy-apple.mask.png`)), images: await Promise.all(panel.variants.map(v => uri(resolve(output, `${role}.${v}.png`)))) });
        }
        const png = await page.evaluate(async ({ panel, rows }) => {
            const load = async src => { const img = new Image(); img.src = src; await img.decode(); return img; };
            const columns = panel.variants.length;
            const width = 500 * columns;
            const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = 85 + 620 * rows.length;
            const ctx = canvas.getContext('2d'); ctx.fillStyle = '#14212b'; ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#ffffff'; ctx.font = 'bold 19px sans-serif'; ctx.fillText(panel.title, 15, 28);
            ctx.font = '14px sans-serif'; ctx.fillText(panel.kind === 'q' ? 'Q_selected = sum of selected w using ORIGINAL full-scene T. Black outside bounded ROI. Crop magnification only.' : '988 × 730 evidence; crop magnification only. Cyan tints original Gaussian opacity; no Native Selection writes.', 15, 56);
            for (let row = 0; row < rows.length; row++) {
                const mask = await load(rows[row].mask);
                const mc = document.createElement('canvas'); mc.width = mask.width; mc.height = mask.height;
                const mx = mc.getContext('2d'); mx.drawImage(mask, 0, 0);
                const data = mx.getImageData(0, 0, mc.width, mc.height).data;
                let x0 = mc.width, y0 = mc.height, x1 = 0, y1 = 0;
                for (let p = 0; p < mc.width * mc.height; p++) if (data[p * 4]) {
                    const x = p % mc.width, y = Math.floor(p / mc.width);
                    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
                }
                const side = Math.max(x1 - x0, y1 - y0) + 32;
                const cx = (x0 + x1 - side) / 2, cy = (y0 + y1 - side) / 2;
                for (let col = 0; col < columns; col++) {
                    const img = await load(rows[row].images[col]);
                    const left = col * 500 + 6, top = 85 + row * 620;
                    ctx.fillStyle = '#ffffff'; ctx.font = '16px sans-serif'; ctx.fillText(`${rows[row].role}: ${panel.labels[col]}`, left, top);
                    ctx.drawImage(img, left, top + 10, 488, 361);
                    ctx.strokeStyle = '#ff44dd'; ctx.lineWidth = 1; ctx.strokeRect(left + cx / 988 * 488, top + 10 + cy / 730 * 361, side / 988 * 488, side / 730 * 361);
                    ctx.imageSmoothingEnabled = false;
                    ctx.drawImage(img, cx, cy, side, side, left + 133, top + 380, 222, 222);
                    ctx.imageSmoothingEnabled = true;
                }
            }
            return canvas.toDataURL();
        }, { panel, rows });
        await writeFile(resolve(output, panel.file), Buffer.from(png.split(',')[1], 'base64'));
        console.log(panel.file);
    }
} finally { await page.close(); await browser.close(); }
