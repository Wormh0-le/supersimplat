import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';

const BINARY_SCENE_SNAPSHOT_FORMAT = 'supersplat-packed-scene-snapshot';
const BINARY_SCENE_SNAPSHOT_FORMAT_VERSION = 1;
const BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION = '1';
const MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES = 4 * 1024 * 1024;
const DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES =
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES;
const MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT = 4096;

type SceneSnapshotShFloatCount = 0 | 9 | 24 | 45;

type PackedSceneSnapshotFieldName =
    | 'stableIds'
    | 'means'
    | 'rotationsXyzw'
    | 'logScales'
    | 'logitOpacities'
    | 'dc'
    | 'sh';

interface PackedSceneSnapshotInput {
    readonly sceneId: string;
    readonly coordinateConvention: string;
    readonly stableIdSchema: 'uint32';
    readonly appearancePolicy: string;
    readonly renderConfiguration: SceneSnapshotRenderConfiguration;
    readonly stableIds: Uint32Array;
    readonly means: Float32Array;
    readonly rotationsXyzw: Float32Array;
    readonly logScales: Float32Array;
    readonly logitOpacities: Float32Array;
    readonly dc: Float32Array;
    readonly sh: Float32Array;
    readonly shFloatCountPerGaussian: SceneSnapshotShFloatCount;
}

interface PackedSceneSnapshotField {
    readonly name: PackedSceneSnapshotFieldName;
    readonly scalarType: 'uint32le' | 'float32le';
    readonly componentCount: number;
    readonly byteOffset: number;
    readonly byteLength: number;
}

interface PackedSceneSnapshot {
    readonly format: typeof BINARY_SCENE_SNAPSHOT_FORMAT;
    readonly formatVersion: typeof BINARY_SCENE_SNAPSHOT_FORMAT_VERSION;
    readonly protocolVersion: typeof BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly contentDigest: string;
    readonly gaussianCount: number;
    readonly coordinateConvention: string;
    readonly stableIdSchema: 'uint32';
    readonly attributeSchema: string;
    readonly appearancePolicy: string;
    readonly renderConfiguration: SceneSnapshotRenderConfiguration;
    readonly shFloatCountPerGaussian: SceneSnapshotShFloatCount;
    readonly payloadByteLength: number;
    readonly fields: readonly PackedSceneSnapshotField[];
    readonly stableIds: Uint32Array;
    readonly means: Float32Array;
    readonly rotationsXyzw: Float32Array;
    readonly logScales: Float32Array;
    readonly logitOpacities: Float32Array;
    readonly dc: Float32Array;
    readonly sh: Float32Array;
    readPayloadRange(offset: number, byteLength: number): Uint8Array;
}

interface BinarySceneSnapshotChunk {
    readonly index: number;
    readonly offset: number;
    readonly byteLength: number;
    readonly digest: string;
}

interface BinarySceneSnapshotManifest {
    readonly format: typeof BINARY_SCENE_SNAPSHOT_FORMAT;
    readonly formatVersion: typeof BINARY_SCENE_SNAPSHOT_FORMAT_VERSION;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly contentDigest: string;
    readonly content: {
        readonly protocolVersion: typeof BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION;
        readonly gaussianCount: number;
        readonly coordinateConvention: string;
        readonly stableIdSchema: 'uint32';
        readonly attributeSchema: string;
        readonly appearancePolicy: string;
        readonly renderConfiguration: SceneSnapshotRenderConfiguration;
        readonly shFloatCountPerGaussian: SceneSnapshotShFloatCount;
        readonly payloadByteLength: number;
        readonly fields: readonly PackedSceneSnapshotField[];
    };
    readonly transfer: {
        readonly chunkByteLength: number;
        readonly chunks: readonly BinarySceneSnapshotChunk[];
    };
}

const fieldNames: readonly PackedSceneSnapshotFieldName[] = [
    'stableIds',
    'means',
    'rotationsXyzw',
    'logScales',
    'logitOpacities',
    'dc',
    'sh'
];

const isLittleEndian = (): boolean => {
    const value = new Uint32Array([1]);
    return new Uint8Array(value.buffer)[0] === 1;
};

