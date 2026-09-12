// Pure CPU oracle: double precision, premultiplied RGB, no residual early exit.
export type Layer = { id: number; sourceRow: number; alpha: number; color?: readonly number[] };
export type Contributor = { id: number; sourceRow: number; drawSlot: number; alpha: number; T: number; w: number };

export class IncompleteContributionError extends Error {
    constructor(reason: string) {
        super(`Incomplete contribution: ${reason}`);
        this.name = 'IncompleteContributionError';
    }
}

export const compareTraceIdentity = (cpu: readonly Pick<Contributor, 'id' | 'drawSlot'>[], gpuNearToFar: readonly Pick<Contributor, 'id' | 'drawSlot'>[]) => {
    const cpuIds = new Set(cpu.map(c => c.id)), gpuIds = new Set(gpuNearToFar.map(c => c.id));
    const missingCPU = gpuNearToFar.filter(c => !cpuIds.has(c.id)).map(c => c.id);
    const extraCPU = cpu.filter(c => !gpuIds.has(c.id)).map(c => c.id);
    const drawOrderMatches = cpu.length === gpuNearToFar.length && cpu.every((c, i) => c.id === gpuNearToFar[i].id && c.drawSlot === gpuNearToFar[i].drawSlot);
    return { missingCPU, extraCPU, drawOrderMatches };
};


export type CacheSnapshot = {
    /** Full native cache textures: A has four u32 words, B one u32 per entry. */
    cacheA: Uint32Array;
    cacheB: Uint32Array;
    /** Actual far-to-near cache entry indices; only [0,count) is live. */
    order: Uint32Array;
    count: number;
    entryBase: number;
    instanceBase: number;
    sourceRows: Uint32Array;
    width: number;
    height: number;
};
export type ROI = { x: number; y: number; width: number; height: number };
export const SUPPORT_POLICY = Object.freeze({ positiveErosionRadius: 2, negativeGap: 4 });
export const CONTRIBUTION_LIMITS = Object.freeze({ pixels: 20000, records: 20000000, traceRecords: 20000, bytes: 128 * 1024 * 1024, tracePixels: 16, selectionSets: 32 });
export type ContributionOptions = {
    /** Frozen square/Chebyshev policy; shared unchanged across views. */
    policy?: typeof SUPPORT_POLICY;
    /** Limits may only lower the hard ceilings. */
    limits?: Partial<{ [K in keyof typeof CONTRIBUTION_LIMITS]: number }>;
    selectionSets?: readonly (readonly number[])[];
};

export const halfToFloat = (bits: number): number => {
    const sign = bits & 0x8000 ? -1 : 1;
    const exponent = (bits >>> 10) & 31;
    const mantissa = bits & 1023;
    if (exponent === 31) return mantissa ? NaN : sign * Infinity;
    return sign * (exponent ? (1 + mantissa / 1024) * 2 ** (exponent - 15) : mantissa * 2 ** -24);
};

const integer = (value: number, label: string, min = 0) => {
    if (!Number.isSafeInteger(value) || value < min) throw new Error(`Invalid ${label}: ${value}`);
};
const contains = (ids: Uint32Array, id: number) => {
    let lo = 0;
    let hi = ids.length;
    while (lo < hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (ids[mid] < id) lo = mid + 1;
        else hi = mid;
    }
    return ids[lo] === id;
};
const snorm16 = (bits: number) => Math.max(-1, ((bits << 16) >> 16) / 32767);

export const composeLayers = (farToNear: readonly Layer[], maxRecords = 20000) => {
    integer(maxRecords, 'maxRecords');
    if (farToNear.length > Math.min(maxRecords, CONTRIBUTION_LIMITS.traceRecords)) throw new IncompleteContributionError('record limit exceeded');
    const seen = new Set<number>();
    let finalT = 1, total = 0, winnerId = -1, best = 0;
    const rgba = new Float64Array(4);
    const contributors: Contributor[] = [];
    for (let drawSlot = farToNear.length - 1; drawSlot >= 0; drawSlot--) {
        const { id, sourceRow, alpha, color } = farToNear[drawSlot];
        integer(id, 'ID'); integer(sourceRow, 'source row');
        if (seen.has(id)) throw new Error('Invalid duplicate layer ID');
        seen.add(id);
        if (color && (color.length !== 3 || color.some(c => !Number.isFinite(c) || c < 0))) throw new Error('Invalid color');
        if (!Number.isFinite(alpha) || alpha < 0 || alpha > 1) throw new Error('Invalid alpha');
        const w = alpha * finalT;
        contributors.push({ id, sourceRow, drawSlot, alpha, T: finalT, w });
        finalT *= 1 - alpha;
        total += w;
        for (let c = 0; c < 3; c++) rgba[c] += w * (color?.[c] ?? 0);
        if (w > best) {
            best = w; winnerId = id;
        }
    }
    rgba[3] = total;
    return { contributors, total, finalT, winnerId, rgba };
};


