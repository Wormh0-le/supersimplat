import type { CacheSnapshot } from './native-contribution-reference';

// Bounded GPU raster/blend oracle for the handful of CPU trace pixels only.
// Not the ROI producer, a rendering backend, or an acceleration claim. The cache
// decoding and quad math below mirror projected-splat-shader.ts, without tints.
const shaderCode = /* wgsl */`
struct Out {
    @builtin(position) position: vec4f,
    @location(0) uv: vec2f,
    @location(1) color: vec4f,
    @location(2) @interpolate(flat) index: u32
};
@group(0) @binding(0) var<storage, read> cache: array<u32>;
@group(0) @binding(1) var<storage, read_write> trace: array<vec4f>;
@group(0) @binding(2) var<uniform> viewport: vec2f;
@vertex fn vs(@builtin(vertex_index) v: u32, @builtin(instance_index) index: u32) -> Out {
    let base = index * 5u;
    let a = vec4u(cache[base], cache[base+1u], cache[base+2u], cache[base+3u]);
    let b = cache[base+4u];
    var o: Out;
    if (((b >> 16u) & 255u) == 0u) {
        o.position = vec4f(0.0, 0.0, 2.0, 1.0);
        return o;
    }
    let maxRadius = min(1024.0, min(viewport.x, viewport.y));
    let ndc = unpack2x16snorm(a.x) * (vec2f(1.0) + vec2f(4.0 * maxRadius) / viewport);
    let depth = bitcast<f32>(a.y);
    // No other geometry/depth writer is allowed in this diagnostic capture.
    let clip = vec4f(ndc * depth, 0.0, depth);
    let axis1 = unpack2x16float(a.w);
    let axis2 = unpack2x16float(b).x * normalize(vec2f(axis1.y, -axis1.x));
    var corners = array<vec2f,6>(vec2f(-1,-1),vec2f(1,-1),vec2f(1,1),vec2f(-1,-1),vec2f(1,1),vec2f(-1,1));
    let corner = corners[v];
    let offset = (corner.x * axis1 + corner.y * axis2) * clip.w * (vec2f(2.0) / viewport);
    let bits = a.z;
    let color = vec3f(vec3u(bits, bits>>10u, bits>>20u) & vec3u(1023u)) * (f32(1u << (bits>>30u)) / 1023.0);
    o.position = clip + vec4f(offset, 0.0, 0.0);
    o.uv = corner;
    o.color = vec4f(pow(pow(color,vec3f(2.2))+vec3f(1e-7),vec3f(1.0/2.2)), f32((b>>16u)&255u)/255.0);
    o.index = index;
    return o;
}
@fragment fn fs(o: Out) -> @location(0) vec4f {
    let radius = dot(o.uv, o.uv);
    if (radius > 1.0) { discard; }
    let alpha = (exp(-4.0*radius)-exp(-4.0))/(1.0-exp(-4.0)) * o.color.a;
    trace[o.index] = vec4f(o.color.rgb, alpha);
    return vec4f(o.color.rgb * alpha, alpha);
}`;

type ProbeLayer = { id: number; drawSlot: number; alpha: number; cache: number[] };
type ProbeSample = { pixel: number[]; contributors: ProbeLayer[]; fullFrame?: boolean };

