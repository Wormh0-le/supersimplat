import type { SceneSnapshot } from '../scene-snapshot';
import {
    areCameraBindingsEqual,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';

export interface AnchorRenderRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly snapshot: SceneSnapshot;
    readonly cameraBinding: CameraBinding;
}

export interface AnchorRgbArtifact {
    readonly pngBase64: string;
    readonly digest: string;
    readonly width: number;
    readonly height: number;
}

export interface AnchorRenderResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly viewId: 'anchor-view';
    readonly cameraBinding: CameraBinding;
    readonly rgb: AnchorRgbArtifact;
    readonly contributorDigest: string;
    readonly rendererId: 'gsplat';
}

export interface AISelectAnchorRenderer {
    renderAnchor(request: AnchorRenderRequest): Promise<AnchorRenderResponse>;
}

type UnknownRecord = Record<string, unknown>;

export interface PngDimensions {
    readonly width: number;
    readonly height: number;
}

interface ParsedPng {
    readonly dimensions: PngDimensions;
    readonly imageData: readonly Uint8Array[];
    readonly bitDepth: number;
    readonly colorType: number;
    readonly interlaceMethod: number;
}

const pngSignature = [137, 80, 78, 71, 13, 10, 26, 10];

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isBase64 = (value: unknown): value is string => {
    return (
        typeof value === 'string' &&
        value.length > 0 &&
        value.length % 4 === 0 &&
        /^[a-z0-9+/]*={0,2}$/i.test(value)
    );
};

const isPositiveSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) > 0;
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

/** Decode only the Companion-owned PNG bytes that cross the transport boundary. */
export const decodePngBase64 = (base64: string): Uint8Array<ArrayBuffer> => {
    if (typeof globalThis.atob !== 'function') {
        throw new Error('This editor context cannot decode an Anchor PNG artifact.');
    }
    const binary = globalThis.atob(base64);
    const bytes = new Uint8Array(new ArrayBuffer(binary.length));
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
};

const pngUint32 = (bytes: Uint8Array, offset: number): number => {
    return (
        bytes[offset] * 0x1000000 +
        bytes[offset + 1] * 0x10000 +
        bytes[offset + 2] * 0x100 +
        bytes[offset + 3]
    );
};

const pngChunkType = (bytes: Uint8Array, offset: number): string => {
    return String.fromCharCode(
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3]
    );
};