const bytesOf = (value: Uint32Array | Float32Array): Uint8Array => {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
};

const copyRenderConfiguration = (
    value: SceneSnapshotRenderConfiguration
): SceneSnapshotRenderConfiguration => {
    if (
        !value ||
        typeof value.version !== 'string' ||
        !value.version ||
        value.alphaMode !== 'opaque-background' ||
        typeof value.rasterizer !== 'string' ||
        !value.rasterizer ||
        !Number.isInteger(value.shBands) ||
        value.shBands < 0 ||
        value.shBands > 3 ||
        value.backgroundRgba.length !== 4 ||
        !value.backgroundRgba.every(component => Number.isFinite(component))
    ) {
        throw new Error(
            'Packed Scene Snapshot requires complete finite render configuration semantics.'
        );
    }
    return Object.freeze({
        version: value.version,
        backgroundRgba: Object.freeze([
            value.backgroundRgba[0],
            value.backgroundRgba[1],
            value.backgroundRgba[2],
            value.backgroundRgba[3]
        ]) as readonly [number, number, number, number],
        alphaMode: value.alphaMode,
        shBands: value.shBands,
        rasterizer: value.rasterizer
    });
};

const isSupportedShFloatCount = (
    value: number
): value is SceneSnapshotShFloatCount => {
    return value === 0 || value === 9 || value === 24 || value === 45;
};

const assertFinitePlane = (name: string, plane: Float32Array): void => {
    for (let index = 0; index < plane.length; index += 1) {
        if (!Number.isFinite(plane[index])) {
            throw new Error(
                `Packed Scene Snapshot ${name} values must be finite.`
            );
        }
    }
};

const assertUniqueStableIds = (stableIds: Uint32Array): void => {
    // Keep this proof in a typed plane: a Set would allocate a JavaScript
    // entry for every Gaussian and defeat the scalable SoA boundary.
    const ordered = new Uint32Array(stableIds);
    ordered.sort();
    for (let index = 1; index < ordered.length; index += 1) {
        if (ordered[index] === ordered[index - 1]) {
            throw new Error(
                'Packed Scene Snapshot Stable Gaussian IDs must be unique uint32 values.'
            );
        }
    }
};

const assertNonZeroRotations = (rotationsXyzw: Float32Array): void => {
    for (let offset = 0; offset < rotationsXyzw.length; offset += 4) {
        const magnitudeSquared =
            rotationsXyzw[offset] * rotationsXyzw[offset] +
            rotationsXyzw[offset + 1] * rotationsXyzw[offset + 1] +
            rotationsXyzw[offset + 2] * rotationsXyzw[offset + 2] +
            rotationsXyzw[offset + 3] * rotationsXyzw[offset + 3];
        if (magnitudeSquared <= 0) {
            throw new Error(
                'Packed Scene Snapshot rotations must be non-zero quaternions.'
            );
        }
    }
};

const assertPlaneLengths = (input: PackedSceneSnapshotInput): number => {
    const gaussianCount = input.stableIds.length;
    if (!Number.isSafeInteger(gaussianCount) || gaussianCount <= 0) {
        throw new Error(
            'Packed Scene Snapshot Gaussian count must be a positive safe integer.'
        );
    }
    if (!isSupportedShFloatCount(input.shFloatCountPerGaussian)) {
        throw new Error(
            'Packed Scene Snapshot uses an unsupported spherical-harmonic schema.'
        );
    }
    const expectedLengths: readonly [string, number, number][] = [
        ['means', input.means.length, gaussianCount * 3],
        ['rotationsXyzw', input.rotationsXyzw.length, gaussianCount * 4],
        ['logScales', input.logScales.length, gaussianCount * 3],
        ['logitOpacities', input.logitOpacities.length, gaussianCount],
        ['dc', input.dc.length, gaussianCount * 3],
        ['sh', input.sh.length, gaussianCount * input.shFloatCountPerGaussian]
    ];
    expectedLengths.forEach(([name, actual, expected]) => {
        if (actual !== expected) {
            throw new Error(
                `Packed Scene Snapshot ${name} plane has an unexpected length.`
            );
        }
    });
    return gaussianCount;
};

