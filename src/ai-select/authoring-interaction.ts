import type { PromptTool } from './prompt-state';

export type AuthoringTool = PromptTool | 'paint' | 'erase' | 'inspect';
export type AuthoringPointerAction =
    'point' | 'box' | 'prompt-constraint' | 'pixel-edit' | 'none';

export interface PointerStrokeSample {
    readonly xPx: number;
    readonly yPx: number;
}

/**
 * Transactional pointer-sample buffer for one Paint/Erase gesture. Nothing
 * leaves the buffer until commit; cancellation has no domain-side effect.
 */
export class PointerStrokeBuffer {
    private samples: PointerStrokeSample[] | null = null;

    begin(sample: PointerStrokeSample): void {
        this.samples = [sample];
    }

    append(sample: PointerStrokeSample): void {
        if (this.samples === null) {
            return;
        }
        const previous = this.samples[this.samples.length - 1];
        if (previous.xPx === sample.xPx && previous.yPx === sample.yPx) {
            return;
        }
        this.samples.push(sample);
    }

    cancel(): void {
        this.samples = null;
    }

    get previewSamples(): readonly PointerStrokeSample[] {
        return this.samples ?? [];
    }

    commit(): readonly PointerStrokeSample[] | null {
        const samples = this.samples;
        this.samples = null;
        return samples === null
            ? null
            : Object.freeze(
                  samples.map((sample) =>
                      Object.freeze({ xPx: sample.xPx, yPx: sample.yPx })
                  )
              );
    }
}

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
