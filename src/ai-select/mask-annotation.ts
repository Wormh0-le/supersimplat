import { sha256Digest } from '../scene-snapshot-binary';

/**
 * The packed-mask wire encoding shared with the Companion. Bits are packed
 * LSB-first in row-major pixel order (`y * width + x`), base64-encoded for
 * transport, and bound to their bytes by a `sha256:` digest.
 */
export const maskBitsetEncoding = 'bitset-lsb-v1';

export type MaskPolarity = 'include' | 'exclude';

/** A single point prompt in integer RGB pixel coordinates. */
export interface MaskPrompt {
    readonly promptId: string;
    readonly xPx: number;
    readonly yPx: number;
    readonly polarity: MaskPolarity;
}

export type MaskSource =
    'single-frame-sam' | 'propagated' | 'manual' | 'hybrid';

/**
 * Editing Masks stay `draft` until Confirm Mask publishes them as
 * `user-confirmed`. Automatic cross-view Masks publish directly as Stable
 * with the quality label supplied by the Companion's evidence-backed Mask
 * Review (`auto-good` or the fail-closed `auto-review`, the latter Excluded
 * from Lift by default). Nothing fabricates a quality label.
 */
export type MaskLifecycleStatus =
    'draft' | 'auto-good' | 'auto-review' | 'user-confirmed';

export interface MaskArtifact {
    readonly encoding: typeof maskBitsetEncoding;
    readonly width: number;
    readonly height: number;
    readonly data: string;
    /** The `sha256:` digest of the decoded bitset bytes. */
    readonly digest: string;
}

/**
 * One immutable, versioned 2D annotation bound to the exact authoritative RGB
 * digest it was authored from (Final Spec v1.1 §10). It never carries 3D or
 * Gaussian identity.
 */
export interface MaskAnnotation {
    readonly maskId: string;
    readonly viewId: string;
    readonly source: MaskSource;
    readonly status: MaskLifecycleStatus;
    readonly artifact: MaskArtifact;
    readonly prompts?: readonly MaskPrompt[];
    readonly parentMaskId?: string;
    readonly createdFromRgbDigest: string;
}

export interface BrushStroke {
    readonly xPx: number;
    readonly yPx: number;
    readonly radiusPx: number;
    readonly mode: 'add' | 'erase';
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isPositiveSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) > 0;
};

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

const isBase64 = (value: unknown): value is string => {
    return (
        typeof value === 'string' &&
        value.length > 0 &&
        value.length % 4 === 0 &&
        /^[a-z0-9+/]*={0,2}$/i.test(value)
    );
};

export const isMaskPrompt = (value: unknown): value is MaskPrompt => {
    return (
        isRecord(value) &&
        isNonEmptyString(value.promptId) &&
        isNonNegativeSafeInteger(value.xPx) &&
        isNonNegativeSafeInteger(value.yPx) &&
        (value.polarity === 'include' || value.polarity === 'exclude')
    );
};

export const maskBitsetByteLength = (width: number, height: number): number => {
    return Math.ceil((width * height) / 8);
};

const decodedBase64Length = (data: string): number => {
    let length = (data.length / 4) * 3;
    if (data.endsWith('==')) {
        length -= 2;
    } else if (data.endsWith('=')) {
        length -= 1;
    }
    return length;
};

const base64Decode = (data: string): Uint8Array<ArrayBuffer> => {
    if (typeof globalThis.atob !== 'function') {
        throw new Error(
            'This editor context cannot decode an AI Select Mask artifact.'
        );
    }
    const binary = globalThis.atob(data);
    const bytes = new Uint8Array(new ArrayBuffer(binary.length));
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
};

/** Decode the base64 payload of a Mask bitset without validating it. */
export const decodeMaskBitsetBase64 = (
    data: string
): Uint8Array<ArrayBuffer> => {
    return base64Decode(data);
};

const BASE64_CHUNK_SIZE = 0x8000;

const base64Encode = (bytes: Uint8Array): string => {
    if (typeof globalThis.btoa !== 'function') {
        throw new Error(
            'This editor context cannot encode an AI Select Mask artifact.'
        );
    }
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += BASE64_CHUNK_SIZE) {
        binary += String.fromCharCode(
            ...bytes.subarray(offset, offset + BASE64_CHUNK_SIZE)
        );
    }
    return globalThis.btoa(binary);
};

/** The unused tail bits of the final byte must stay zero on the wire. */
const hasCleanTrailingBits = (
    bytes: Uint8Array,
    width: number,
    height: number
): boolean => {
    const pixelCount = width * height;
    const usedBits = pixelCount % 8;
    if (usedBits === 0 || bytes.length === 0) {
        return true;
    }
    const mask = 0xff << usedBits;
    return (bytes[bytes.length - 1] & mask) === 0;
};

/**
 * Validate one Mask artifact crossing the transport boundary. An empty
 * foreground is structurally legal: Editing Masks may be empty, and Anchor
 * validation (Ticket 05) owns the nearly-empty Stable Mask gate.
 */
