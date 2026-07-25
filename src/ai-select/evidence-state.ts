/**
 * Per-view Evidence lifecycle state. Evidence is a derived artifact that may
 * exist only after a Stable Mask; it is independent from RGB readiness and
 * from Mask lifecycle (Final Spec v1.1 §§7, 11). This module owns identity
 * and invalidation only — Ticket 20 introduces the production P/N/V kernel
 * that produces the artifacts these identities describe.
 */
export type EvidenceStatus =
    'not-requested' | 'pending' | 'ready' | 'stale' | 'failed';

/**
 * The versioned Evidence Policy identity bound into per-view Evidence
 * dependency identities. No production Evidence exists at this stage; the
 * seam exists so the production P/N/V path invalidates artifacts by exact
 * policy identity without a later contract change. It is a version identity,
 * not a calibrated policy digest.
 */
export const aiSelectEvidencePolicyVersion = 'evidence-policy/pnv-v0';

/**
 * The exact dependency identity one per-view Evidence artifact binds. RGB
 * digest already pins the CameraBinding and target dependency of the
 * authoritative render; Working Set tokens and raster/evidence kernel
 * identity join this record with the production Evidence path.
 */
export interface EvidenceDependencyIdentity {
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly stableMaskDigest: string;
    readonly evidencePolicyDigest: string;
}

type RecordedEvidenceStatus = 'pending' | 'ready' | 'failed';

interface EvidenceRecord {
    readonly identity: EvidenceDependencyIdentity;
    readonly status: RecordedEvidenceStatus;
    readonly errorMessage?: string;
}

/** The derived per-view Evidence surface for one current input identity. */
export interface ViewEvidenceState {
    readonly viewId: string;
    readonly status: EvidenceStatus;
    /** The identity of the last produced/attempted artifact, for inspection. */
    readonly artifactIdentity?: EvidenceDependencyIdentity;
    readonly errorMessage?: string;
}

export const areEvidenceIdentitiesEqual = (
    left: EvidenceDependencyIdentity | null,
    right: EvidenceDependencyIdentity | null
): boolean => {
    if (left === null || right === null) {
        return left === right;
    }
    return (
        left.viewId === right.viewId &&
        left.rgbDigest === right.rgbDigest &&
        left.stableMaskDigest === right.stableMaskDigest &&
        left.evidencePolicyDigest === right.evidencePolicyDigest
    );
};

/**
 * Derive the current Evidence status from the last recorded attempt. A ready
 * or pending artifact whose exact RGB/Mask/policy identity no longer matches
 * is stale; a failure bound to superseded inputs reads as not-requested so it
 * never masks the current input state.
 */
export const deriveEvidenceStatus = (
    record: EvidenceRecord | null,
    currentIdentity: EvidenceDependencyIdentity | null
): EvidenceStatus => {
    if (record === null) {
        return 'not-requested';
    }
    if (areEvidenceIdentitiesEqual(record.identity, currentIdentity)) {
        return record.status;
    }
    return record.status === 'failed' ? 'not-requested' : 'stale';
};

const copyIdentity = (
    identity: EvidenceDependencyIdentity
): EvidenceDependencyIdentity => {
    return Object.freeze({
        viewId: identity.viewId,
        rgbDigest: identity.rgbDigest,
        stableMaskDigest: identity.stableMaskDigest,
        evidencePolicyDigest: identity.evidencePolicyDigest
    });
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const assertIdentity = (
    identity: EvidenceDependencyIdentity
): EvidenceDependencyIdentity => {
    if (
        !isNonEmptyString(identity?.viewId) ||
        !isDigest(identity.rgbDigest) ||
        !isDigest(identity.stableMaskDigest) ||
        !isNonEmptyString(identity.evidencePolicyDigest)
    ) {
        throw new Error(
            'AI Select Evidence requires a complete RGB/Mask/policy dependency identity.'
        );
    }
    return identity;
};

/**
 * Records the latest per-view Evidence attempt. Records are replaced
 * atomically per view; a failure never mutates Mask, RGB, or any other
 * view's Evidence state.
 */
export class PerViewEvidenceRegistry {
    private readonly records = new Map<string, EvidenceRecord>();

    markPending(identity: EvidenceDependencyIdentity): void {
        this.replace(assertIdentity(identity), { status: 'pending' });
    }

    markReady(identity: EvidenceDependencyIdentity): void {
        this.replace(assertIdentity(identity), { status: 'ready' });
    }

    markFailed(identity: EvidenceDependencyIdentity, message: string): void {
        this.replace(assertIdentity(identity), {
            status: 'failed',
            errorMessage:
                typeof message === 'string' && message.trim().length > 0
                    ? message
                    : 'AI Select Evidence production failed.'
        });
    }

    statusFor(
        viewId: string,
        currentIdentity: EvidenceDependencyIdentity | null
    ): ViewEvidenceState {
        const record = this.records.get(viewId) ?? null;
        const status = deriveEvidenceStatus(record, currentIdentity);
        return Object.freeze({
            viewId,
            status,
            ...(record === null || status === 'not-requested'
                ? {}
                : { artifactIdentity: copyIdentity(record.identity) }),
            ...(record?.errorMessage === undefined || status === 'not-requested'
                ? {}
                : { errorMessage: record.errorMessage })
        });
    }

    disposeView(viewId: string): void {
        this.records.delete(viewId);
    }

    private replace(
        identity: EvidenceDependencyIdentity,
        outcome:
            | { readonly status: 'pending' | 'ready' }
            | { readonly status: 'failed'; readonly errorMessage: string }
    ): void {
        this.records.set(
            identity.viewId,
            Object.freeze({
                identity: copyIdentity(identity),
                ...outcome
            })
        );
    }
}
