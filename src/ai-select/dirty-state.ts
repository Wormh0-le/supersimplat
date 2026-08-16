/**
 * The explicit upstream-to-downstream recompute state for one Current Target
 * Context. It deliberately records only product dependencies: there is no
 * tracker, sequence, reference, or propagation state in the current model.
 */
export interface AISelectDirtyState {
    readonly targetGeometryDirty: boolean;
    readonly localKeyViewPlanDirty: boolean;
    readonly promptDirtyViewIds: readonly string[];
    readonly maskInferenceDirtyViewIds: readonly string[];
    readonly evidenceDirtyViewIds: readonly string[];
    readonly liftDirty: boolean;
    readonly candidateStale: boolean;
}

export type AISelectDirtyStateListener = (state: AISelectDirtyState) => void;

const assertViewId = (viewId: string): void => {
    if (typeof viewId !== 'string' || viewId.length === 0) {
        throw new Error('AI Select dirty-state changes require a View id.');
    }
};

const addViewIds = (target: Set<string>, viewIds: readonly string[]): void => {
    for (const viewId of viewIds) {
        assertViewId(viewId);
        target.add(viewId);
    }
};

const frozenViewIds = (viewIds: ReadonlySet<string>): readonly string[] =>
    Object.freeze([...viewIds].sort());

/**
 * Owns the formal Ticket 12 dirty state. Each mutation is deliberately
 * scoped to the View identities whose bound inputs changed; none triggers
 * inference, Evidence production, or Lift work as a side effect.
 */
export class AISelectDirtyStateTracker {
    private readonly listeners = new Set<AISelectDirtyStateListener>();
    private targetGeometryDirty = false;
    private localKeyViewPlanDirty = false;
    private readonly promptDirtyViewIds = new Set<string>();
    private readonly maskInferenceDirtyViewIds = new Set<string>();
    private readonly evidenceDirtyViewIds = new Set<string>();
    private liftDirty = false;
    private candidateStale = false;

    get state(): AISelectDirtyState {
        return Object.freeze({
            targetGeometryDirty: this.targetGeometryDirty,
            localKeyViewPlanDirty: this.localKeyViewPlanDirty,
            promptDirtyViewIds: frozenViewIds(this.promptDirtyViewIds),
            maskInferenceDirtyViewIds: frozenViewIds(
                this.maskInferenceDirtyViewIds
            ),
            evidenceDirtyViewIds: frozenViewIds(this.evidenceDirtyViewIds),
            liftDirty: this.liftDirty,
            candidateStale: this.candidateStale
        });
    }

    subscribe(listener: AISelectDirtyStateListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    /** Start a fresh target-local lifecycle with no stale View identities. */
    reset(): void {
        this.targetGeometryDirty = false;
        this.localKeyViewPlanDirty = false;
        this.promptDirtyViewIds.clear();
        this.maskInferenceDirtyViewIds.clear();
        this.evidenceDirtyViewIds.clear();
        this.liftDirty = false;
        this.candidateStale = false;
        this.publish();
    }

    /**
     * A newly published Anchor Stable Mask makes only the target geometry,
     * local plan, and the plan-bound View Prompt/Mask work dirty. Existing
     * per-View Evidence remains current until a View publishes a replacement
     * Stable Mask or changes its Camera/RGB identity.
     */
    markAnchorStableChanged(dependentViewIds: readonly string[]): void {
        this.targetGeometryDirty = true;
        this.localKeyViewPlanDirty = true;
        this.markPromptAndMaskDirty(dependentViewIds);
        this.publish();
    }

    /** Target Geometry Hint replacement resolved successfully. */
    markTargetGeometryReady(): void {
        this.targetGeometryDirty = false;
        this.publish();
    }

    /**
     * The bounded initial local Key-View plan became current. Only Views in
     * that plan acquire a new Prompt/Mask dependency.
     */
    markLocalKeyViewPlanReady(dependentViewIds: readonly string[]): void {
        this.localKeyViewPlanDirty = false;
        this.markPromptAndMaskDirty(dependentViewIds);
        this.publish();
    }

    /** A View's current Prompt artifact is absent, failed, or superseded. */
    markPromptDirty(viewId: string): void {
        assertViewId(viewId);
        this.markPromptAndMaskDirty([viewId]);
        this.publish();
    }

    /** A new immutable 3D-guided Prompt is ready for its bound Mask run. */
    markPromptReady(viewId: string): void {
        assertViewId(viewId);
        this.promptDirtyViewIds.delete(viewId);
        this.maskInferenceDirtyViewIds.add(viewId);
        this.publish();
    }

    /**
     * Stable publication is the only Mask-authoring transition that dirties
     * Evidence. It never starts Evidence or Lift work itself.
     */
    markStableMaskPublished(viewId: string): void {
        assertViewId(viewId);
        this.promptDirtyViewIds.delete(viewId);
        this.maskInferenceDirtyViewIds.delete(viewId);
        this.evidenceDirtyViewIds.add(viewId);
        this.liftDirty = true;
        this.candidateStale = true;
        this.publish();
    }

    /** One View's CameraBinding or authoritative RGB identity changed. */
    markViewCameraOrRgbChanged(viewId: string): void {
        assertViewId(viewId);
        this.markPromptAndMaskDirty([viewId]);
        this.evidenceDirtyViewIds.add(viewId);
        this.liftDirty = true;
        this.candidateStale = true;
        this.publish();
    }

    /** Participation affects aggregation, even though the Mask is unchanged. */
    markParticipationChanged(viewId: string): void {
        assertViewId(viewId);
        this.liftDirty = true;
        this.candidateStale = true;
        this.publish();
    }

    /** Policy/Working-Set identity changes invalidate exactly their Views. */
    markEvidencePolicyOrWorkingSetChanged(viewIds: readonly string[]): void {
        addViewIds(this.evidenceDirtyViewIds, viewIds);
        this.liftDirty = true;
        this.candidateStale = true;
        this.publish();
    }

    /**
     * A complete, exact-current Re-Lift atomically replaced Candidate and
     * Uncertain. Upstream Prompt/Mask work remains independently dirty.
     */
    markCandidatePublished(replace: (() => void) | null = null): void {
        this.evidenceDirtyViewIds.clear();
        this.liftDirty = false;
        this.candidateStale = false;
        replace?.();
        this.publish();
    }

    /**
     * Editing Mask mutations are intentionally not represented here. Until
     * Confirm Mask atomically publishes a new Stable Mask, Evidence and a
     * previous Candidate remain valid and inspectable.
     */
    markEditingMaskChanged(): void {}

    /** Drop identities when a target-local View is disposed or replaced. */
    forgetView(viewId: string): void {
        assertViewId(viewId);
        this.promptDirtyViewIds.delete(viewId);
        this.maskInferenceDirtyViewIds.delete(viewId);
        this.evidenceDirtyViewIds.delete(viewId);
        this.publish();
    }

    private markPromptAndMaskDirty(viewIds: readonly string[]): void {
        addViewIds(this.promptDirtyViewIds, viewIds);
        addViewIds(this.maskInferenceDirtyViewIds, viewIds);
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                // Observers do not own lifecycle commits. One broken UI
                // listener must not roll back or hide a valid atomic state
                // transition from other observers.
                console.error(error);
            }
        });
    }
}
