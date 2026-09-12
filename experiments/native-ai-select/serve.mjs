// Local, read-only routes. Raw benchmark assets remain outside the checkout.
import { createReadStream } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, extname, sep } from 'node:path';

const [bundleArg, plyArg] = process.argv.slice(2);
if (!bundleArg || !plyArg) throw new Error('Usage: node experiments/native-ai-select/serve.mjs EXTERNAL_BUNDLE EXTERNAL_PLY');
const app = await realpath('dist');
const bundle = await realpath(bundleArg);
const ply = await realpath(plyArg);
const repo = await realpath('.');
for (const path of [bundle, ply]) {
    if (path === repo || path.startsWith(repo + sep)) throw new Error('Keep assets outside the repository');
}
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.wasm': 'application/wasm' };
createServer(async (req, res) => {
    try {
        if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
        const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
        const root = path.startsWith('/bundle/') ? bundle : app;
        const file = path === '/point_cloud.ply' ? ply : await realpath(resolve(root, '.' + (root === bundle ? path.slice(7) : path === '/' ? '/index.html' : path)));
        if (file !== ply && !file.startsWith(root + sep)) { res.writeHead(403).end(); return; }
        const { size } = await stat(file);
        const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range ?? '');
        const start = range ? Number(range[1]) : 0;
        const end = range && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
        if (start > end || end >= size) { res.writeHead(416).end(); return; }
        res.writeHead(range ? 206 : 200, {
            'Content-Type': types[extname(file)] ?? 'application/octet-stream',
            'Content-Length': end - start + 1, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store',
            ...(range ? { 'Content-Range': `bytes ${start}-${end}/${size}` } : {})
        });
        if (req.method === 'HEAD') res.end();
        else createReadStream(file, { start, end }).pipe(res);
    } catch { res.writeHead(404).end(); }
}).listen(3187, '127.0.0.1', () => console.log('http://localhost:3187/?nativeMaskDiagnostic'));