// With snapshot supplied, membership is collected independently from EVERY live
// native draw entry. One N-sized GPU output is reused sequentially per pixel;
// never a viewport-by-N matrix and never a CPU-filtered contributor subset.
const probeNativeTrace = async (device: GPUDevice, samples: ProbeSample[], width: number, height: number, snapshot?: CacheSnapshot) => {
    if (samples.length > 16 || samples.reduce((n, s) => n + s.contributors.length, 0) > 20000) throw new Error('Native probe incomplete: record capacity');
    if (snapshot && (snapshot.count < 1 || snapshot.count > 1000000)) throw new Error('Native probe incomplete: live payload capacity');
    const start = performance.now();
    let packed: Uint32Array | undefined;
    if (snapshot) {
        packed = new Uint32Array(snapshot.count * 5);
        for (let i = 0; i < snapshot.count; i++) {
            const entry = snapshot.order[i];
            if (entry * 4 + 3 >= snapshot.cacheA.length || entry >= snapshot.cacheB.length) throw new Error('Invalid native probe cache identity');
            packed.set(snapshot.cacheA.subarray(entry * 4, entry * 4 + 4), i * 5);
            packed[i * 5 + 4] = snapshot.cacheB[entry];
        }
    }
    const shader = device.createShaderModule({ code: shaderCode });
    const pipeline = device.createRenderPipeline({
        layout: 'auto',
        vertex: { module: shader, entryPoint: 'vs' },
        fragment: { module: shader,
            entryPoint: 'fs',
            targets: [{ format: 'rgba16float', blend: { color: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha' }, alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha' } } }] },
        primitive: { cullMode: 'none' }
    });
    const viewport = device.createBuffer({ size: 8, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(viewport, 0, new Float32Array([width, height]));
    const texture = device.createTexture({ size: [width, height], format: 'rgba16float', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
    let readbackBytes = 0, peakBufferBytes = 0, cpuTypedPeakBytes = 0, records = 0;
    const results = [];
    try {
        for (const sample of samples) {
            const sequence = snapshot ? null : sample.contributors.slice().reverse();
            const count = snapshot?.count ?? sequence.length;
            if (!count) throw new Error('No trace contributors: cannot qualify an empty/failed native capture');
            const data = packed ?? Uint32Array.from(sequence.flatMap(c => c.cache));
            const input = device.createBuffer({ size: data.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
            const output = device.createBuffer({ size: count * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC });
            const read = device.createBuffer({ size: count * 16 + 256, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
            peakBufferBytes = Math.max(peakBufferBytes, data.byteLength + count * 32 + 256 + 8);
            cpuTypedPeakBytes = Math.max(cpuTypedPeakBytes, data.byteLength + count * 16 + 256);
            try {
                device.queue.writeBuffer(input, 0, data);
                const encoder = device.createCommandEncoder();
                const pass = encoder.beginRenderPass({ colorAttachments: [{ view: texture.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 0] }] });
                pass.setPipeline(pipeline);
                pass.setBindGroup(0, device.createBindGroup({ layout: pipeline.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: input } }, { binding: 1, resource: { buffer: output } }, { binding: 2, resource: { buffer: viewport } }] }));
                if (!sample.fullFrame) pass.setScissorRect(sample.pixel[0], sample.pixel[1], 1, 1);
                pass.draw(6, count);
                pass.end();
                encoder.copyBufferToBuffer(output, 0, read, 0, count * 16);
                encoder.copyTextureToBuffer({ texture, origin: [sample.pixel[0], sample.pixel[1], 0] }, { buffer: read, offset: count * 16, bytesPerRow: 256 }, [1, 1]);
                device.queue.submit([encoder.finish()]);
                await read.mapAsync(GPUMapMode.READ);
                const memory = read.getMappedRange();
                const values = new Float32Array(memory, 0, count * 4);
                const fragments: { id: number; drawSlot: number; rgba: number[] }[] = [];
                for (let i = 0; i < count; i++) {
                    // The shader's gamma epsilon makes every fragment RGB > 0,
                    // even when alpha is zero or incoming T is zero. A cleared
                    // slot therefore means no invocation, not 'occluded'.
                    if (snapshot && values[i * 4] === 0 && values[i * 4 + 1] === 0 && values[i * 4 + 2] === 0 && values[i * 4 + 3] === 0) continue;
                    if (++records > 20000) throw new Error('Native probe incomplete: GPU fragment capacity');
                    const id = snapshot ? snapshot.order[i] - snapshot.entryBase + snapshot.instanceBase : sequence[i].id;
                    const rgba = Array.from(values.subarray(i * 4, i * 4 + 4));
                    if (rgba.some(v => !Number.isFinite(v))) throw new Error('Native probe invalid fragment output');
                    fragments.push({ id, drawSlot: snapshot ? i : sequence[i].drawSlot, rgba });
                }
                results.push({ pixel: sample.pixel, half: Array.from(new Uint16Array(memory, count * 16, 4)), fragments });
                readbackBytes += count * 16 + 256;
                read.unmap();
            } finally {
                input.destroy(); output.destroy(); read.destroy();
            }
        }
    } finally {
        viewport.destroy(); texture.destroy();
    }
    return { results, cost: { wallMs: performance.now() - start, readbackBytes, cpuTypedPeakBytes, records, fullDrawCount: snapshot?.count ?? null, allocatedGpuPeakBytes: width * height * 8 + peakBufferBytes, gpuElapsedMs: null as number | null } };
};

export { probeNativeTrace };