export const isMaskArtifact = (value: unknown): value is MaskArtifact => {
    if (
        !isRecord(value) ||
        value.encoding !== maskBitsetEncoding ||
        !isPositiveSafeInteger(value.width) ||
        !isPositiveSafeInteger(value.height) ||
        !isBase64(value.data) ||
        !isDigest(value.digest)
    ) {
        return false;
    }
    const width = value.width as number;
    const height = value.height as number;
    if (
        decodedBase64Length(value.data) !== maskBitsetByteLength(width, height)
    ) {
        return false;
    }
    const bytes = base64Decode(value.data as string);
    return hasCleanTrailingBits(bytes, width, height);
};

export const isMaskAnnotation = (value: unknown): value is MaskAnnotation => {
    return (
        isRecord(value) &&
        isNonEmptyString(value.maskId) &&
        isNonEmptyString(value.viewId) &&
        (value.source === 'single-frame-sam' ||
            value.source === 'propagated' ||
            value.source === 'manual' ||
            value.source === 'hybrid') &&
        (value.status === 'draft' ||
            value.status === 'auto-good' ||
            value.status === 'auto-review' ||
            value.status === 'user-confirmed') &&
        isMaskArtifact(value.artifact) &&
        (value.prompts === undefined ||
            (Array.isArray(value.prompts) &&
                value.prompts.every(isMaskPrompt))) &&
        (value.parentMaskId === undefined ||
            isNonEmptyString(value.parentMaskId)) &&
        isDigest(value.createdFromRgbDigest)
    );
};

/** Decode and digest-verify a validated Mask artifact into packed bytes. */
export const decodeMaskArtifact = (
    artifact: MaskArtifact
): Uint8Array<ArrayBuffer> => {
    const bytes = base64Decode(artifact.data);
    if (
        bytes.length !== maskBitsetByteLength(artifact.width, artifact.height)
    ) {
        throw new Error(
            'AI Select Mask artifact has an invalid bitset length.'
        );
    }
    if (sha256Digest(bytes) !== artifact.digest) {
        throw new Error(
            'AI Select Mask artifact bytes do not match their digest.'
        );
    }
    return bytes;
};

const artifactFromBytes = (
    bytes: Uint8Array,
    width: number,
    height: number
): MaskArtifact => {
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: base64Encode(bytes),
        digest: sha256Digest(bytes)
    });
};

export const createEmptyMaskArtifact = (
    width: number,
    height: number
): MaskArtifact => {
    if (!isPositiveSafeInteger(width) || !isPositiveSafeInteger(height)) {
        throw new Error(
            'AI Select Mask dimensions must be positive safe integers.'
        );
    }
    return artifactFromBytes(
        new Uint8Array(maskBitsetByteLength(width, height)),
        width,
        height
    );
};

const isBrushStroke = (value: unknown): value is BrushStroke => {
    return (
        isRecord(value) &&
        isNonNegativeSafeInteger(value.xPx) &&
        isNonNegativeSafeInteger(value.yPx) &&
        isPositiveSafeInteger(value.radiusPx) &&
        (value.mode === 'add' || value.mode === 'erase')
    );
};

/**
 * Apply every stamp in one gesture with one decode and one artifact digest.
 * Callers can therefore interpolate densely without reprocessing the whole
 * Mask for every sample.
 */
export const applyBrushStrokes = (
    artifact: MaskArtifact,
    strokes: readonly BrushStroke[]
): MaskArtifact => {
    if (!isMaskArtifact(artifact)) {
        throw new Error(
            'AI Select brush editing requires a valid Mask artifact.'
        );
    }
    if (strokes.length === 0 || !strokes.every(isBrushStroke)) {
        throw new Error(
            'AI Select brush strokes need integer pixel coordinates, a positive radius, and an add/erase mode.'
        );
    }
    if (
        strokes.some(
            (stroke) =>
                stroke.xPx >= artifact.width || stroke.yPx >= artifact.height
        )
    ) {
        throw new Error(
            'AI Select brush strokes must land inside the Mask artifact bounds.'
        );
    }
    const bytes = decodeMaskArtifact(artifact);
    const { width, height } = artifact;
    for (const stroke of strokes) {
        const radiusSquared = stroke.radiusPx * stroke.radiusPx;
        const minX = Math.max(0, stroke.xPx - stroke.radiusPx);
        const maxX = Math.min(width - 1, stroke.xPx + stroke.radiusPx);
        const minY = Math.max(0, stroke.yPx - stroke.radiusPx);
        const maxY = Math.min(height - 1, stroke.yPx + stroke.radiusPx);
        for (let y = minY; y <= maxY; y += 1) {
            for (let x = minX; x <= maxX; x += 1) {
                const dx = x - stroke.xPx;
                const dy = y - stroke.yPx;
                if (dx * dx + dy * dy > radiusSquared) {
                    continue;
                }
                const index = y * width + x;
                if (stroke.mode === 'add') {
                    bytes[index >> 3] |= 1 << (index % 8);
                } else {
                    bytes[index >> 3] &= ~(1 << (index % 8));
                }
            }
        }
    }
    return artifactFromBytes(bytes, width, height);
};

/** Apply one local brush stamp through the gesture-capable implementation. */
export const applyBrushStroke = (
    artifact: MaskArtifact,
    stroke: BrushStroke
): MaskArtifact => {
    return applyBrushStrokes(artifact, [stroke]);
};
