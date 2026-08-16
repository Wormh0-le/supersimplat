import { sha256Digest, sha256DigestParts } from '../scene-snapshot-binary';

type SemanticValue = string | number | boolean;

const encoder = new TextEncoder();
const MEMBERSHIP_CHUNK_BYTES = 64 * 1024;

const assertNamespace = (namespace: string): void => {
    if (namespace.trim().length === 0) {
        throw new Error(
            'AI Select dependency fingerprints require a namespace.'
        );
    }
};

const canonicalValue = (value: SemanticValue): string => {
    if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
            throw new Error(
                'AI Select dependency fingerprints require finite numbers.'
            );
        }
        return `n:${Object.is(value, -0) ? 0 : value}`;
    }
    return typeof value === 'boolean'
        ? `b:${value ? 1 : 0}`
        : `s:${value.length}:${value}`;
};

/** Fingerprint a small ordered semantic record, independent of edit ordinals. */
export const semanticValueFingerprint = (
    namespace: string,
    values: readonly SemanticValue[]
): string => {
    assertNamespace(namespace);
    const digest = sha256Digest(
        encoder.encode(values.map(canonicalValue).join('\u0000'))
    );
    return `${namespace}:${digest}`;
};

/**
 * Fingerprint only deleted membership. Native selection and lock flags are
 * intentionally masked out so editor-only state cannot suspend AI Select.
 */
export const semanticDeletedMembershipFingerprint = (
    state: ArrayLike<number>,
    deletedMask: number,
    contentIdentity: string
): string => {
    if (!Number.isInteger(deletedMask) || deletedMask <= 0) {
        throw new Error(
            'AI Select Gaussian membership requires a deleted-state mask.'
        );
    }
    function* parts(): Iterable<Uint8Array> {
        yield encoder.encode(
            `membership\u0000${contentIdentity}\u0000${state.length}\u0000`
        );
        const chunk = new Uint8Array(
            Math.min(MEMBERSHIP_CHUNK_BYTES, Math.max(1, state.length))
        );
        for (let offset = 0; offset < state.length;) {
            const count = Math.min(chunk.length, state.length - offset);
            for (let index = 0; index < count; index += 1) {
                chunk[index] =
                    (state[offset + index] & deletedMask) === 0 ? 0 : 1;
            }
            yield chunk.subarray(0, count);
            offset += count;
        }
    }
    return `membership:${sha256DigestParts(parts())}`;
};

export interface SemanticGeometryFingerprintInput {
    readonly contentIdentity: string;
    readonly transformIndices: ArrayLike<number>;
    readonly writeTransform: (
        transformIndex: number,
        target: Float32Array
    ) => void;
}

/**
 * Fingerprint each Gaussian's effective local 3x4 transform. Palette slot
 * numbers are representation details: exact inverse edits restore this token
 * even when native history used different intermediate slots.
 */
export const semanticGeometryFingerprint = (
    input: SemanticGeometryFingerprintInput
): string => {
    function* parts(): Iterable<Uint8Array> {
        yield encoder.encode(
            `geometry\u0000${input.contentIdentity}\u0000${input.transformIndices.length}\u0000`
        );
        const transform = new Float32Array(12);
        const bytes = new Uint8Array(transform.buffer);
        for (
            let gaussianIndex = 0;
            gaussianIndex < input.transformIndices.length;
            gaussianIndex += 1
        ) {
            input.writeTransform(
                input.transformIndices[gaussianIndex] ?? 0,
                transform
            );
            yield bytes;
        }
    }
    return `geometry:${sha256DigestParts(parts())}`;
};
