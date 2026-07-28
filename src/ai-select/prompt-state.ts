import { sha256Digest } from '../scene-snapshot-binary';
import {
    isMaskArtifact,
    type MaskArtifact,
    type MaskPolarity
} from './mask-annotation';

export const promptStateSchemaVersion = 1;

export type PromptTool =
    | 'positive-point'
    | 'negative-point'
    | 'positive-box'
    | 'negative-box'
    | 'positive-mask-constraint'
    | 'negative-mask-constraint'
    | 'positive-text'
    | 'negative-text';

export interface PointPrompt {
    readonly promptId: string;
    readonly polarity: MaskPolarity;
    readonly xPx: number;
    readonly yPx: number;
}

export interface BoxPrompt {
    readonly promptId: string;
    readonly polarity: MaskPolarity;
    readonly x0Px: number;
    readonly y0Px: number;
    readonly x1Px: number;
    readonly y1Px: number;
}

export interface MaskConstraintPrompt {
    readonly promptId: string;
    readonly polarity: MaskPolarity;
    readonly artifact: MaskArtifact;
}

export interface TextPrompt {
    readonly promptId: string;
    readonly polarity: MaskPolarity;
    readonly text: string;
    readonly locale?: string;
}

export interface PromptState {
    readonly schemaVersion: typeof promptStateSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly revision: number;
    readonly points: readonly PointPrompt[];
    readonly boxes: readonly BoxPrompt[];
    readonly maskConstraints: readonly MaskConstraintPrompt[];
    readonly textPrompts: readonly TextPrompt[];
    readonly digest: string;
}

