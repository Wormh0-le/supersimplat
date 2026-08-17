import { sha256Digest } from '../scene-snapshot-binary';
import type { MaskPolarity } from './mask-annotation';

// Ticket 04C: PromptState schema v2 shrinks the instance prompt contract to
// Positive/Negative Points plus at most one Positive Instance Box. v1
// artifacts (maskConstraints/textPrompts/negative boxes) fail closed on
// exact-key, schemaVersion, and digest-recompute validation.
export const promptStateSchemaVersion = 2;

export type PromptTool = 'positive-point' | 'negative-point' | 'positive-box';

export interface PointPrompt {
    readonly promptId: string;
    readonly polarity: MaskPolarity;
    readonly xPx: number;
    readonly yPx: number;
}

export interface BoxPrompt {
    readonly promptId: string;
    /** Positive Instance Box only; exclude polarity fails closed (§4). */
    readonly polarity: 'include';
    readonly x0Px: number;
    readonly y0Px: number;
    readonly x1Px: number;
    readonly y1Px: number;
}

export interface PromptState {
    readonly schemaVersion: typeof promptStateSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly revision: number;
    readonly points: readonly PointPrompt[];
    readonly boxes: readonly BoxPrompt[];
    readonly digest: string;
}

/**
 * The SAM 3 Image instance adapter capability record (04C contract §3). The
 * digest binds exactly the five current capability flags plus the compiler policy
 * version; removed prompt families are absent from the record entirely, so
 * old records with `unsupportedPromptReasons` fail closed.
 */
export interface PromptAdapterCapabilities {
    readonly positivePoints: boolean;
    readonly negativePoints: boolean;
    readonly positiveInstanceBox: boolean;
    readonly previousLogitsRefinement: boolean;
    readonly singlePointMultimask: boolean;
    readonly compilerPolicyVersion: string;
    readonly capabilityDigest: string;
}

type PromptStatePayload = Omit<PromptState, 'digest'>;

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;

