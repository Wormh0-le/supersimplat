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
export type GalleryFilter = 'all' | 'needs-review';
export type GallerySort = 'creation' | 'newest' | 'needs-review';
export type NavigatorBadge =
    'failure' | 'needs-review' | 'processing' | 'ready';

export interface NavigatorProjectionItem {
    readonly id: string;
    readonly view: GeneratedAIView | null;
}

export interface NavigatorProjection {
    readonly items: readonly NavigatorProjectionItem[];
    readonly currentId: string | null;
    readonly selectionChanged: boolean;
    readonly empty: boolean;
}

// This is the repository-reserved Anchor View identity; generated/user View
// validators reject it, so presentation projection cannot collide with it.
export const NAVIGATOR_ANCHOR_ID = 'anchor-view';

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

const isGalleryViewNeedsReview = (view: GeneratedAIView): boolean =>
    view.assessment?.status === 'review' &&
    view.maskQuality !== 'user-confirmed';

/**
 * Controller lifecycle operations may regroup sources; the monotonic ordinal
 * restores global creation order. Sorting never consults current selection.
 */
export const orderGalleryViews = (
    views: readonly GeneratedAIView[],
    sort: GallerySort = 'creation'
): GeneratedAIView[] => {
    const creationOrder = [...views].sort(
        (left, right) => left.creationOrdinal - right.creationOrdinal
    );
    if (sort === 'newest') {
        return creationOrder.reverse();
    }
    if (sort === 'needs-review') {
        const review = creationOrder.filter(isGalleryViewNeedsReview);
        const remaining = creationOrder.filter(
            (view) => !isGalleryViewNeedsReview(view)
        );
        return [...review, ...remaining];
    }
    return creationOrder;
};

export const nextRadioChoice = <T extends string>(
    entries: readonly T[],
    current: T,
    key: string
): T | null => {
    if (entries.length === 0) {
        return null;
    }
    if (key === 'Home') {
        return entries[0];
    }
    if (key === 'End') {
        return entries[entries.length - 1];
    }
    const direction =
        key === 'ArrowRight' || key === 'ArrowDown'
            ? 1
            : key === 'ArrowLeft' || key === 'ArrowUp'
              ? -1
              : 0;
    if (direction === 0) {
        return null;
    }
    const currentIndex = Math.max(0, entries.indexOf(current));
    return entries[
        (currentIndex + direction + entries.length) % entries.length
    ];
};

export const filterGalleryViews = (
    views: readonly GeneratedAIView[],
    filter: GalleryFilter
): GeneratedAIView[] => {
    switch (filter) {
        case 'all':
            return [...views];
        case 'needs-review':
            // User Confirmed authority settles an automatic Review; the View
            // is no longer pending a decision.
            return views.filter(isGalleryViewNeedsReview);
    }
};

export const navigatorBadgePresentation = (
    view: GeneratedAIView
): NavigatorBadge => {
    if (
        view.renderStatus === 'failed' ||
        view.promptStatus === 'failed' ||
        view.maskStatus === 'failed' ||
        view.maskQuality === 'failed' ||
        view.assessment?.status === 'failed'
    ) {
        return 'failure';
    }
    if (isGalleryViewNeedsReview(view)) {
        return 'needs-review';
    }
    if (
        view.renderStatus === 'pending' ||
        view.renderStatus === 'rendering' ||
        view.promptStatus === 'synthesizing' ||
        view.maskStatus === 'generating'
    ) {
        return 'processing';
    }
    return 'ready';
};

/** Anchor is the oldest item; Needs Review filtering intentionally excludes it. */
export const projectNavigatorViews = (
    views: readonly GeneratedAIView[],
    filter: GalleryFilter,
    sort: GallerySort,
    currentId: string
): NavigatorProjection => {
    const visible = filterGalleryViews(views, filter);
    const ordered = orderGalleryViews(visible, sort);
    let items: NavigatorProjectionItem[] = ordered.map((view) =>
        Object.freeze({ id: view.viewId, view })
    );
    if (filter === 'all') {
        const anchor = Object.freeze({
            id: NAVIGATOR_ANCHOR_ID,
            view: null
        });
        if (sort === 'newest') {
            items = [...items, anchor];
        } else if (sort === 'needs-review') {
            const firstNonReview = items.findIndex(
                (item) =>
                    item.view !== null && !isGalleryViewNeedsReview(item.view)
            );
            const index = firstNonReview < 0 ? items.length : firstNonReview;
            items = [...items.slice(0, index), anchor, ...items.slice(index)];
        } else {
            items = [anchor, ...items];
        }
    }
    const currentVisible = items.some((item) => item.id === currentId);
    const nextId = currentVisible ? currentId : (items[0]?.id ?? null);
    return Object.freeze({
        items: Object.freeze(items),
        currentId: nextId,
        selectionChanged: nextId !== currentId,
        empty: items.length === 0
    });
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

    const canToggleParticipation =
        view.participation === 'included' ||
        view.maskQuality === 'auto-good' ||
        view.maskQuality === 'user-confirmed';
    // A user-added View without a Stable Mask can explicitly stay excluded.
    const userOwnedNoMask =
        galleryViewRole(view.source) === 'user-added' &&
        view.stableMaskId === undefined;
    const actions: GalleryCardActions = Object.freeze({
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
        // A failed user-owned View remains inspectable and can stay excluded;
        // recovery is a replacement View, not an identical-input render.
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
