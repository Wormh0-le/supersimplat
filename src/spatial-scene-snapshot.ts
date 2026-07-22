import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';
import {
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    sha256Digest,
    type PackedSceneSnapshot,
    type SceneSnapshotShFloatCount
} from './scene-snapshot-binary';

const SPATIAL_SCENE_MANIFEST_FORMAT = 'supersplat-spatial-scene-manifest';
const SPATIAL_SCENE_MANIFEST_FORMAT_VERSION = 1;
const SPATIAL_SCENE_CHUNK_FORMAT = 'supersplat-spatial-scene-chunk';
const SPATIAL_SCENE_CHUNK_FORMAT_VERSION = 1;
const DEFAULT_SPATIAL_SCENE_CHUNK_BYTES = 1 * 1024 * 1024;
const MAX_SPATIAL_SCENE_CHUNK_COUNT = 4096;
const SPATIAL_SCENE_VALIDITY_CUT = 1 / 255;
const SPATIAL_SCENE_OPACITY_GUARD = 1 - 2 ** -12;
const SPATIAL_SCENE_WORLD_EPSILON = 1e-5;
const SPATIAL_SCENE_SCALE_EPSILON = 2 ** -18;
const MAX_FINITE_SPATIAL_SCALE = 1e12;

type SpatialSupportBounds =
    | {
          readonly kind: 'empty';
      }
    | {
          readonly kind: 'unbounded';
      }
    | {
          readonly kind: 'finite';
          readonly min: readonly [number, number, number];
          readonly max: readonly [number, number, number];
      };

interface GaussianSupportInput {
    readonly mean: readonly [number, number, number];
    readonly rotationXyzw: readonly [number, number, number, number];
    readonly logScale: readonly [number, number, number];
    readonly logitOpacity: number;
}

interface SpatialSceneChunkDescriptor {
    readonly chunkId: string;
    readonly chunkDigest: string;
    readonly byteLength: number;
    readonly gaussianCount: number;
    readonly globalOrdinalMin: number;
    readonly globalOrdinalMax: number;
    readonly supportBounds: SpatialSupportBounds;
}

interface SpatialSceneManifest {
    readonly format: typeof SPATIAL_SCENE_MANIFEST_FORMAT;
    readonly formatVersion: typeof SPATIAL_SCENE_MANIFEST_FORMAT_VERSION;
    readonly chunkFormat: typeof SPATIAL_SCENE_CHUNK_FORMAT;
    readonly chunkFormatVersion: typeof SPATIAL_SCENE_CHUNK_FORMAT_VERSION;
    readonly protocolVersion: '1';
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly contentDigest: string;
    readonly targetSplatId: string;
    readonly totalGaussianCount: number;
    readonly coordinateConvention: string;
    readonly stableIdSchema: 'uint32';
    readonly attributeSchema: string;
    readonly appearancePolicy: string;
    readonly renderConfiguration: SceneSnapshotRenderConfiguration;
    readonly shFloatCountPerGaussian: SceneSnapshotShFloatCount;
    readonly chunks: readonly SpatialSceneChunkDescriptor[];
}

interface SpatialSceneSnapshot {
    readonly manifest: SpatialSceneManifest;
    readChunkPayload(chunkId: string): Uint8Array;
}

interface BuildSpatialSceneSnapshotOptions {
    readonly targetSplatId: string;
    readonly chunkByteLength?: number;
}

const finite = (value: number): boolean => Number.isFinite(value);

const freezeTriple = (
    values: readonly [number, number, number]
): readonly [number, number, number] => Object.freeze([...values]) as readonly [number, number, number];

const SUPPORT_EMPTY = 0;
const SUPPORT_FINITE = 1;
const SUPPORT_UNBOUNDED = 2;

type SupportKind =
    typeof SUPPORT_EMPTY | typeof SUPPORT_FINITE | typeof SUPPORT_UNBOUNDED;

interface SupportBoundsScratch {
    minimumX: number;
    minimumY: number;
    minimumZ: number;
    maximumX: number;
    maximumY: number;
    maximumZ: number;
}

const supportBoundsScratch = (): SupportBoundsScratch => ({
    minimumX: 0,
    minimumY: 0,
    minimumZ: 0,
    maximumX: 0,
    maximumY: 0,
    maximumZ: 0
});