export const cacheColor = (packed: number): [number, number, number] => {
    const scale = 2 ** (packed >>> 30) / 1023;
    const output = (shift: number) => ((((packed >>> shift) & 1023) * scale) ** 2.2 + 1e-7) ** (1 / 2.2);
    return [output(0), output(10), output(20)];
};

// WebGPU rasterizer's 8-bit subpixel grid on the qualified NVIDIA/D3D12
// adapter. Reconstruct f32 clip vertices first, then snap to the raster grid.
// This is not re-sorting/re-projecting PLY depths. Unqualified devices must
// pass the native pixel gate rather than assuming identical raster precision.
const rasterTriangles = (cx: number, cy: number, ax: number, ay: number, bx: number, by: number, depth: number, width: number, height: number) => {
    const f = Math.fround;
    const ndcX = f(cx / (width / 2) - 1);
    const ndcY = f(1 - cy / (height / 2));
    const vertices = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([u, v]) => {
        const clipX = f(f(ndcX * depth) + f(f(f(u * ax + v * bx) * depth) * f(2 / width)));
        const clipY = f(f(ndcY * depth) + f(f(f(-u * ay - v * by) * depth) * f(2 / height)));
        return [Math.round((clipX / depth + 1) * width * 128) / 256, Math.round((1 - clipY / depth) * height * 128) / 256, u, v];
    });
    return [[0, 1, 2], [0, 2, 3]].map((indices) => {
        const [a, b, c] = indices.map(i => vertices[i]);
        const dx1 = b[0] - a[0], dy1 = b[1] - a[1], dx2 = c[0] - a[0], dy2 = c[1] - a[1];
        const det = dx1 * dy2 - dy1 * dx2;
        return { a, b, c, dx1, dy1, dx2, dy2, det };
    });
};
/**
 * ROI row-major outputs; winnerIds=-1 outside target mask or when every w=0.
 * Stats arrays are indexed by instance ID, sourceRows is a borrowed immutable input.
 * visible=sum(w) over the entire ROI; target=sum(w) on the un-eroded mask.
 * Positive/negative are weighted sums on the disjoint policy regions (0=ignore,
 * 1=positive, 2=negative). Neighborhoods crossing the ROI boundary are ignored.
 * The caller must keep snapshot, mask and selection lists immutable during this call.
 * Typed-array bytes are exact, including scratch; bounded trace JS objects are not
 * misrepresented as measured bytes. No scene-sized JS objects or contribution matrix.
 */
