import { pathToFileURL } from 'node:url';

const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser = await chromium.launch({ headless: true, args: [
    '--remote-debugging-port=9333', '--no-sandbox', '--enable-unsafe-webgpu',
    '--use-angle=swiftshader', '--enable-features=Vulkan', '--disable-vulkan-surface'
] });
console.log('Chromium started for software WebGPU reproducibility (not a hardware benchmark)');
await new Promise(resolve => browser.on('disconnected', resolve));