// This numeric worker is deliberately allocation-free per Gaussian. The
// manifest builder can scan a large typed SoA without creating Gaussian-shaped
// JavaScript arrays or objects; only the public single-Gaussian helper below
// materializes a descriptive bound value.
const writeConservativeGaussianSupportBounds = (
    meanX: number,
    meanY: number,
    meanZ: number,
    rotationX: number,
    rotationY: number,
    rotationZ: number,
    rotationW: number,
    logScaleX: number,
    logScaleY: number,
    logScaleZ: number,
    logitOpacity: number,
    scratch: SupportBoundsScratch
): SupportKind => {
    if (
        !finite(meanX) ||
        !finite(meanY) ||
        !finite(meanZ) ||
        !finite(rotationX) ||
        !finite(rotationY) ||
        !finite(rotationZ) ||
        !finite(rotationW) ||
        !finite(logScaleX) ||
        !finite(logScaleY) ||
        !finite(logScaleZ) ||
        !finite(logitOpacity)
    ) {
        return SUPPORT_UNBOUNDED;
    }
    const magnitude = Math.hypot(rotationX, rotationY, rotationZ, rotationW);
    if (!finite(magnitude) || magnitude === 0) {
        return SUPPORT_UNBOUNDED;
    }
    const x = rotationX / magnitude;
    const y = rotationY / magnitude;
    const z = rotationZ / magnitude;
    const w = rotationW / magnitude;
    const scaleX = Math.exp(logScaleX);
    const scaleY = Math.exp(logScaleY);
    const scaleZ = Math.exp(logScaleZ);
    if (
        !finite(scaleX) ||
        !finite(scaleY) ||
        !finite(scaleZ) ||
        scaleX <= 0 ||
        scaleY <= 0 ||
        scaleZ <= 0 ||
        scaleX > MAX_FINITE_SPATIAL_SCALE ||
        scaleY > MAX_FINITE_SPATIAL_SCALE ||
        scaleZ > MAX_FINITE_SPATIAL_SCALE
    ) {
        return SUPPORT_UNBOUNDED;
    }
    const opacity = Math.fround(1 / (1 + Math.exp(-logitOpacity)));
    if (!finite(opacity)) {
        return SUPPORT_UNBOUNDED;
    }
    if (opacity < SPATIAL_SCENE_VALIDITY_CUT * SPATIAL_SCENE_OPACITY_GUARD) {
        return SUPPORT_EMPTY;
    }
    const supportRadius = Math.sqrt(
        Math.max(
            0,
            2 *
                Math.log(
                    Math.max(opacity, SPATIAL_SCENE_VALIDITY_CUT) /
                        SPATIAL_SCENE_VALIDITY_CUT
                )
        )
    );
    const r00 = 1 - 2 * (y * y + z * z);
    const r01 = 2 * (x * y - z * w);
    const r02 = 2 * (x * z + y * w);
    const r10 = 2 * (x * y + z * w);
    const r11 = 1 - 2 * (x * x + z * z);
    const r12 = 2 * (y * z - x * w);
    const r20 = 2 * (x * z - y * w);
    const r21 = 2 * (y * z + x * w);
    const r22 = 1 - 2 * (x * x + y * y);
    const maximumScale = Math.max(scaleX, scaleY, scaleZ);
    const epsilon =
        SPATIAL_SCENE_WORLD_EPSILON +
        SPATIAL_SCENE_SCALE_EPSILON * Math.max(1, maximumScale);
    const extentX =
        supportRadius *
            Math.sqrt(
                (r00 * scaleX) ** 2 + (r01 * scaleY) ** 2 + (r02 * scaleZ) ** 2
            ) +
        epsilon;
    const extentY =
        supportRadius *
            Math.sqrt(
                (r10 * scaleX) ** 2 + (r11 * scaleY) ** 2 + (r12 * scaleZ) ** 2
            ) +
        epsilon;
    const extentZ =
        supportRadius *
            Math.sqrt(
                (r20 * scaleX) ** 2 + (r21 * scaleY) ** 2 + (r22 * scaleZ) ** 2
            ) +
        epsilon;
    if (
        !finite(extentX) ||
        !finite(extentY) ||
        !finite(extentZ) ||
        extentX < 0 ||
        extentY < 0 ||
        extentZ < 0
    ) {
        return SUPPORT_UNBOUNDED;
    }
    scratch.minimumX = meanX - extentX;
    scratch.minimumY = meanY - extentY;
    scratch.minimumZ = meanZ - extentZ;
    scratch.maximumX = meanX + extentX;
    scratch.maximumY = meanY + extentY;
    scratch.maximumZ = meanZ + extentZ;
    if (
        !finite(scratch.minimumX) ||
        !finite(scratch.minimumY) ||
        !finite(scratch.minimumZ) ||
        !finite(scratch.maximumX) ||
        !finite(scratch.maximumY) ||
        !finite(scratch.maximumZ)
    ) {
        return SUPPORT_UNBOUNDED;
    }
    return SUPPORT_FINITE;
};