export const runContribution = (
    snapshot: CacheSnapshot, roi: ROI, mask: Uint8Array,
    tracePixels: readonly (readonly [number, number])[], options: ContributionOptions = {}
) => {
    const started = performance.now();
    const limits = { ...CONTRIBUTION_LIMITS, ...options.limits };
    for (const key of Object.keys(CONTRIBUTION_LIMITS) as (keyof typeof CONTRIBUTION_LIMITS)[]) {
        integer(limits[key], `limit ${key}`);
        if (limits[key] > CONTRIBUTION_LIMITS[key]) throw new Error(`Invalid limit ${key}: exceeds hard ceiling`);
    }
    const overflow = (reason: string): never => {
        throw new IncompleteContributionError(reason);
    };
    const { width, height, count, entryBase, instanceBase, sourceRows, cacheA, cacheB, order } = snapshot;
    integer(width, 'frame width', 1);
    integer(height, 'frame height', 1);
    integer(count, 'count');
    integer(entryBase, 'entryBase');
    integer(instanceBase, 'instanceBase');
    integer(roi.x, 'ROI x');
    integer(roi.y, 'ROI y');
    integer(roi.width, 'ROI width', 1);
    integer(roi.height, 'ROI height', 1);
    if (roi.x + roi.width > width || roi.y + roi.height > height) throw new Error('Invalid ROI: outside framebuffer; caller must clip');
    if (mask.length !== width * height) throw new Error('Invalid mask: expected full framebuffer');
    if (count > order.length || count > sourceRows.length) throw new Error('Invalid live order count');
    if (cacheA.length % 4) throw new Error('Invalid cacheA word count');
    const pixels = roi.width * roi.height;
    if (pixels > limits.pixels) overflow('pixel limit exceeded');
    if (tracePixels.length > limits.tracePixels) overflow('trace pixel limit exceeded');
    const sets = options.selectionSets ?? [];
    if (sets.length > limits.selectionSets) overflow('selection set limit exceeded');
    const policy = { ...SUPPORT_POLICY, ...options.policy };
    // This is a named fixed diagnostic, not per-view tuning machinery.
    if (policy.positiveErosionRadius !== 2 || policy.negativeGap !== 4) throw new Error('Invalid policy: use frozen SUPPORT_POLICY');
    const n = sourceRows.length;
    let typedArrayBytes = 0;
    const reserve = (bytes: number) => {
        if (!Number.isSafeInteger(bytes) || typedArrayBytes + bytes > limits.bytes) overflow('typed-array byte limit exceeded');
        typedArrayBytes += bytes;
    };
    // Account for all new arrays before any scene-sized allocation.
    reserve(n * 33); // four f64 sums + shared order-seen/touched byte
    reserve(pixels * (8 * 8 + 1 + 4)); // total,T,RGBA,best,winner + region + trace index
    reserve(pixels * sets.length * 8);
    for (const ids of sets) reserve(ids.length * 4);
    reserve(sets.length); // per-current-splat membership
    const positive = new Float64Array(n);
    const negative = new Float64Array(n);
    const visible = new Float64Array(n);
    const target = new Float64Array(n);
    const touched = new Uint8Array(n);
    const total = new Float64Array(pixels);
    const finalT = new Float64Array(pixels).fill(1);
    const rgba = new Float64Array(pixels * 4);
    const best = new Float64Array(pixels);
    const winnerIds = new Float64Array(pixels).fill(-1);
    const regions = new Uint8Array(pixels);
    const traceIndex = new Int32Array(pixels).fill(-1);
    const selectedSums = sets.map(() => new Float64Array(pixels));
    const selectedIds = sets.map((ids) => {
        for (const id of ids) {
            integer(id, 'selected ID');
            if (id >= n) throw new Error('Invalid selected ID range');
        }
        return Uint32Array.from(ids).sort();
    });
    const membership = new Uint8Array(sets.length);
    const traces = tracePixels.map(([x, y], index) => {
        integer(x, 'trace x');
        integer(y, 'trace y');
        if (x < roi.x || x >= roi.x + roi.width || y < roi.y || y >= roi.y + roi.height) throw new Error('Invalid trace pixel: outside ROI');
        const p = (y - roi.y) * roi.width + x - roi.x;
        if (traceIndex[p] !== -1) throw new Error('Invalid duplicate trace pixel');
        traceIndex[p] = index;
        return { pixel: [x, y] as [number, number], contributors: [] as Contributor[] };
    });
    let positivePixels = 0;
    let negativePixels = 0;
    let targetPixels = 0;
    for (let y = roi.y; y < roi.y + roi.height; y++) {
        for (let x = roi.x; x < roi.x + roi.width; x++) {
            const p = (y - roi.y) * roi.width + x - roi.x;
            const inside = mask[y * width + x] !== 0;
            if (inside) targetPixels++;
            const radius = inside ? policy.positiveErosionRadius : policy.negativeGap;
            if (x - radius < roi.x || y - radius < roi.y || x + radius >= roi.x + roi.width || y + radius >= roi.y + roi.height) continue;
            let uniform = true;
            for (let dy = -radius; dy <= radius && uniform; dy++) {
                for (let dx = -radius; dx <= radius; dx++) {
                    if ((mask[(y + dy) * width + x + dx] !== 0) !== inside) {
                        uniform = false;
                        break;
                    }
                }
            }
            if (uniform) {
                regions[p] = inside ? 1 : 2;
                if (inside) positivePixels++;
                else negativePixels++;
            }
        }
    }
    let records = 0;
    let traceRecords = 0;
    let touchedCount = 0;
    const degenerateEntries: number[] = [];
    let intersectingSplats = 0;
    const ndcMargin = 4 * Math.min(1024, width, height);
    const edge = Math.exp(-4);
    const cacheFloats = new Float32Array(cacheA.buffer, cacheA.byteOffset, cacheA.length);
    const f = Math.fround;
    // Reverse the exact native draw order, including zero-weight/fully hidden layers.
    for (let drawSlot = count - 1; drawSlot >= 0; drawSlot--) {
        const entry = order[drawSlot];
        const id = entry - entryBase + instanceBase;
        if (entry < entryBase || entry >= cacheB.length || entry * 4 + 3 >= cacheA.length || id < instanceBase || id >= n) throw new Error(`Invalid cache/order identity at draw slot ${drawSlot}`);
        if (touched[id] & 1) throw new Error(`Invalid duplicate order entry ${entry}`);
        touched[id] |= 1;
        const a = entry * 4;
        const center = cacheA[a];
        const axis = cacheA[a + 3];
        const b = cacheB[entry];
        const opacity = ((b >>> 16) & 255) / 255;
        // The native vertex shader skips these before reading half axes.
        if (opacity === 0) continue;
        const cx = (1 + f(f(snorm16(center & 65535)) * f(1 + ndcMargin / width))) * width / 2;
        const cy = (1 - f(f(snorm16(center >>> 16)) * f(1 + ndcMargin / height))) * height / 2;
        const ax = halfToFloat(axis & 65535);
        const ay = -halfToFloat(axis >>> 16);
        const len2 = halfToFloat(b & 65535);
        if (len2 === 0) {
            // Native zero-width quad (including a nonfinite major axis) has no
            // finite-area raster primitive. Report identities; verify native replay.
            if (degenerateEntries.length === 64) overflow('degenerate identity report limit exceeded');
            degenerateEntries.push(id);
            continue;
        }
        if (!Number.isFinite(ax) || !Number.isFinite(ay) || !Number.isFinite(len2) || len2 < 0) throw new Error(`Invalid nonfinite/negative cache axis at entry ${entry}: words=${cacheA.subarray(a, a + 4)},${b}, alpha=${opacity}`);
        const len1 = Math.hypot(ax, ay);
        if (len1 === 0 || len2 === 0) continue; // degenerate quad covers no area
        // axis2 = len2 * normalize(nativeAxis1.y, -nativeAxis1.x), then flip Y.
        const inverseLen = f(1 / Math.sqrt(f(f(ax * ax) + f(ay * ay))));
        const bx = f(f(-ay * inverseLen) * len2);
        const by = f(f(ax * inverseLen) * len2);
        const extentX = Math.abs(ax) + Math.abs(bx);
        const extentY = Math.abs(ay) + Math.abs(by);
        const x0 = Math.max(roi.x, Math.ceil(cx - extentX - 0.51));
        const x1 = Math.min(roi.x + roi.width - 1, Math.floor(cx + extentX - 0.49));
        const y0 = Math.max(roi.y, Math.ceil(cy - extentY - 0.51));
        const y1 = Math.min(roi.y + roi.height - 1, Math.floor(cy + extentY - 0.49));
        if (x0 > x1 || y0 > y1) continue;
        intersectingSplats++;
        const depth = cacheFloats[a + 1];
        if (!Number.isFinite(depth) || depth <= 0) throw new Error('Invalid perspective cache depth');
        const triangles = rasterTriangles(cx, cy, ax, ay, bx, by, depth, width, height);
        const packed = cacheA[a + 2];
        const [cr, cg, cb] = cacheColor(packed);
        for (let s = 0; s < selectedIds.length; s++) membership[s] = contains(selectedIds[s], id) ? 1 : 0;
        for (let y = y0; y <= y1; y++) {
            for (let x = x0; x <= x1; x++) {
                let r = Infinity;
                for (const tri of triangles) {
                    if (tri.det === 0) continue;
                    const dx = x + 0.5 - tri.a[0], dy = y + 0.5 - tri.a[1];
                    const p = (tri.dy2 * dx - tri.dx2 * dy) / tri.det;
                    const q = (tri.dx1 * dy - tri.dy1 * dx) / tri.det;
                    if (p < 0 || q < 0 || p + q > 1) continue;
                    const u = tri.a[2] + p * (tri.b[2] - tri.a[2]) + q * (tri.c[2] - tri.a[2]);
                    const v = tri.a[3] + p * (tri.b[3] - tri.a[3]) + q * (tri.c[3] - tri.a[3]);
                    r = u * u + v * v;
                    break;
                }
                if (r > 1) continue;
                if (++records > limits.records) overflow('record limit exceeded');
                if (!(touched[id] & 2)) {
                    touched[id] |= 2;
                    touchedCount++;
                }
                const p = (y - roi.y) * roi.width + x - roi.x;
                const alpha = opacity * (Math.exp(-4 * r) - edge) / (1 - edge);
                const T = finalT[p];
                const w = T * alpha;
                const trace = traceIndex[p];
                if (trace !== -1) {
                    if (++traceRecords > limits.traceRecords) overflow('trace record limit exceeded');
                    traces[trace].contributors.push({ id, sourceRow: sourceRows[id], drawSlot, alpha, T, w });
                }
                total[p] += w;
                finalT[p] = T * (1 - alpha);
                rgba[p * 4] += w * cr;
                rgba[p * 4 + 1] += w * cg;
                rgba[p * 4 + 2] += w * cb;
                rgba[p * 4 + 3] += w;
                visible[id] += w;
                if (regions[p] === 1) positive[id] += w;
                if (regions[p] === 2) negative[id] += w;
                if (mask[y * width + x]) {
                    target[id] += w;
                    if (w > best[p]) {
                        best[p] = w;
                        winnerIds[p] = id;
                    }
                }
                for (let s = 0; s < membership.length; s++) {
                    if (membership[s]) selectedSums[s][p] += w;
                }
            }
        }
    }
    for (let id = 0; id < n; id++) touched[id] >>>= 1;
    return {
        roi: { ...roi },
        total,
        finalT,
        rgba,
        winnerIds,
        regions,
        selectedSums,
        traces,
        stats: { positive, negative, visible, target, touched, sourceRows },
        summary: { typedArrayBytes, elapsedMs: performance.now() - started, records, traceRecords, processedPixels: pixels, scannedSplats: count, intersectingSplats, touchedCount, positivePixels, negativePixels, targetPixels, degenerateEntries, truncated: false as const, residualBound: 0 as const }
    };
};

