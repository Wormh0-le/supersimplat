import type { AIViewParticipation } from './ai-view';
import type { GeneratedViewMaskQuality } from './generated-view-controller';
import type { ImageInstancePromptArtifact } from './image-instance-mask';
import type { AISelectMaskState } from './mask-controller';
import { hasSemanticEditingMaskChange } from './mask-registry';

export type InspectorParticipationToggle = 'include' | 'exclude' | null;

export interface ViewInspectorPresentationInput {
    readonly viewId: string;
    readonly rgbDigest?: string;
    readonly quality: GeneratedViewMaskQuality;
    readonly participation: AIViewParticipation;
    readonly participationToggle: InspectorParticipationToggle;
    readonly actionableIssues: readonly string[];
    readonly maskState: Pick<
        AISelectMaskState,
        | 'editingMask'
        | 'stableMask'
        | 'editingMaskIssue'
        | 'promptState'
        | 'publishedPromptState'
        | 'requestStatus'
        | 'hasUnconfirmedPromptChanges'
        | 'hasUnconfirmedMaskChanges'
    >;
    /** Planner-published Prompt used before an explicit correction session. */
    readonly generatedPrompt?: ImageInstancePromptArtifact;
    readonly technicalErrors?: readonly string[];
}

export interface InspectorVersionIdentity {
    readonly digest: string;
    readonly revision?: number;
}

export interface InspectorMaskVersion extends InspectorVersionIdentity {
    readonly maskId: string;
}

export type InspectorTechnicalField =
    | 'view-id'
    | 'rgb-digest'
    | 'published-prompt-digest'
    | 'editing-prompt-digest'
    | 'stable-mask-id'
    | 'stable-mask-digest'
    | 'editing-mask-id'
    | 'editing-mask-digest'
    | 'editing-mask-issue'
    | 'error';

export interface ViewInspectorPresentation {
    readonly sectionOrder: readonly [
        'assessment-and-review',
        'prompt-and-mask',
        'technical-details'
    ];
    readonly assessment: {
        readonly quality: GeneratedViewMaskQuality;
        readonly participation: {
            readonly value: AIViewParticipation;
            readonly icon: AIViewParticipation;
            readonly pressed: boolean;
            readonly toggle: InspectorParticipationToggle;
        };
        readonly issueReasons: readonly string[];
    };
    readonly promptAndMask: {
        readonly prompt: {
            readonly positivePointCount: number;
            readonly negativePointCount: number;
            readonly boxCount: number;
            readonly published: InspectorVersionIdentity | null;
            readonly editing: InspectorVersionIdentity | null;
        };
        readonly mask: {
            readonly status:
                | 'none'
                | 'confirmed'
                | 'draft'
                | 'pending'
                | 'failed'
                | 'invalid-editing';
            readonly published: InspectorMaskVersion | null;
            readonly editing: InspectorMaskVersion | null;
        };
        readonly hasUnconfirmedChanges: boolean;
    };
    readonly technicalDetails: {
        readonly collapsedByDefault: true;
        readonly rows: readonly {
            readonly label: InspectorTechnicalField;
            readonly value: string;
        }[];
    };
}

const promptIdentity = (
    prompt:
        | AISelectMaskState['promptState']
        | ImageInstancePromptArtifact
        | null
        | undefined
): InspectorVersionIdentity | null => {
    if (prompt == null) {
        return null;
    }
    if ('artifactDigest' in prompt) {
        return Object.freeze({ digest: prompt.artifactDigest });
    }
    return Object.freeze({ digest: prompt.digest, revision: prompt.revision });
};

const maskIdentity = (
    mask: AISelectMaskState['stableMask']
): InspectorMaskVersion | null => {
    return mask === null
        ? null
        : Object.freeze({
              maskId: mask.maskId,
              digest: mask.artifact.digest
          });
};