const conservativeGaussianSupportBounds = (
    input: GaussianSupportInput
): SpatialSupportBounds => {
    const scratch = supportBoundsScratch();
    const kind = writeConservativeGaussianSupportBounds(
        input.mean[0],
        input.mean[1],
        input.mean[2],
        input.rotationXyzw[0],
        input.rotationXyzw[1],
        input.rotationXyzw[2],
        input.rotationXyzw[3],
        input.logScale[0],
        input.logScale[1],
        input.logScale[2],
        input.logitOpacity,
        scratch
    );
    if (kind === SUPPORT_UNBOUNDED) {
        return Object.freeze({ kind: 'unbounded' });
    }
    if (kind === SUPPORT_EMPTY) {
        return Object.freeze({ kind: 'empty' });
    }
    return Object.freeze({
        kind: 'finite',
        min: freezeTriple([
            scratch.minimumX,
            scratch.minimumY,
            scratch.minimumZ
        ]),
        max: freezeTriple([
            scratch.maximumX,
            scratch.maximumY,
            scratch.maximumZ
        ])
    });
};

const spatialChunkByteLength = (
    gaussianCount: number,
    shFloatCountPerGaussian: SceneSnapshotShFloatCount
): number => {
    return gaussianCount * (64 + 4 * shFloatCountPerGaussian);
};

const morton3 = (x: number, y: number, z: number): number => {
    let result = 0;
    for (let bit = 0; bit < 10; bit += 1) {
        result |= ((x >>> bit) & 1) << (3 * bit);
        result |= ((y >>> bit) & 1) << (3 * bit + 1);
        result |= ((z >>> bit) & 1) << (3 * bit + 2);
    }
    return result >>> 0;
};

const quantize = (value: number, minimum: number, maximum: number): number => {
    if (maximum === minimum) {
        return 0;
    }
    return Math.max(
        0,
        Math.min(
            1023,
            Math.floor(((value - minimum) / (maximum - minimum)) * 1023)
        )
    );
};

const spatialOrdering = (snapshot: PackedSceneSnapshot): Uint32Array => {
    const count = snapshot.gaussianCount;
    const minimum = [Infinity, Infinity, Infinity];
    const maximum = [-Infinity, -Infinity, -Infinity];
    for (let ordinal = 0; ordinal < count; ordinal += 1) {
        for (let axis = 0; axis < 3; axis += 1) {
            const value = snapshot.means[ordinal * 3 + axis];
            minimum[axis] = Math.min(minimum[axis], value);
            maximum[axis] = Math.max(maximum[axis], value);
        }
    }
    const keys = new Uint32Array(count);
    const ordinals = new Uint32Array(count);
    for (let ordinal = 0; ordinal < count; ordinal += 1) {
        const offset = ordinal * 3;
        keys[ordinal] = morton3(
            quantize(snapshot.means[offset], minimum[0], maximum[0]),
            quantize(snapshot.means[offset + 1], minimum[1], maximum[1]),
            quantize(snapshot.means[offset + 2], minimum[2], maximum[2])
        );
        ordinals[ordinal] = ordinal;
    }
    ordinals.sort((left, right) => keys[left] - keys[right] || left - right);
    return ordinals;
};

