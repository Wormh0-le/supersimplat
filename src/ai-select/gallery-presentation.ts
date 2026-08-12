import type { AIViewSource } from './ai-view';
import type { GeneratedAIView } from './generated-view-controller';
import { reviewReasonActionKeys } from './view-assessment';

/**
 * Gallery View role is presentation identity only: it never implies trust,
 * quality, or Participation (Final Spec v1.3 §§17–18). `replacement` Views
 * are planner-generated and keep the generated role.
 */
export type GalleryViewRole = 'generated' | 'user-added';

/**
 * Gallery filters project which cards are visible. They live in presentation
 * only: applying one never mutates Prompt, Mask, Participation, Evidence, or
 * Candidate state.
 */
export type GalleryFilter = 'all' | 'included' | 'excluded' | 'needs-review';

/**
 * A `status` line is always a localized `ai-select.*` key; a `detail` line is
 * a raw technical message rendered muted. Semantic states (for example "no
 * usable Mask") are statuses, so a transport/OOM message can never replace
 * them.
 */
export type GalleryCardLine =
    | { readonly kind: 'status'; readonly key: string }
    | { readonly kind: 'detail'; readonly text: string };

/**
 * The complete corrective-action vocabulary of an ordinary Gallery card.
 * Backend routes, fallback provenance, tracker state, generic
 * ProposalDecision panels, Prompt Brush, and Negative Box are absent by
 * construction — the Anchor candidate choice stays on the Anchor surface.
 */
export interface GalleryCardActions {
    readonly retryRender: boolean;
    /** Rebuild the Route-B 3D-guided Prompt without running SAM. */
    readonly regeneratePrompt: boolean;
    /**
     * Start one explicit Auto Mask inference attempt from the current Prompt.
     * It is a Retry for failed/unavailable inference and a Refresh otherwise.
     */
    readonly refreshMask: boolean;
    readonly confirmAsIs: boolean;
    readonly participationToggle: 'include' | 'exclude' | null;
    readonly inspectCamera: boolean;
    readonly excludeView: boolean;
}

export interface GalleryCardPresentation {
    readonly viewId: string;
    readonly role: GalleryViewRole;
    /** Per-role ordinal for the card title ("View 2", "User View 1"). */
    readonly titleOrdinal: number;
    readonly lines: readonly GalleryCardLine[];
    readonly actions: GalleryCardActions;
    readonly selected: boolean;
}

export const galleryViewRole = (source: AIViewSource): GalleryViewRole => {
    return source === 'user-added' ? 'user-added' : 'generated';
};

const status = (key: string): GalleryCardLine =>
    Object.freeze({ kind: 'status', key });
const detail = (text: string): GalleryCardLine =>
    Object.freeze({ kind: 'detail', text });

/**
 * Stable Gallery order: generated local Views keep creation order, then
 * user-added Views. Appending later Views never reorders prior completed
 * Views, so Generate More cannot visually stale them.
 */
export const orderGalleryViews = (
    views: readonly GeneratedAIView[]
): GeneratedAIView[] => {
    const generated = views.filter(
        (view) => galleryViewRole(view.source) === 'generated'
    );
    const userAdded = views.filter(
        (view) => galleryViewRole(view.source) === 'user-added'
    );
    return [...generated, ...userAdded];
};

export const filterGalleryViews = (
    views: readonly GeneratedAIView[],
    filter: GalleryFilter
): GeneratedAIView[] => {
    switch (filter) {
        case 'all':
            return [...views];
        case 'included':
            return views.filter((view) => view.participation === 'included');
        case 'excluded':
            return views.filter((view) => view.participation === 'excluded');
        case 'needs-review':
            // User Confirmed authority settles an automatic Review; the View
            // is no longer pending a decision.
            return views.filter(
                (view) =>
                    view.assessment?.status === 'review' &&
                    view.maskQuality !== 'user-confirmed'
            );
    }
};

/**
 * Compose one card from the independent per-View states. Render, Prompt
 * synthesis, Mask inference, Mask Review, Participation, and Evidence stay
 * separate lines: RGB Ready survives Mask pending/failure, and a Mask or
 * Prompt failure never demotes the completed render.
 */