const u32Bytes = new Uint8Array(4);
const f32Bytes = new Uint8Array(4);
const u32View = new DataView(u32Bytes.buffer);
const f32View = new DataView(f32Bytes.buffer);

const sha256Constants = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]);

/** A small incremental SHA-256 implementation for browser-owned typed planes. */
class IncrementalSha256 {
    private readonly state = new Uint32Array([
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
        0x1f83d9ab, 0x5be0cd19
    ]);
    private readonly words = new Uint32Array(64);
    private readonly block = new Uint8Array(64);
    private blockLength = 0;
    private byteLength = 0n;
    private finished = false;

    update(bytes: Uint8Array): this {
        if (this.finished) {
            throw new Error(
                'Cannot update a completed Snapshot Content Digest.'
            );
        }
        this.byteLength += BigInt(bytes.length);
        let offset = 0;
        while (offset < bytes.length) {
            const copied = Math.min(
                64 - this.blockLength,
                bytes.length - offset
            );
            this.block.set(
                bytes.subarray(offset, offset + copied),
                this.blockLength
            );
            this.blockLength += copied;
            offset += copied;
            if (this.blockLength === 64) {
                this.processBlock(this.block);
                this.blockLength = 0;
            }
        }
        return this;
    }

    updateUint32(value: number): this {
        u32View.setUint32(0, value >>> 0, true);
        return this.update(u32Bytes);
    }

    updateFloat32(value: number): this {
        f32View.setFloat32(0, value, true);
        return this.update(f32Bytes);
    }

    updateString(value: string): this {
        const bytes = new TextEncoder().encode(value);
        this.updateUint32(bytes.length);
        return this.update(bytes);
    }

    digest(): string {
        if (this.finished) {
            throw new Error('Snapshot Content Digest was already finalized.');
        }
        const bitLength = this.byteLength * 8n;
        this.update(new Uint8Array([0x80]));
        while (this.blockLength !== 56) {
            this.update(new Uint8Array([0]));
        }
        const length = new Uint8Array(8);
        for (let index = 0; index < 8; index += 1) {
            length[7 - index] = Number(
                (bitLength >> BigInt(index * 8)) & 0xffn
            );
        }
        this.update(length);
        this.finished = true;
        let hexadecimal = '';
        for (const value of this.state) {
            hexadecimal += value.toString(16).padStart(8, '0');
        }
        return hexadecimal;
    }