const chunkSupportBounds = (
    snapshot: PackedSceneSnapshot,
    ordinals: Uint32Array
): SpatialSupportBounds => {
    let hasFiniteSupport = false;
    let minimumX = Infinity;
    let minimumY = Infinity;
    let minimumZ = Infinity;
    let maximumX = -Infinity;
    let maximumY = -Infinity;
    let maximumZ = -Infinity;
    const scratch = supportBoundsScratch();
    for (let index = 0; index < ordinals.length; index += 1) {
        const ordinal = ordinals[index];
        const meanOffset = ordinal * 3;
        const rotationOffset = ordinal * 4;
        const kind = writeConservativeGaussianSupportBounds(
            snapshot.means[meanOffset],
            snapshot.means[meanOffset + 1],
            snapshot.means[meanOffset + 2],
            snapshot.rotationsXyzw[rotationOffset],
            snapshot.rotationsXyzw[rotationOffset + 1],
            snapshot.rotationsXyzw[rotationOffset + 2],
            snapshot.rotationsXyzw[rotationOffset + 3],
            snapshot.logScales[meanOffset],
            snapshot.logScales[meanOffset + 1],
            snapshot.logScales[meanOffset + 2],
            snapshot.logitOpacities[ordinal],
            scratch
        );
        if (kind === SUPPORT_UNBOUNDED) {
            return Object.freeze({ kind: 'unbounded' });
        }
        if (kind === SUPPORT_EMPTY) {
            continue;
        }
        hasFiniteSupport = true;
        minimumX = Math.min(minimumX, scratch.minimumX);
        minimumY = Math.min(minimumY, scratch.minimumY);
        minimumZ = Math.min(minimumZ, scratch.minimumZ);
        maximumX = Math.max(maximumX, scratch.maximumX);
        maximumY = Math.max(maximumY, scratch.maximumY);
        maximumZ = Math.max(maximumZ, scratch.maximumZ);
    }
    if (!hasFiniteSupport) {
        return Object.freeze({ kind: 'empty' });
    }
    return Object.freeze({
        kind: 'finite',
        min: freezeTriple([minimumX, minimumY, minimumZ]),
        max: freezeTriple([maximumX, maximumY, maximumZ])
    });
};

const sortedOrdinalChunk = (ordinals: Uint32Array): Uint32Array => {
    const result = new Uint32Array(ordinals);
    result.sort();
    return result;
};

const buildChunkPayload = (
    snapshot: PackedSceneSnapshot,
    ordinals: Uint32Array
): Uint8Array => {
    const count = ordinals.length;
    const byteLength = spatialChunkByteLength(
        count,
        snapshot.shFloatCountPerGaussian
    );
    const bytes = new Uint8Array(byteLength);
    let offset = 0;
    const globalOrdinals = new Uint32Array(bytes.buffer, offset, count);
    offset += globalOrdinals.byteLength;
    const stableIds = new Uint32Array(bytes.buffer, offset, count);
    offset += stableIds.byteLength;
    const means = new Float32Array(bytes.buffer, offset, count * 3);
    offset += means.byteLength;
    const rotations = new Float32Array(bytes.buffer, offset, count * 4);
    offset += rotations.byteLength;
    const logScales = new Float32Array(bytes.buffer, offset, count * 3);
    offset += logScales.byteLength;
    const logitOpacities = new Float32Array(bytes.buffer, offset, count);
    offset += logitOpacities.byteLength;
    const dc = new Float32Array(bytes.buffer, offset, count * 3);
    offset += dc.byteLength;
    const sh = new Float32Array(
        bytes.buffer,
        offset,
        count * snapshot.shFloatCountPerGaussian
    );

    for (let index = 0; index < count; index += 1) {
        const ordinal = ordinals[index];
        globalOrdinals[index] = ordinal;
        stableIds[index] = snapshot.stableIds[ordinal];
        means.set(
            snapshot.means.subarray(ordinal * 3, ordinal * 3 + 3),
            index * 3
        );
        rotations.set(
            snapshot.rotationsXyzw.subarray(ordinal * 4, ordinal * 4 + 4),
            index * 4
        );
        logScales.set(
            snapshot.logScales.subarray(ordinal * 3, ordinal * 3 + 3),
            index * 3
        );
        logitOpacities[index] = snapshot.logitOpacities[ordinal];
        dc.set(snapshot.dc.subarray(ordinal * 3, ordinal * 3 + 3), index * 3);
        if (snapshot.shFloatCountPerGaussian > 0) {
            const shOffset = ordinal * snapshot.shFloatCountPerGaussian;
            sh.set(
                snapshot.sh.subarray(
                    shOffset,
                    shOffset + snapshot.shFloatCountPerGaussian
                ),
                index * snapshot.shFloatCountPerGaussian
            );
        }
    }
    return bytes;
};