export const galleryCardPresentation = (
    view: GeneratedAIView,
    titleOrdinal: number
): GalleryCardPresentation => {
    const lines: GalleryCardLine[] = [
        status(`ai-select.views.status.${view.renderStatus}`)
    ];
    if (
        view.renderStatus === 'failed' &&
        view.renderErrorMessage !== undefined
    ) {
        lines.push(detail(view.renderErrorMessage));
    }
    if (view.renderStatus === 'ready') {
        // Prompt synthesis is its own dimension: Prompt Ready is visible
        // separately from Mask inference states.
        lines.push(
            status(`ai-select.views.status.prompt-${view.promptStatus}`)
        );
        if (
            view.promptStatus === 'limited' &&
            view.promptDiagnostics !== undefined
        ) {
            for (const diagnostic of view.promptDiagnostics) {
                lines.push(detail(diagnostic));
            }
        }
        if (
            view.promptStatus === 'failed' &&
            view.promptErrorMessage !== undefined
        ) {
            lines.push(detail(view.promptErrorMessage));
        }
        lines.push(status(`ai-select.views.status.mask-${view.maskStatus}`));
        if (view.maskStatus === 'failed') {
            if (view.maskErrorMessage !== undefined) {
                lines.push(detail(view.maskErrorMessage));
            }
            lines.push(status('ai-select.review.mask-failure-options'));
        }
        lines.push(
            status(`ai-select.views.status.evidence-${view.evidenceStatus}`)
        );
        lines.push(status(`ai-select.review.quality.${view.maskQuality}`));
        lines.push(status(`ai-select.participation.${view.participation}`));
        if (view.assessment?.status === 'review') {
            for (const reason of view.assessment.actionableReasons) {
                lines.push(status(`ai-select.review.reason.${reason}`));
                for (const actionKey of reviewReasonActionKeys(reason)) {
                    lines.push(status(actionKey));
                }
            }
            lines.push(status('ai-select.review.correction-options'));
        }
    }

    const generatedAutoView =
        galleryViewRole(view.source) === 'generated' &&
        view.maskQuality !== 'user-confirmed';
    // These are deliberately independent user actions. Rebuilding a Prompt
    // never starts SAM; refresh uses the current immutable Prompt artifact.
    const regeneratePrompt =
        generatedAutoView &&
        view.renderStatus === 'ready' &&
        view.promptStatus !== 'none' &&
        view.promptStatus !== 'synthesizing';
    const refreshMask =
        generatedAutoView &&
        view.renderStatus === 'ready' &&
        view.promptStatus === 'ready' &&
        view.maskStatus !== 'generating';
    const canToggleParticipation =
        view.participation === 'included' ||
        view.maskQuality === 'auto-good' ||
        view.maskQuality === 'user-confirmed';
    // A user-added View without a Stable Mask can explicitly stay excluded.
    const userOwnedNoMask =
        galleryViewRole(view.source) === 'user-added' &&
        view.stableMaskId === undefined;
    const actions: GalleryCardActions = Object.freeze({
        retryRender: view.renderStatus === 'failed',
        regeneratePrompt,
        refreshMask,
        confirmAsIs:
            view.maskStatus === 'ready' &&
            view.assessment?.status === 'review' &&
            view.maskQuality !== 'user-confirmed',
        participationToggle: canToggleParticipation
            ? view.participation === 'included'
                ? 'exclude'
                : 'include'
            : null,
        // The planner-owned CameraBinding always exists, even for a failed
        // render, so Camera Inspection is always available.
        inspectCamera: true,
        // Render failure still offers the explicit Exclude decision next to
        // Retry (Ticket 11 failure contract). Selecting a RGB Ready card
        // already exposes its Mask editor; it needs no duplicate action.
        excludeView: userOwnedNoMask
    });
    return Object.freeze({
        viewId: view.viewId,
        role: galleryViewRole(view.source),
        titleOrdinal,
        lines: Object.freeze(lines),
        actions,
        selected: view.selected
    });
};