const pngCrc32 = (bytes: Uint8Array, start: number, end: number): number => {
    let crc = 0xffffffff;
    for (let index = start; index < end; index += 1) {
        crc ^= bytes[index];
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
};

const isSupportedPngEncoding = (bitDepth: number, colorType: number): boolean => {
    switch (colorType) {
        case 0:
            return [1, 2, 4, 8, 16].includes(bitDepth);
        case 2:
        case 4:
        case 6:
            return bitDepth === 8 || bitDepth === 16;
        case 3:
            return [1, 2, 4, 8].includes(bitDepth);
        default:
            return false;
    }
};

const pngChannels = (colorType: number): number => {
    switch (colorType) {
        case 0:
        case 3:
            return 1;
        case 2:
            return 3;
        case 4:
            return 2;
        case 6:
            return 4;
        default:
            throw new Error('Anchor PNG has an unsupported color type.');
    }
};

const parsePng = (bytes: Uint8Array): ParsedPng => {
    if (
        bytes.length < pngSignature.length ||
        !pngSignature.every((byte, index) => bytes[index] === byte)
    ) {
        throw new Error('Anchor RGB is not a PNG artifact.');
    }

    let dimensions: PngDimensions | null = null;
    let hasImageData = false;
    let imageDataEnded = false;
    let hasPalette = false;
    const imageData: Uint8Array[] = [];
    let bitDepth = 0;
    let colorType = 0;
    let interlaceMethod = 0;
    let offset = pngSignature.length;
    while (offset < bytes.length) {
        if (bytes.length - offset < 12) {
            throw new Error('Anchor PNG has a truncated chunk envelope.');
        }
        const length = pngUint32(bytes, offset);
        const typeOffset = offset + 4;
        const dataOffset = offset + 8;
        const checksumOffset = dataOffset + length;
        const nextOffset = checksumOffset + 4;
        if (nextOffset > bytes.length) {
            throw new Error('Anchor PNG has a truncated chunk payload.');
        }
        if (pngUint32(bytes, checksumOffset) !== pngCrc32(bytes, typeOffset, checksumOffset)) {
            throw new Error('Anchor PNG has an invalid chunk checksum.');
        }

        const type = pngChunkType(bytes, typeOffset);
        if (dimensions === null) {
            if (type !== 'IHDR' || length !== 13) {
                throw new Error('Anchor PNG must begin with one IHDR chunk.');
            }
            const width = pngUint32(bytes, dataOffset);
            const height = pngUint32(bytes, dataOffset + 4);
            if (!isPositiveSafeInteger(width) || !isPositiveSafeInteger(height)) {
                throw new Error('Anchor PNG dimensions must be positive integers.');
            }
            bitDepth = bytes[dataOffset + 8];
            colorType = bytes[dataOffset + 9];
            const compressionMethod = bytes[dataOffset + 10];
            const filterMethod = bytes[dataOffset + 11];
            interlaceMethod = bytes[dataOffset + 12];
            if (
                !isSupportedPngEncoding(bitDepth, colorType) ||
                compressionMethod !== 0 ||
                filterMethod !== 0 ||
                (interlaceMethod !== 0 && interlaceMethod !== 1)
            ) {
                throw new Error('Anchor PNG has unsupported image encoding metadata.');
            }
            dimensions = Object.freeze({ width, height });
        } else if (type === 'IHDR') {
            throw new Error('Anchor PNG must not contain multiple IHDR chunks.');
        }

        if (type === 'IDAT') {
            if (imageDataEnded) {
                throw new Error('Anchor PNG IDAT chunks must be contiguous.');
            }
            hasImageData = true;
            imageData.push(bytes.subarray(dataOffset, checksumOffset));
        } else if (type === 'PLTE') {
            if (
                hasImageData ||
                hasPalette ||
                length === 0 ||
                length % 3 !== 0 ||
                colorType === 0 ||
                colorType === 4 ||
                length / 3 > (1 << bitDepth)
            ) {
                throw new Error('Anchor PNG has an invalid palette chunk.');
            }
            hasPalette = true;
        } else if (hasImageData && type !== 'IEND') {
            imageDataEnded = true;
        }
        if (type === 'IEND') {
            if (length !== 0 || !hasImageData || (colorType === 3 && !hasPalette)) {
                throw new Error('Anchor PNG has an invalid IEND chunk.');
            }
            if (nextOffset !== bytes.length) {
                throw new Error('Anchor PNG has trailing bytes after IEND.');
            }
            return {
                dimensions,
                imageData,
                bitDepth,
                colorType,
                interlaceMethod
            };
        }
        offset = nextOffset;
    }
    throw new Error('Anchor PNG is missing its terminal IEND chunk.');
};

/**
 * Validate the immutable PNG envelope before a browser displays an
 * authoritative Artifact. The browser still checks its SHA-256 separately.
 */
export const parsePngDimensions = (bytes: Uint8Array): PngDimensions => {
    return parsePng(bytes).dimensions;
};

const concatenatePngImageData = (chunks: readonly Uint8Array[]): Uint8Array => {
    const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
    const result = new Uint8Array(length);
    let offset = 0;
    chunks.forEach((chunk) => {
        result.set(chunk, offset);
        offset += chunk.length;
    });
    return result;
};

const pngBlobPart = (bytes: Uint8Array): ArrayBuffer => {
    const copy = new Uint8Array(new ArrayBuffer(bytes.length));
    copy.set(bytes);
    return copy.buffer;
};

const validateInflatedPngImageData = async (png: ParsedPng): Promise<void> => {
    if (typeof globalThis.DecompressionStream !== 'function') {
        throw new Error('This editor context cannot decode an Anchor PNG artifact.');
    }
    if (png.interlaceMethod !== 0) {
        throw new Error('This editor context requires a native decoder for interlaced Anchor PNGs.');
    }
    try {
        const compressed = concatenatePngImageData(png.imageData);
        const compressedBlob = new Blob([pngBlobPart(compressed)]);
        const decompressor = new DecompressionStream('deflate');
        const stream = compressedBlob.stream().pipeThrough(decompressor);
        const decoded = new Uint8Array(await new Response(stream).arrayBuffer());
        const rowLength = Math.ceil(
            png.dimensions.width * pngChannels(png.colorType) * png.bitDepth / 8
        );
        if (decoded.length !== (rowLength + 1) * png.dimensions.height) {
            throw new Error('Anchor PNG image data has an invalid decoded length.');
        }
        for (let offset = 0; offset < decoded.length; offset += rowLength + 1) {
            if (decoded[offset] > 4) {
                throw new Error('Anchor PNG image data has an invalid filter byte.');
            }
        }
    } catch (error) {
        throw new Error('Anchor PNG image data is not decodable.');
    }
};

const assertDecodedDimensions = (
    dimensions: PngDimensions,
    width: number,
    height: number
): void => {
    if (width !== dimensions.width || height !== dimensions.height) {
        throw new Error('Anchor PNG decoder dimensions do not match its IHDR.');
    }
};

/**
 * Confirm that structurally valid PNG bytes can actually be decoded before
 * they become user-visible AI observation state. Native browser decoders are
 * authoritative; the stream fallback keeps non-DOM transport tests fail-closed.
 */
export const validatePngDecodable = async (
    bytes: Uint8Array
): Promise<PngDimensions> => {
    const png = parsePng(bytes);
    const blob = new Blob([pngBlobPart(bytes)], { type: 'image/png' });
    if (typeof globalThis.createImageBitmap === 'function') {
        try {
            const bitmap = await globalThis.createImageBitmap(blob);
            try {
                assertDecodedDimensions(png.dimensions, bitmap.width, bitmap.height);
            } finally {
                bitmap.close();
            }
            return png.dimensions;
        } catch (error) {
            throw new Error('Anchor PNG image data is not decodable.');
        }
    }
    if (typeof document !== 'undefined' && typeof URL.createObjectURL === 'function') {
        const image = document.createElement('img');
        const objectUrl = URL.createObjectURL(blob);
        try {
            if (typeof image.decode === 'function') {
                image.src = objectUrl;
                await image.decode();
            } else {
                const loaded = new Promise<void>((resolve, reject) => {
                    image.addEventListener('load', () => resolve(), { once: true });
                    image.addEventListener(
                        'error',
                        () => reject(new Error('Anchor PNG image data is not decodable.')),
                        { once: true }
                    );
                });
                image.src = objectUrl;
                await loaded;
            }
            assertDecodedDimensions(png.dimensions, image.naturalWidth, image.naturalHeight);
            return png.dimensions;
        } catch (error) {
            throw new Error('Anchor PNG image data is not decodable.');
        } finally {
            URL.revokeObjectURL(objectUrl);
        }
    }
    await validateInflatedPngImageData(png);
    return png.dimensions;
};

const actualPngDimensions = (base64: string): PngDimensions | null => {
    try {
        return parsePngDimensions(decodePngBase64(base64));
    } catch (error) {
        return null;
    }
};

export const isAnchorRenderRequest = (
    value: unknown
): value is AnchorRenderRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isRecord(value.target) &&
        isNonEmptyString(value.target.splatId) &&
        isRecord(value.snapshot) &&
        isNonEmptyString(value.snapshot.sceneId) &&
        isNonEmptyString(value.snapshot.sceneVersion) &&
        isCameraBinding(value.cameraBinding) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        value.snapshot.sceneId === value.target.splatId
    );
};

