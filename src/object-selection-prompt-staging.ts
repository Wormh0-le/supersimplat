import type {
    ObjectSelectionPrompt,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionState
} from './object-selection-session';

interface ObjectSelectionAnchorFrame {
    readonly viewId: string;
    readonly frameDigest: string;
    readonly frameWidth: number;
    readonly frameHeight: number;
}

interface ObjectSelectionCanvasPromptPoint {
    readonly xPx: number;
    readonly yPx: number;
    readonly normalizedX: number;
    readonly normalizedY: number;
}

interface ObjectSelectionPromptStagingOptions {
    readonly session: ObjectSelectionSessionInterface;
    readonly isAnchorViewCurrent: () => Promise<boolean>;
    readonly isTargetHit: (
        point: ObjectSelectionCanvasPromptPoint
    ) => Promise<boolean>;
    readonly onCameraLockChange: (locked: boolean) => void;
    readonly onStagingChange?: (staging: boolean) => void;
    readonly onError: (error: unknown) => void;
    readonly stagePrompt?: (prompt: ObjectSelectionPrompt) => void;
}

const anchorsMatch = (
    left: ObjectSelectionAnchorFrame,
    right: ObjectSelectionAnchorFrame
) => {
    return left.viewId === right.viewId &&
        left.frameDigest === right.frameDigest &&
        left.frameWidth === right.frameWidth &&
        left.frameHeight === right.frameHeight;
};

// The browser owns point placement and topmost Target Splat hit-testing. This
// controller keeps that mutable UI interaction separate from the session's
// replayable Prompt Log while exposing only staged, Anchor-bound prompts.
class ObjectSelectionPromptStaging {
    private session: ObjectSelectionSessionInterface;
    private isAnchorViewCurrent: () => Promise<boolean>;
    private isTargetHit: (
        point: ObjectSelectionCanvasPromptPoint
    ) => Promise<boolean>;
    private onCameraLockChange: (locked: boolean) => void;
    private onStagingChange: (staging: boolean) => void;
    private onError: (error: unknown) => void;
    private stagePrompt: (prompt: ObjectSelectionPrompt) => void;
    private anchor: ObjectSelectionAnchorFrame | null = null;
    private promptCount = 0;
    private pendingPromptCount = 0;
    private staging = false;
    private stagingGeneration = 0;
    private cameraLocked = false;
    private unsubscribe: (() => void) | null;

    constructor(options: ObjectSelectionPromptStagingOptions) {
        this.session = options.session;
        this.isAnchorViewCurrent = options.isAnchorViewCurrent;
        this.isTargetHit = options.isTargetHit;
        this.onCameraLockChange = options.onCameraLockChange;
        this.onStagingChange = options.onStagingChange ?? (() => {});
        this.onError = options.onError;
        this.stagePrompt = options.stagePrompt ??
            (prompt => this.session.stagePrompt(prompt));
        this.unsubscribe = this.session.subscribe(state => this.update(state));
    }

    setAnchorFrame(anchor: ObjectSelectionAnchorFrame | null) {
        this.anchor = anchor === null ? null : { ...anchor };
    }

    async stageAt(point: ObjectSelectionCanvasPromptPoint): Promise<boolean> {
        const state = this.session.state;
        if (this.staging || !this.canStage(state)) {
            return false;
        }
        const anchor = this.anchor;
        if (anchor === null) {
            this.onError(
                new Error('Object Selection requires an Anchor View before staging prompts.')
            );
            return false;
        }

        const stagingGeneration = ++this.stagingGeneration;
        this.setStaging(true);
        this.syncCameraLock();
        try {
            const anchorViewCurrent = await this.isAnchorViewCurrent();
            if (!this.isCurrentStaging(stagingGeneration)) {
                return false;
            }
            if (!anchorViewCurrent) {
                this.onError(
                    new Error('Return to the session Anchor View before staging prompts.')
                );
                return false;
            }
            if (
                !this.canStage(this.session.state) ||
                this.session.state.mode !== state.mode ||
                this.anchor === null ||
                !anchorsMatch(this.anchor, anchor)
            ) {
                return false;
            }
            const targetHit = await this.isTargetHit({ ...point });
            if (!this.isCurrentStaging(stagingGeneration)) {
                return false;
            }
            if (!targetHit) {
                this.onError(
                    new Error('Prompt must hit the current Target Splat.')
                );
                return false;
            }
            if (
                !this.canStage(this.session.state) ||
                this.session.state.mode !== state.mode ||
                this.anchor === null ||
                !anchorsMatch(this.anchor, anchor)
            ) {
                return false;
            }
            this.stagePrompt({
                promptId: `object-selection-prompt-${++this.promptCount}`,
                viewId: anchor.viewId,
                frameDigest: anchor.frameDigest,
                frameWidth: anchor.frameWidth,
                frameHeight: anchor.frameHeight,
                xPx: point.xPx,
                yPx: point.yPx,
                polarity: 'include'
            });
            return true;
        } catch (error) {
            if (this.isCurrentStaging(stagingGeneration)) {
                this.onError(error);
            }
            return false;
        } finally {
            if (this.isCurrentStaging(stagingGeneration)) {
                this.setStaging(false);
                this.syncCameraLock();
            }
        }
    }

    undoLastPendingPrompt() {
        if (this.cancelStaging()) {
            return true;
        }
        if (!this.canStage(this.session.state)) {
            return false;
        }
        try {
            return this.session.undoLastPendingPrompt();
        } catch (error) {
            this.onError(error);
            return false;
        }
    }

    clearPendingPrompts() {
        this.cancelStaging();
        if (!this.canStage(this.session.state)) {
            return;
        }
        try {
            this.session.clearPendingPrompts();
        } catch (error) {
            this.onError(error);
        }
    }

    destroy() {
        this.unsubscribe?.();
        this.unsubscribe = null;
        this.pendingPromptCount = 0;
        this.cancelStaging();
        this.setCameraLocked(false);
    }

    private canStage(state: ObjectSelectionSessionState) {
        return state.status === 'preview' &&
            state.candidate !== null &&
            state.mode !== 'New';
    }

    private update(state: ObjectSelectionSessionState) {
        this.pendingPromptCount = state.pendingPrompts.length;
        this.syncCameraLock();
    }

    private syncCameraLock() {
        this.setCameraLocked(this.staging || this.pendingPromptCount > 0);
    }

    private setStaging(staging: boolean) {
        if (this.staging === staging) {
            return;
        }
        this.staging = staging;
        this.onStagingChange(staging);
    }

    private isCurrentStaging(generation: number) {
        return this.staging && this.stagingGeneration === generation;
    }

    private cancelStaging() {
        if (!this.staging) {
            return false;
        }
        this.stagingGeneration += 1;
        this.setStaging(false);
        this.syncCameraLock();
        return true;
    }

    private setCameraLocked(locked: boolean) {
        if (this.cameraLocked === locked) {
            return;
        }
        this.cameraLocked = locked;
        this.onCameraLockChange(locked);
    }
}

export {
    ObjectSelectionPromptStaging
};

export type {
    ObjectSelectionAnchorFrame,
    ObjectSelectionCanvasPromptPoint,
    ObjectSelectionPromptStagingOptions
};