/** Pure, reusable current-View Inspector projection (Ticket 16C/16E seam). */
export const viewInspectorPresentation = (
    input: ViewInspectorPresentationInput
): ViewInspectorPresentation => {
    const sectionOrder: ViewInspectorPresentation['sectionOrder'] =
        Object.freeze([
            'assessment-and-review',
            'prompt-and-mask',
            'technical-details'
        ]);
    const state = input.maskState;
    const invalidEditing = state.editingMaskIssue !== null;
    const maskChanged = hasSemanticEditingMaskChange(
        state.editingMask,
        state.stableMask
    );
    const publishedPrompt =
        state.publishedPromptState !== null &&
        state.publishedPromptState.revision > 0
            ? state.publishedPromptState
            : (input.generatedPrompt ?? state.publishedPromptState);
    const displayedPrompt =
        state.promptState !== null && state.promptState.revision > 0
            ? state.promptState
            : (input.generatedPrompt ?? state.promptState);
    const promptPoints =
        displayedPrompt == null
            ? []
            : 'points' in displayedPrompt
              ? displayedPrompt.points
              : [
                    ...displayedPrompt.positivePoints.map(() => ({
                        polarity: 'include' as const
                    })),
                    ...displayedPrompt.negativePoints.map(() => ({
                        polarity: 'exclude' as const
                    }))
                ];
    const boxCount =
        displayedPrompt == null
            ? 0
            : 'boxes' in displayedPrompt
              ? displayedPrompt.boxes.length
              : displayedPrompt.positiveBox === undefined
                ? 0
                : 1;
    const issueReasons = [
        ...input.actionableIssues,
        ...(invalidEditing ? ['editing-mask-state-invalid'] : [])
    ];
    const rows: { label: InspectorTechnicalField; value: string }[] = [
        { label: 'view-id', value: input.viewId }
    ];
    if (input.rgbDigest !== undefined) {
        rows.push({ label: 'rgb-digest', value: input.rgbDigest });
    }
    const publishedPromptIdentity = promptIdentity(publishedPrompt);
    if (publishedPromptIdentity !== null) {
        rows.push({
            label: 'published-prompt-digest',
            value: publishedPromptIdentity.digest
        });
    }
    const editingPromptIdentity = state.hasUnconfirmedPromptChanges
        ? promptIdentity(state.promptState)
        : null;
    if (editingPromptIdentity !== null) {
        rows.push({
            label: 'editing-prompt-digest',
            value: editingPromptIdentity.digest
        });
    }
    if (state.stableMask !== null) {
        rows.push(
            { label: 'stable-mask-id', value: state.stableMask.maskId },
            {
                label: 'stable-mask-digest',
                value: state.stableMask.artifact.digest
            }
        );
    }
    if (maskChanged && state.editingMask !== null) {
        rows.push(
            { label: 'editing-mask-id', value: state.editingMask.maskId },
            {
                label: 'editing-mask-digest',
                value: state.editingMask.artifact.digest
            }
        );
    }
    if (state.editingMaskIssue !== null) {
        rows.push({
            label: 'editing-mask-issue',
            value: state.editingMaskIssue
        });
    }
    for (const error of input.technicalErrors ?? []) {
        if (error.length > 0) {
            rows.push({ label: 'error', value: error });
        }
    }
    return Object.freeze({
        sectionOrder,
        assessment: Object.freeze({
            quality: input.quality,
            participation: Object.freeze({
                value: input.participation,
                icon: input.participation,
                pressed: input.participation === 'included',
                toggle: input.participationToggle
            }),
            issueReasons: Object.freeze(issueReasons)
        }),
        promptAndMask: Object.freeze({
            prompt: Object.freeze({
                positivePointCount: promptPoints.filter(
                    (point) => point.polarity === 'include'
                ).length,
                negativePointCount: promptPoints.filter(
                    (point) => point.polarity === 'exclude'
                ).length,
                boxCount,
                published: publishedPromptIdentity,
                editing: editingPromptIdentity
            }),
            mask: Object.freeze({
                status: invalidEditing
                    ? 'invalid-editing'
                    : state.requestStatus === 'pending'
                      ? 'pending'
                      : state.requestStatus === 'failed'
                        ? 'failed'
                        : maskChanged
                          ? 'draft'
                          : state.stableMask === null
                            ? 'none'
                            : 'confirmed',
                published: maskIdentity(state.stableMask),
                editing:
                    maskChanged && state.editingMask !== null
                        ? maskIdentity(state.editingMask)
                        : null
            }),
            hasUnconfirmedChanges:
                state.requestStatus === 'pending' ||
                state.hasUnconfirmedPromptChanges ||
                state.hasUnconfirmedMaskChanges
        }),
        technicalDetails: Object.freeze({
            collapsedByDefault: true,
            rows: Object.freeze(rows.map((row) => Object.freeze(row)))
        })
    });
};