    private processBlock(block: Uint8Array): void {
        const words = this.words;
        for (let index = 0; index < 16; index += 1) {
            const offset = index * 4;
            words[index] =
                ((block[offset] << 24) |
                    (block[offset + 1] << 16) |
                    (block[offset + 2] << 8) |
                    block[offset + 3]) >>>
                0;
        }
        for (let index = 16; index < 64; index += 1) {
            const previous15 = words[index - 15];
            const previous2 = words[index - 2];
            const sigma0 =
                (((previous15 >>> 7) | (previous15 << 25)) ^
                    ((previous15 >>> 18) | (previous15 << 14)) ^
                    (previous15 >>> 3)) >>>
                0;
            const sigma1 =
                (((previous2 >>> 17) | (previous2 << 15)) ^
                    ((previous2 >>> 19) | (previous2 << 13)) ^
                    (previous2 >>> 10)) >>>
                0;
            words[index] =
                (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
        }

        let a = this.state[0];
        let b = this.state[1];
        let c = this.state[2];
        let d = this.state[3];
        let e = this.state[4];
        let f = this.state[5];
        let g = this.state[6];
        let h = this.state[7];
        for (let index = 0; index < 64; index += 1) {
            const sigma1 =
                (((e >>> 6) | (e << 26)) ^
                    ((e >>> 11) | (e << 21)) ^
                    ((e >>> 25) | (e << 7))) >>>
                0;
            const choice = ((e & f) ^ (~e & g)) >>> 0;
            const temporary1 =
                (h +
                    sigma1 +
                    choice +
                    sha256Constants[index] +
                    words[index]) >>>
                0;
            const sigma0 =
                (((a >>> 2) | (a << 30)) ^
                    ((a >>> 13) | (a << 19)) ^
                    ((a >>> 22) | (a << 10))) >>>
                0;
            const majority = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
            const temporary2 = (sigma0 + majority) >>> 0;
            h = g;
            g = f;
            f = e;
            e = (d + temporary1) >>> 0;
            d = c;
            c = b;
            b = a;
            a = (temporary1 + temporary2) >>> 0;
        }
        this.state[0] = (this.state[0] + a) >>> 0;
        this.state[1] = (this.state[1] + b) >>> 0;
        this.state[2] = (this.state[2] + c) >>> 0;
        this.state[3] = (this.state[3] + d) >>> 0;
        this.state[4] = (this.state[4] + e) >>> 0;
        this.state[5] = (this.state[5] + f) >>> 0;
        this.state[6] = (this.state[6] + g) >>> 0;
        this.state[7] = (this.state[7] + h) >>> 0;
    }
}

const updateCanonicalMetadata = (
    digest: IncrementalSha256,
    snapshot: {
        readonly gaussianCount: number;
        readonly coordinateConvention: string;
        readonly stableIdSchema: 'uint32';
        readonly attributeSchema: string;
        readonly appearancePolicy: string;
        readonly renderConfiguration: SceneSnapshotRenderConfiguration;
        readonly shFloatCountPerGaussian: SceneSnapshotShFloatCount;
    }
): void => {
    digest.update(
        new TextEncoder().encode(
            `${BINARY_SCENE_SNAPSHOT_FORMAT}-v${BINARY_SCENE_SNAPSHOT_FORMAT_VERSION}\0`
        )
    );
    [
        snapshot.coordinateConvention,
        snapshot.stableIdSchema,
        snapshot.attributeSchema,
        snapshot.appearancePolicy,
        snapshot.renderConfiguration.version,
        snapshot.renderConfiguration.alphaMode,
        snapshot.renderConfiguration.rasterizer
    ].forEach(value => digest.updateString(value));
    digest.updateUint32(snapshot.gaussianCount);
    digest.updateUint32(snapshot.shFloatCountPerGaussian);
    digest.updateUint32(snapshot.renderConfiguration.shBands);
    snapshot.renderConfiguration.backgroundRgba.forEach((value) => {
        digest.updateFloat32(value);
    });
    [1, 3, 4, 3, 1, 3, snapshot.shFloatCountPerGaussian].forEach(
        componentCount => digest.updateUint32(componentCount)
    );
};

const snapshotContentDigest = (
    snapshot: Omit<
        PackedSceneSnapshot,
        'contentDigest' | 'sceneVersion' | 'readPayloadRange'
    >
): string => {
    const digest = new IncrementalSha256();
    updateCanonicalMetadata(digest, snapshot);
    fieldNames.forEach(name => digest.update(bytesOf(snapshot[name])));
    return `sha256:${digest.digest()}`;
};

const chunkDigest = (bytes: Uint8Array): string => {
    return `sha256:${new IncrementalSha256().update(bytes).digest()}`;
};

const fieldsFor = (
    snapshot: Pick<
        PackedSceneSnapshot,
        | 'stableIds'
        | 'means'
        | 'rotationsXyzw'
        | 'logScales'
        | 'logitOpacities'
        | 'dc'
        | 'sh'
        | 'shFloatCountPerGaussian'
    >
): readonly PackedSceneSnapshotField[] => {
    let byteOffset = 0;
    const componentCounts: Record<PackedSceneSnapshotFieldName, number> = {
        stableIds: 1,
        means: 3,
        rotationsXyzw: 4,
        logScales: 3,
        logitOpacities: 1,
        dc: 3,
        sh: snapshot.shFloatCountPerGaussian
    };
    return Object.freeze(
        fieldNames.map((name) => {
            const plane = snapshot[name];
            const field: PackedSceneSnapshotField = Object.freeze({
                name,
                scalarType: name === 'stableIds' ? 'uint32le' : 'float32le',
                componentCount: componentCounts[name],
                byteOffset,
                byteLength: plane.byteLength
            });
            byteOffset += plane.byteLength;
            return field;
        })
    );
};

const packedReadPayloadRange = (
    fields: readonly PackedSceneSnapshotField[],
    planes: Pick<
        PackedSceneSnapshot,
        | 'stableIds'
        | 'means'
        | 'rotationsXyzw'
        | 'logScales'
        | 'logitOpacities'
        | 'dc'
        | 'sh'
    >,
    payloadByteLength: number,
    offset: number,
    byteLength: number
): Uint8Array => {
    if (
        !Number.isSafeInteger(offset) ||
        !Number.isSafeInteger(byteLength) ||
        offset < 0 ||
        byteLength < 0 ||
        byteLength > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES ||
        offset + byteLength > payloadByteLength
    ) {
        throw new Error(
            'Packed Scene Snapshot payload reads must stay within one bounded chunk.'
        );
    }
    const bytes = new Uint8Array(byteLength);
    const end = offset + byteLength;
    fields.forEach((field) => {
        const fieldEnd = field.byteOffset + field.byteLength;
        const overlapStart = Math.max(offset, field.byteOffset);
        const overlapEnd = Math.min(end, fieldEnd);
        if (overlapStart >= overlapEnd) {
            return;
        }
        const plane = bytesOf(planes[field.name]);
        bytes.set(
            plane.subarray(
                overlapStart - field.byteOffset,
                overlapEnd - field.byteOffset
            ),
            overlapStart - offset
        );
    });
    return bytes;
};

const buildPackedSceneSnapshot = (
    input: PackedSceneSnapshotInput
): PackedSceneSnapshot => {
    if (!isLittleEndian()) {
        throw new Error(
            'Binary SceneSnapshot Registration v1 requires a little-endian typed-array platform.'
        );
    }
    if (
        !input.sceneId ||
        !input.coordinateConvention ||
        input.stableIdSchema !== 'uint32' ||
        !input.appearancePolicy
    ) {
        throw new Error(
            'Packed Scene Snapshot requires complete target identity and semantics.'
        );
    }
    const gaussianCount = assertPlaneLengths(input);
    assertUniqueStableIds(input.stableIds);
    assertFinitePlane('means', input.means);
    assertFinitePlane('rotationsXyzw', input.rotationsXyzw);
    assertFinitePlane('logScales', input.logScales);
    assertFinitePlane('logitOpacities', input.logitOpacities);
    assertFinitePlane('dc', input.dc);
    assertFinitePlane('sh', input.sh);
    assertNonZeroRotations(input.rotationsXyzw);

    const renderConfiguration = copyRenderConfiguration(
        input.renderConfiguration
    );
    const attributeSchema = `mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x${input.shFloatCountPerGaussian}`;
    const planes = {
        stableIds: input.stableIds,
        means: input.means,
        rotationsXyzw: input.rotationsXyzw,
        logScales: input.logScales,
        logitOpacities: input.logitOpacities,
        dc: input.dc,
        sh: input.sh
    };
    const fields = fieldsFor({
        ...planes,
        shFloatCountPerGaussian: input.shFloatCountPerGaussian
    });
    const payloadByteLength = fields.reduce(
        (total, field) => total + field.byteLength,
        0
    );
    if (!Number.isSafeInteger(payloadByteLength)) {
        throw new Error(
            'Packed Scene Snapshot payload exceeds the supported byte length.'
        );
    }
    const content: Omit<
        PackedSceneSnapshot,
        'contentDigest' | 'sceneVersion' | 'readPayloadRange'
    > = {
        format: BINARY_SCENE_SNAPSHOT_FORMAT,
        formatVersion: BINARY_SCENE_SNAPSHOT_FORMAT_VERSION,
        protocolVersion: BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION,
        sceneId: input.sceneId,
        gaussianCount,
        coordinateConvention: input.coordinateConvention,
        stableIdSchema: input.stableIdSchema,
        attributeSchema,
        appearancePolicy: input.appearancePolicy,
        renderConfiguration,
        shFloatCountPerGaussian: input.shFloatCountPerGaussian,
        payloadByteLength,
        fields,
        ...planes
    };
    const contentDigest = snapshotContentDigest(content);
    const snapshot: PackedSceneSnapshot = {
        ...content,
        sceneVersion: contentDigest,
        contentDigest,
        readPayloadRange: (offset, byteLength) => {
            return packedReadPayloadRange(
                fields,
                planes,
                payloadByteLength,
                offset,
                byteLength
            );
        }
    };
    return Object.freeze(snapshot);
};

const createBinarySceneSnapshotManifest = (
    snapshot: PackedSceneSnapshot,
    chunkByteLength = DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES
): BinarySceneSnapshotManifest => {
    if (
        !Number.isSafeInteger(chunkByteLength) ||
        chunkByteLength <= 0 ||
        chunkByteLength > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES
    ) {
        throw new Error(
            'Binary SceneSnapshot Registration v1 chunk size is outside the bounded limit.'
        );
    }
    const chunkCount = Math.ceil(snapshot.payloadByteLength / chunkByteLength);
    if (chunkCount > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT) {
        throw new Error(
            'Binary SceneSnapshot Registration v1 manifest exceeds the bounded chunk count.'
        );
    }
    const chunks: BinarySceneSnapshotChunk[] = [];
    for (let index = 0; index < chunkCount; index += 1) {
        const offset = index * chunkByteLength;
        const byteLength = Math.min(
            chunkByteLength,
            snapshot.payloadByteLength - offset
        );
        chunks.push(
            Object.freeze({
                index,
                offset,
                byteLength,
                digest: chunkDigest(
                    snapshot.readPayloadRange(offset, byteLength)
                )
            })
        );
    }
    return Object.freeze({
        format: BINARY_SCENE_SNAPSHOT_FORMAT,
        formatVersion: BINARY_SCENE_SNAPSHOT_FORMAT_VERSION,
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
        contentDigest: snapshot.contentDigest,
        content: Object.freeze({
            protocolVersion: snapshot.protocolVersion,
            gaussianCount: snapshot.gaussianCount,
            coordinateConvention: snapshot.coordinateConvention,
            stableIdSchema: snapshot.stableIdSchema,
            attributeSchema: snapshot.attributeSchema,
            appearancePolicy: snapshot.appearancePolicy,
            renderConfiguration: snapshot.renderConfiguration,
            shFloatCountPerGaussian: snapshot.shFloatCountPerGaussian,
            payloadByteLength: snapshot.payloadByteLength,
            fields: snapshot.fields
        }),
        transfer: Object.freeze({
            chunkByteLength,
            chunks: Object.freeze(chunks)
        })
    });
};

const isPackedSceneSnapshot = (
    value: unknown
): value is PackedSceneSnapshot => {
    return (
        typeof value === 'object' &&
        value !== null &&
        (value as PackedSceneSnapshot).format ===
            BINARY_SCENE_SNAPSHOT_FORMAT &&
        (value as PackedSceneSnapshot).formatVersion ===
            BINARY_SCENE_SNAPSHOT_FORMAT_VERSION &&
        (value as PackedSceneSnapshot).protocolVersion ===
            BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION &&
        typeof (value as PackedSceneSnapshot).sceneId === 'string' &&
        typeof (value as PackedSceneSnapshot).sceneVersion === 'string' &&
        typeof (value as PackedSceneSnapshot).contentDigest === 'string' &&
        typeof (value as PackedSceneSnapshot).readPayloadRange === 'function'
    );
};

export {
    BINARY_SCENE_SNAPSHOT_FORMAT,
    BINARY_SCENE_SNAPSHOT_FORMAT_VERSION,
    BINARY_SCENE_SNAPSHOT_PROTOCOL_VERSION,
    DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_COUNT,
    buildPackedSceneSnapshot,
    createBinarySceneSnapshotManifest,
    isPackedSceneSnapshot
};

export type {
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    PackedSceneSnapshot,
    PackedSceneSnapshotField,
    PackedSceneSnapshotFieldName,
    PackedSceneSnapshotInput,
    SceneSnapshotShFloatCount
};