export type ViewSupport = { readonly positive: number; readonly negative: number };
export type SupportRule = { ratio: number; minSupport: number };
export const SUPPORT_RULE: Readonly<SupportRule> = Object.freeze({ ratio: 0.8, minSupport: 1 });

/** Equal view coefficients (1), not per-view normalization or posterior feedback. */
export const classifySupport = (viewStats: readonly ViewSupport[], rule: Readonly<SupportRule> = SUPPORT_RULE) => {
    if (!Number.isFinite(rule.ratio) || rule.ratio < 0 || rule.ratio > 1 || !Number.isFinite(rule.minSupport) || rule.minSupport <= 0) throw new Error('Invalid support rule');
    let positive = 0;
    let negative = 0;
    for (const view of viewStats) {
        if (!Number.isFinite(view.positive) || view.positive < 0 || !Number.isFinite(view.negative) || view.negative < 0) throw new Error('Invalid raw view support');
        positive += view.positive;
        negative += view.negative;
    }
    const support = positive + negative;
    if (!Number.isFinite(support)) throw new Error('Invalid support sum overflow');
    const ratio = support === 0 ? null : positive / support;
    const unknown = support === 0 || support < rule.minSupport;
    const selected = !unknown && ratio >= rule.ratio && positive >= rule.minSupport;
    const conflict = positive >= rule.minSupport && negative >= rule.minSupport;
    const status = unknown ? 'unknown' : selected ? 'selected' : 'rejected';
    return { positive, negative, support, ratio, status, selected, conflict };
};
