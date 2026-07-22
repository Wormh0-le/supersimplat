import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';

const BINARY_SCENE_SNAPSHOT_FORMAT = 'supersplat-packed-scene-snapshot';
const BINARY_SCENE_SNAPSHOT_FORMAT_VERSION = 1;
const MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES = 4 * 1024 * 1024;
const DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES =
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES;

type SceneSnapshotShFloatCount = 0 | 9 | 24 | 45;

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
    readonly name:
        | 'stableIds'
        | 'means'
        | 'rotationsXyzw'
        | 'logScales'
        | 'logitOpacities'
        | 'dc'
        | 'sh';
    readonly scalarType: 'uint32le' | 'float32le';
    readonly componentCount: number;
    readonly byteOffset: number;
    readonly byteLength: number;
}

interface PackedSceneSnapshot {
    readonly format: typeof BINARY_SCENE_SNAPSHOT_FORMAT;
    readonly formatVersion: typeof BINARY_SCENE_SNAPSHOT_FORMAT_VERSION;
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

/**
 * The public format seam for Ticket 02A. The implementation intentionally
 * lands after the protocol document and red contract tests have been reviewed.
 */
const buildPackedSceneSnapshot = (
    _input: PackedSceneSnapshotInput
): PackedSceneSnapshot => {
    throw new Error('Binary SceneSnapshot Registration v1 is not implemented.');
};

const createBinarySceneSnapshotManifest = (
    _snapshot: PackedSceneSnapshot,
    _chunkByteLength = DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES
): BinarySceneSnapshotManifest => {
    throw new Error('Binary SceneSnapshot Registration v1 is not implemented.');
};

export {
    BINARY_SCENE_SNAPSHOT_FORMAT,
    BINARY_SCENE_SNAPSHOT_FORMAT_VERSION,
    DEFAULT_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    buildPackedSceneSnapshot,
    createBinarySceneSnapshotManifest
};

export type {
    BinarySceneSnapshotChunk,
    BinarySceneSnapshotManifest,
    PackedSceneSnapshot,
    PackedSceneSnapshotField,
    PackedSceneSnapshotInput,
    SceneSnapshotShFloatCount
};