export interface PromptAdapterCapabilities {
    readonly points: boolean;
    readonly negativePoints: boolean;
    readonly boxes: boolean;
    readonly negativeBoxes: boolean;
    readonly maskInput: boolean;
    readonly negativeMaskConstraints: boolean;
    readonly text: boolean;
    readonly negativeText: boolean;
    readonly multiCandidateOutput: boolean;
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

const promptStateDigest = (payload: PromptStatePayload): string => {
    return sha256Digest(encoder.encode(canonicalJson(payload)));
};

const copyArtifact = (artifact: MaskArtifact): MaskArtifact => {
    return Object.freeze({
        encoding: artifact.encoding,
        width: artifact.width,
        height: artifact.height,
        data: artifact.data,
        digest: artifact.digest
    });
};

const freezePayload = (payload: PromptStatePayload): PromptStatePayload => {
    return Object.freeze({
        ...payload,
        points: Object.freeze(
            payload.points.map((point) => Object.freeze({ ...point }))
        ),
        boxes: Object.freeze(
            payload.boxes.map((box) => Object.freeze({ ...box }))
        ),
        maskConstraints: Object.freeze(
            payload.maskConstraints.map((constraint) =>
                Object.freeze({
                    ...constraint,
                    artifact: copyArtifact(constraint.artifact)
                })
            )
        ),
        textPrompts: Object.freeze(
            payload.textPrompts.map((prompt) => Object.freeze({ ...prompt }))
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
        boxes: [],
        maskConstraints: [],
        textPrompts: []
    });
};

export const revisePromptState = (
    current: PromptState,
    prompts: {
        readonly points?: readonly PointPrompt[];
        readonly boxes?: readonly BoxPrompt[];
        readonly maskConstraints?: readonly MaskConstraintPrompt[];
        readonly textPrompts?: readonly TextPrompt[];
    }
): PromptState => {
    if (current.revision >= Number.MAX_SAFE_INTEGER) {
        throw new Error('AI Select Prompt revision cannot advance safely.');
    }
    return publish({
        schemaVersion: promptStateSchemaVersion,
        viewId: current.viewId,
        rgbDigest: current.rgbDigest,
        revision: current.revision + 1,
        points: prompts.points ?? current.points,
        boxes: prompts.boxes ?? current.boxes,
        maskConstraints: prompts.maskConstraints ?? current.maskConstraints,
        textPrompts: prompts.textPrompts ?? current.textPrompts
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
            'maskConstraints',
            'textPrompts',
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
        !Array.isArray(value.maskConstraints) ||
        !Array.isArray(value.textPrompts)
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
            isPolarity(box.polarity) &&
            isPixel(box.x0Px) &&
            isPixel(box.y0Px) &&
            isPixel(box.x1Px) &&
            isPixel(box.y1Px) &&
            (box.x0Px as number) < (box.x1Px as number) &&
            (box.y0Px as number) < (box.y1Px as number)
    );
    const constraints = value.maskConstraints.every(
        (constraint) =>
            isRecord(constraint) &&
            hasExactKeys(constraint, ['promptId', 'polarity', 'artifact']) &&
            isNonEmptyString(constraint.promptId) &&
            isPolarity(constraint.polarity) &&
            isMaskArtifact(constraint.artifact)
    );
    const texts = value.textPrompts.every(
        (prompt) =>
            isRecord(prompt) &&
            hasExactKeys(
                prompt,
                ['promptId', 'polarity', 'text'],
                ['locale']
            ) &&
            isNonEmptyString(prompt.promptId) &&
            isPolarity(prompt.polarity) &&
            isNonEmptyString(prompt.text) &&
            (prompt.locale === undefined || isNonEmptyString(prompt.locale))
    );
    if (!points || !boxes || !constraints || !texts) {
        return false;
    }
    const promptIds = [
        ...value.points,
        ...value.boxes,
        ...value.maskConstraints,
        ...value.textPrompts
    ].map((prompt) => (prompt as { promptId: string }).promptId);
    if (new Set(promptIds).size !== promptIds.length) {
        return false;
    }
    const { digest, ...payload } = value;
    return promptStateDigest(payload as PromptStatePayload) === digest;
};

const capabilityPayload = (
    capabilities: Omit<PromptAdapterCapabilities, 'capabilityDigest'>
) => ({
    points: capabilities.points,
    negativePoints: capabilities.negativePoints,
    boxes: capabilities.boxes,
    negativeBoxes: capabilities.negativeBoxes,
    maskInput: capabilities.maskInput,
    negativeMaskConstraints: capabilities.negativeMaskConstraints,
    text: capabilities.text,
    negativeText: capabilities.negativeText,
    multiCandidateOutput: capabilities.multiCandidateOutput
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

export const isPromptAdapterCapabilities = (
    value: unknown
): value is PromptAdapterCapabilities => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'points',
            'negativePoints',
            'boxes',
            'negativeBoxes',
            'maskInput',
            'negativeMaskConstraints',
            'text',
            'negativeText',
            'multiCandidateOutput',
            'capabilityDigest'
        ])
    ) {
        return false;
    }
    const booleanKeys = [
        'points',
        'negativePoints',
        'boxes',
        'negativeBoxes',
        'maskInput',
        'negativeMaskConstraints',
        'text',
        'negativeText',
        'multiCandidateOutput'
    ] as const;
    if (
        !booleanKeys.every((key) => typeof value[key] === 'boolean') ||
        typeof value.capabilityDigest !== 'string' ||
        !digestPattern.test(value.capabilityDigest)
    ) {
        return false;
    }
    const expected = createPromptAdapterCapabilities(
        value as unknown as Omit<PromptAdapterCapabilities, 'capabilityDigest'>
    );
    return expected.capabilityDigest === value.capabilityDigest;
};

export const promptToolCapabilityReason = (
    tool: PromptTool,
    capabilities: PromptAdapterCapabilities
): string | null => {
    const supported =
        tool === 'positive-point'
            ? capabilities.points
            : tool === 'negative-point'
              ? capabilities.points && capabilities.negativePoints
              : tool === 'positive-box'
                ? capabilities.boxes
                : tool === 'negative-box'
                  ? capabilities.boxes && capabilities.negativeBoxes
                  : tool === 'positive-mask-constraint'
                    ? capabilities.maskInput
                    : tool === 'negative-mask-constraint'
                      ? capabilities.maskInput &&
                        capabilities.negativeMaskConstraints
                      : tool === 'positive-text'
                        ? capabilities.text
                        : capabilities.text && capabilities.negativeText;
    return supported
        ? null
        : `The selected Prompt Adapter does not support ${tool}.`;
};

export const promptStateHasConstraints = (state: PromptState): boolean => {
    return (
        state.points.length > 0 ||
        state.boxes.length > 0 ||
        state.maskConstraints.length > 0 ||
        state.textPrompts.length > 0
    );
};
