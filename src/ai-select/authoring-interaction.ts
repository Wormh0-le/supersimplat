import type { PromptTool } from './prompt-state';

export type AuthoringTool = PromptTool | 'paint' | 'erase' | 'inspect';
export type AuthoringPointerAction =
    'point' | 'box' | 'prompt-constraint' | 'pixel-edit' | 'none';

/** Pointer meaning is selected-tool-only; modifiers and press duration do not alter it. */
export const pointerActionForTool = (
    tool: AuthoringTool
): AuthoringPointerAction => {
    if (tool === 'positive-point' || tool === 'negative-point') {
        return 'point';
    }
    if (tool === 'positive-box' || tool === 'negative-box') {
        return 'box';
    }
    if (
        tool === 'positive-mask-constraint' ||
        tool === 'negative-mask-constraint'
    ) {
        return 'prompt-constraint';
    }
    if (tool === 'paint' || tool === 'erase') {
        return 'pixel-edit';
    }
    return 'none';
};
