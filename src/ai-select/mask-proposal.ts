import { sha256Digest } from '../scene-snapshot-binary';
import {
    decodeMaskBitsetBase64,
    isMaskArtifact,
    type MaskArtifact
} from './mask-annotation';

export const autoMaskProposalSetSchemaVersion = 1;
export const autoMaskProposalPolicyVersion =
    'auto-mask-proposals/bounded-source-order-v1';
export const maximumAutoMaskProposalCount = 4;

export interface PromptConsistencyFacts {
    readonly positivePointsSatisfied: boolean;
    readonly negativePointsSatisfied: boolean;
    readonly positiveBoxesSatisfied?: boolean;
    readonly negativeBoxesSatisfied?: boolean;
    readonly maskConstraintsSatisfied?: boolean;
    readonly textConstraintsSatisfied?: boolean;
}

export interface AutoMaskProposal {
    readonly proposalId: string;
    readonly mask: MaskArtifact;
    readonly sourceIndex: number;
    readonly modelScore?: number;
    readonly modelScoreSemantics?: string;
    readonly promptConsistency: PromptConsistencyFacts;
}

export interface ProposalTruncationRecord {
    readonly originalCount: number;
    readonly retainedCount: number;
    readonly policy: string;
}

export interface AutoMaskProposalSet {
    readonly schemaVersion: typeof autoMaskProposalSetSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptStateDigest: string;
    readonly modelManifestDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly proposalPolicyVersion: string;
    readonly proposalAttemptId: string;
    readonly proposals: readonly AutoMaskProposal[];
    readonly truncation?: ProposalTruncationRecord;
    readonly digest: string;
}

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const canonicalJson = (value: unknown): string => {
    if (Array.isArray(value)) {
        return `[${value.map(canonicalJson).join(',')}]`;
    }
    if (value !== null && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        return `{${Object.keys(record)
            .filter((key) => record[key] !== undefined)
            .sort()
            .map(
                (key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`
            )
            .join(',')}}`;
    }
    return JSON.stringify(value);
};

export const autoMaskProposalSetDigest = (
    value: Omit<AutoMaskProposalSet, 'digest'>
): string => {
    return sha256Digest(encoder.encode(canonicalJson(value)));
};

const artifactDigestMatchesBytes = (artifact: MaskArtifact): boolean => {
    try {
        return (
            sha256Digest(decodeMaskBitsetBase64(artifact.data)) ===
            artifact.digest
        );
    } catch {
        return false;
    }
};

const exactBooleanFacts = (value: unknown): boolean => {
    if (!isRecord(value)) {
        return false;
    }
    const required = ['positivePointsSatisfied', 'negativePointsSatisfied'];
    const optional = [
        'positiveBoxesSatisfied',
        'negativeBoxesSatisfied',
        'maskConstraintsSatisfied',
        'textConstraintsSatisfied'
    ];
    const allowed = new Set([...required, ...optional]);
    return (
        required.every((key) => typeof value[key] === 'boolean') &&
        Object.keys(value).every(
            (key) =>
                allowed.has(key) &&
                (value[key] === undefined || typeof value[key] === 'boolean')
        )
    );
};

export const isAutoMaskProposalSet = (
    value: unknown
): value is AutoMaskProposalSet => {
    if (
        !isRecord(value) ||
        value.schemaVersion !== autoMaskProposalSetSchemaVersion ||
        !isNonEmptyString(value.viewId) ||
        typeof value.rgbDigest !== 'string' ||
        !digestPattern.test(value.rgbDigest) ||
        typeof value.promptStateDigest !== 'string' ||
        !digestPattern.test(value.promptStateDigest) ||
        !isNonEmptyString(value.modelManifestDigest) ||
        typeof value.adapterCapabilityDigest !== 'string' ||
        !digestPattern.test(value.adapterCapabilityDigest) ||
        !isNonEmptyString(value.proposalPolicyVersion) ||
        !isNonEmptyString(value.proposalAttemptId) ||
        !Array.isArray(value.proposals) ||
        value.proposals.length > maximumAutoMaskProposalCount ||
        typeof value.digest !== 'string' ||
        !digestPattern.test(value.digest)
    ) {
        return false;
    }
    const proposalIds = new Set<string>();
    const sourceIndexes = new Set<number>();
    for (const proposal of value.proposals) {
        if (
            !isRecord(proposal) ||
            !isNonEmptyString(proposal.proposalId) ||
            proposalIds.has(proposal.proposalId) ||
            !Number.isSafeInteger(proposal.sourceIndex) ||
            (proposal.sourceIndex as number) < 0 ||
            sourceIndexes.has(proposal.sourceIndex as number) ||
            !isMaskArtifact(proposal.mask) ||
            !artifactDigestMatchesBytes(proposal.mask) ||
            !exactBooleanFacts(proposal.promptConsistency) ||
            (proposal.modelScore !== undefined &&
                (typeof proposal.modelScore !== 'number' ||
                    !Number.isFinite(proposal.modelScore))) ||
            (proposal.modelScoreSemantics !== undefined &&
                !isNonEmptyString(proposal.modelScoreSemantics))
        ) {
            return false;
        }
        proposalIds.add(proposal.proposalId);
        sourceIndexes.add(proposal.sourceIndex as number);
    }
    if (
        value.truncation !== undefined &&
        (!isRecord(value.truncation) ||
            !Number.isSafeInteger(value.truncation.originalCount) ||
            !Number.isSafeInteger(value.truncation.retainedCount) ||
            (value.truncation.originalCount as number) <=
                (value.truncation.retainedCount as number) ||
            value.truncation.retainedCount !== value.proposals.length ||
            !isNonEmptyString(value.truncation.policy))
    ) {
        return false;
    }
    const { digest, ...payload } = value;
    return (
        autoMaskProposalSetDigest(
            payload as Omit<AutoMaskProposalSet, 'digest'>
        ) === digest
    );
};
