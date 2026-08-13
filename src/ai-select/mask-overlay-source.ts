import type { AIViewSource } from './ai-view';

export type InspectedMaskOverlaySource<TAuthoring> =
    | {
          readonly kind: 'authoring';
          readonly authoring: TAuthoring;
      }
    | { readonly kind: 'registry' };

/**
 * Select the live overlay authority for an inspected View. View source is
 * presentation identity only: generated, replacement, and user-added Views
 * all use their authoring session when one exists.
 */
export const selectInspectedMaskOverlaySource = <TAuthoring>(
    _viewSource: AIViewSource,
    authoring: TAuthoring | null
): InspectedMaskOverlaySource<TAuthoring> => {
    return authoring === null
        ? Object.freeze({ kind: 'registry' })
        : Object.freeze({ kind: 'authoring', authoring });
};