const canonicalJson = (value: unknown): string => {
    if (Array.isArray(value)) {
        return `[${value.map(canonicalJson).join(',')}]`;
    }
    if (value !== null && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        return `{${Object.keys(record)
            .sort()
            .map(
                (key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`
            )
            .join(',')}}`;
    }
    return JSON.stringify(value);
};

/**
 * Canonical sorted JSON with plain JSON number spelling. Prompt identity and
 * the opaque logits-ref digest share this encoding (04C contract §4/§7).
 */
export const promptCanonicalJson = canonicalJson;

const promptStateDigest = (payload: PromptStatePayload): string => {
    return sha256Digest(encoder.encode(canonicalJson(payload)));
};

const freezePayload = (payload: PromptStatePayload): PromptStatePayload => {
    return Object.freeze({
        ...payload,
        points: Object.freeze(
            payload.points.map((point) => Object.freeze({ ...point }))
        ),
        boxes: Object.freeze(
            payload.boxes.map((box) => Object.freeze({ ...box }))
        )
    });
};

const publish = (payload: PromptStatePayload): PromptState => {
    const frozen = freezePayload(payload);
    return Object.freeze({
        ...frozen,
        digest: promptStateDigest(frozen)
    });
};

export const createEmptyPromptState = (
    viewId: string,
    rgbDigest: string
): PromptState => {
    return publish({
        schemaVersion: promptStateSchemaVersion,
        viewId,
        rgbDigest,
        revision: 0,
        points: [],
        boxes: []
    });
};

export const revisePromptState = (
    current: PromptState,
    prompts: {
        readonly points?: readonly PointPrompt[];
        readonly boxes?: readonly BoxPrompt[];
    }
): PromptState => {
    if (current.revision >= Number.MAX_SAFE_INTEGER) {
        throw new Error('AI Select Prompt revision cannot advance safely.');
    }
    // At most one Positive Instance Box exists: adding a box replaces it.
    const boxes = prompts.boxes ?? current.boxes;
    return publish({
        schemaVersion: promptStateSchemaVersion,
        viewId: current.viewId,
        rgbDigest: current.rgbDigest,
        revision: current.revision + 1,
        points: prompts.points ?? current.points,
        boxes: boxes.slice(-1)
    });
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const isPixel = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

const isPolarity = (value: unknown): value is MaskPolarity => {
    return value === 'include' || value === 'exclude';
};

const hasExactKeys = (
    value: Record<string, unknown>,
    required: readonly string[],
    optional: readonly string[] = []
): boolean => {
    const allowed = new Set([...required, ...optional]);
    return (
        required.every((key) => Object.hasOwn(value, key)) &&
        Object.keys(value).every((key) => allowed.has(key))
    );
};

export const isPromptState = (value: unknown): value is PromptState => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'schemaVersion',
            'viewId',
            'rgbDigest',
            'revision',
            'points',
            'boxes',
            'digest'
        ]) ||
        value.schemaVersion !== promptStateSchemaVersion ||
        !isNonEmptyString(value.viewId) ||
        typeof value.rgbDigest !== 'string' ||
        !digestPattern.test(value.rgbDigest) ||
        !Number.isSafeInteger(value.revision) ||
        (value.revision as number) < 0 ||
        typeof value.digest !== 'string' ||
        !digestPattern.test(value.digest) ||
        !Array.isArray(value.points) ||
        !Array.isArray(value.boxes) ||
        value.boxes.length > 1
    ) {
        return false;
    }
    const points = value.points.every(
        (point) =>
            isRecord(point) &&
            hasExactKeys(point, ['promptId', 'polarity', 'xPx', 'yPx']) &&
            isNonEmptyString(point.promptId) &&
            isPolarity(point.polarity) &&
            isPixel(point.xPx) &&
            isPixel(point.yPx)
    );
    // Boxes are Positive Instance only: exclude polarity fails closed.
    const boxes = value.boxes.every(
        (box) =>
            isRecord(box) &&
            hasExactKeys(box, [
                'promptId',
                'polarity',
                'x0Px',
                'y0Px',
                'x1Px',
                'y1Px'
            ]) &&
            isNonEmptyString(box.promptId) &&
            box.polarity === 'include' &&
            isPixel(box.x0Px) &&
            isPixel(box.y0Px) &&
            isPixel(box.x1Px) &&
            isPixel(box.y1Px) &&
            (box.x0Px as number) < (box.x1Px as number) &&
            (box.y0Px as number) < (box.y1Px as number)
    );
    if (!points || !boxes) {
        return false;
    }
    const promptIds = [...value.points, ...value.boxes].map(
        (prompt) => (prompt as { promptId: string }).promptId
    );
    if (new Set(promptIds).size !== promptIds.length) {
        return false;
    }
    const { digest, ...payload } = value;
    return promptStateDigest(payload as PromptStatePayload) === digest;
};

const capabilityPayload = (
    capabilities: Omit<PromptAdapterCapabilities, 'capabilityDigest'>
) => ({
    positivePoints: capabilities.positivePoints,
    negativePoints: capabilities.negativePoints,
    positiveInstanceBox: capabilities.positiveInstanceBox,
    previousLogitsRefinement: capabilities.previousLogitsRefinement,
    singlePointMultimask: capabilities.singlePointMultimask,
    compilerPolicyVersion: capabilities.compilerPolicyVersion
});

export const createPromptAdapterCapabilities = (
    capabilities: Omit<PromptAdapterCapabilities, 'capabilityDigest'>
): PromptAdapterCapabilities => {
    const payload = capabilityPayload(capabilities);
    return Object.freeze({
        ...payload,
        capabilityDigest: sha256Digest(encoder.encode(canonicalJson(payload)))
    });
};

const promptToolSupported = (
    tool: PromptTool,
    capabilities: Omit<PromptAdapterCapabilities, 'capabilityDigest'>
): boolean => {
    return tool === 'positive-point'
        ? capabilities.positivePoints
        : tool === 'negative-point'
          ? capabilities.negativePoints
          : capabilities.positiveInstanceBox;
};

export const isPromptAdapterCapabilities = (
    value: unknown
): value is PromptAdapterCapabilities => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'positivePoints',
            'negativePoints',
            'positiveInstanceBox',
            'previousLogitsRefinement',
            'singlePointMultimask',
            'compilerPolicyVersion',
            'capabilityDigest'
        ])
    ) {
        return false;
    }
    const booleanKeys = [
        'positivePoints',
        'negativePoints',
        'positiveInstanceBox',
        'previousLogitsRefinement',
        'singlePointMultimask'
    ] as const;
    if (
        !booleanKeys.every((key) => typeof value[key] === 'boolean') ||
        !isNonEmptyString(value.compilerPolicyVersion) ||
        typeof value.capabilityDigest !== 'string' ||
        !digestPattern.test(value.capabilityDigest)
    ) {
        return false;
    }
    const capabilityPayloadValue = value as unknown as Omit<
        PromptAdapterCapabilities,
        'capabilityDigest'
    >;
    const expected = createPromptAdapterCapabilities(capabilityPayloadValue);
    return expected.capabilityDigest === value.capabilityDigest;
};

export const promptToolCapabilityReason = (
    tool: PromptTool,
    capabilities: PromptAdapterCapabilities
): string | null => {
    return promptToolSupported(tool, capabilities)
        ? null
        : `The selected Prompt Adapter does not support ${tool}.`;
};

export const promptStateHasConstraints = (state: PromptState): boolean => {
    return state.points.length > 0 || state.boxes.length > 0;
};