const buildSpatialSceneSnapshot = (
    snapshot: PackedSceneSnapshot,
    options: BuildSpatialSceneSnapshotOptions
): SpatialSceneSnapshot => {
    if (!options.targetSplatId || options.targetSplatId !== snapshot.sceneId) {
        throw new Error(
            'Spatial Scene Snapshot target identity must match its packed SceneSnapshot.'
        );
    }
    const chunkByteLength =
        options.chunkByteLength ?? DEFAULT_SPATIAL_SCENE_CHUNK_BYTES;
    const bytesPerGaussian = spatialChunkByteLength(
        1,
        snapshot.shFloatCountPerGaussian
    );
    if (
        !Number.isSafeInteger(chunkByteLength) ||
        chunkByteLength < bytesPerGaussian ||
        chunkByteLength > MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES
    ) {
        throw new Error(
            'Spatial Scene Snapshot chunk size is outside the bounded typed payload limit.'
        );
    }
    const rowsPerChunk = Math.floor(chunkByteLength / bytesPerGaussian);
    const spatialOrder = spatialOrdering(snapshot);
    const chunkRows: Uint32Array[] = [];
    const chunks: SpatialSceneChunkDescriptor[] = [];
    for (let start = 0; start < spatialOrder.length; start += rowsPerChunk) {
        const rows = sortedOrdinalChunk(
            spatialOrder.subarray(
                start,
                Math.min(start + rowsPerChunk, spatialOrder.length)
            )
        );
        if (chunkRows.length >= MAX_SPATIAL_SCENE_CHUNK_COUNT) {
            throw new Error(
                'Spatial Scene Snapshot exceeds the bounded spatial chunk count.'
            );
        }
        const payload = buildChunkPayload(snapshot, rows);
        const chunkId = `spatial-${String(chunkRows.length).padStart(8, '0')}`;
        chunkRows.push(rows);
        chunks.push(
            Object.freeze({
                chunkId,
                chunkDigest: sha256Digest(payload),
                byteLength: payload.byteLength,
                gaussianCount: rows.length,
                globalOrdinalMin: rows[0],
                globalOrdinalMax: rows[rows.length - 1],
                supportBounds: chunkSupportBounds(snapshot, rows)
            })
        );
    }
    const manifest: SpatialSceneManifest = Object.freeze({
        format: SPATIAL_SCENE_MANIFEST_FORMAT,
        formatVersion: SPATIAL_SCENE_MANIFEST_FORMAT_VERSION,
        chunkFormat: SPATIAL_SCENE_CHUNK_FORMAT,
        chunkFormatVersion: SPATIAL_SCENE_CHUNK_FORMAT_VERSION,
        protocolVersion: snapshot.protocolVersion,
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
        contentDigest: snapshot.contentDigest,
        targetSplatId: options.targetSplatId,
        totalGaussianCount: snapshot.gaussianCount,
        coordinateConvention: snapshot.coordinateConvention,
        stableIdSchema: snapshot.stableIdSchema,
        attributeSchema: snapshot.attributeSchema,
        appearancePolicy: snapshot.appearancePolicy,
        renderConfiguration: snapshot.renderConfiguration,
        shFloatCountPerGaussian: snapshot.shFloatCountPerGaussian,
        chunks: Object.freeze(chunks)
    });
    const rowsByChunkId = new Map(
        chunks.map((chunk, index) => [chunk.chunkId, chunkRows[index]])
    );
    const payloads = new Map<string, Uint8Array>();
    return Object.freeze({
        manifest,
        readChunkPayload: (chunkId: string): Uint8Array => {
            const existing = payloads.get(chunkId);
            if (existing) {
                return existing;
            }
            const rows = rowsByChunkId.get(chunkId);
            if (!rows) {
                throw new Error(
                    'Spatial Scene Snapshot requested an unknown chunk ID.'
                );
            }
            const payload = buildChunkPayload(snapshot, rows);
            const descriptor = chunks.find(chunk => chunk.chunkId === chunkId);
            if (
                !descriptor ||
                sha256Digest(payload) !== descriptor.chunkDigest
            ) {
                throw new Error(
                    'Spatial Scene Snapshot chunk payload lost its immutable digest.'
                );
            }
            payloads.set(chunkId, payload);
            return payload;
        }
    });
};

export {
    DEFAULT_SPATIAL_SCENE_CHUNK_BYTES,
    MAX_SPATIAL_SCENE_CHUNK_COUNT,
    SPATIAL_SCENE_CHUNK_FORMAT,
    SPATIAL_SCENE_CHUNK_FORMAT_VERSION,
    SPATIAL_SCENE_MANIFEST_FORMAT,
    SPATIAL_SCENE_MANIFEST_FORMAT_VERSION,
    SPATIAL_SCENE_VALIDITY_CUT,
    buildSpatialSceneSnapshot,
    conservativeGaussianSupportBounds
};

export type {
    BuildSpatialSceneSnapshotOptions,
    GaussianSupportInput,
    SpatialSceneChunkDescriptor,
    SpatialSceneManifest,
    SpatialSceneSnapshot,
    SpatialSupportBounds
};