const isAnchorRgbArtifact = (value: unknown): value is AnchorRgbArtifact => {
    return (
        isRecord(value) &&
        isBase64(value.pngBase64) &&
        isDigest(value.digest) &&
        isPositiveSafeInteger(value.width) &&
        isPositiveSafeInteger(value.height)
    );
};

export const isAnchorRenderResponse = (
    value: unknown
): value is AnchorRenderResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.renderConfigVersion) &&
        value.viewId === 'anchor-view' &&
        isCameraBinding(value.cameraBinding) &&
        isAnchorRgbArtifact(value.rgb) &&
        isDigest(value.contributorDigest) &&
        value.rendererId === 'gsplat'
    );
};

export const anchorRenderResponseMatchesRequest = (
    response: AnchorRenderResponse,
    request: AnchorRenderRequest
): boolean => {
    const actualDimensions = actualPngDimensions(response.rgb.pngBase64);
    return (
        actualDimensions !== null &&
        response.requestBinding.targetContextId === request.requestBinding.targetContextId &&
        response.requestBinding.contextRevision === request.requestBinding.contextRevision &&
        areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) &&
        response.targetSplatId === request.target.splatId &&
        response.sceneId === request.snapshot.sceneId &&
        response.sceneVersion === request.snapshot.sceneVersion &&
        response.renderConfigVersion === request.snapshot.renderConfiguration.version &&
        areCameraBindingsEqual(response.cameraBinding, request.cameraBinding) &&
        actualDimensions.width === response.rgb.width &&
        actualDimensions.height === response.rgb.height &&
        response.rgb.width === request.cameraBinding.projection.width &&
        response.rgb.height === request.cameraBinding.projection.height
    );
};
