export type CurrentTargetContextLifecycle = 'active' | 'suspended' | 'disposed';

export interface AITarget {
  readonly splatId: string;
}

/**
 * Semantic identity of the target inputs that affect AI observation rendering
 * and Gaussian lifting. It deliberately excludes editor-only and native
 * selection state so those changes cannot suspend a target context.
 */
export interface TargetDependencyToken {
  readonly splatId: string;
  readonly renderStateToken: string;
  readonly geometryToken: string;
  readonly gaussianIdentityToken: string;
  readonly worldTransformToken: string;
}

/**
 * The async identity every AI request and result must carry. Request IDs are
 * not sufficient because cancellation cannot guarantee that GPU work stopped.
 */
export interface AIRequestBinding {
  readonly targetContextId: string;
  readonly contextRevision: number;
  readonly dependencyToken: TargetDependencyToken;
}

export interface CurrentTargetContext {
  readonly targetContextId: string;
  readonly revision: number;
  readonly target: AITarget;
  readonly dependencyToken: TargetDependencyToken;
  readonly lifecycle: CurrentTargetContextLifecycle;
}

export interface CurrentTargetContextInput {
  readonly target: AITarget;
  readonly dependencyToken: TargetDependencyToken;
}

type UnknownRecord = Record<string, unknown>;

let nextTargetContextOrdinal = 0;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const copyTarget = (target: AITarget): AITarget => {
    return Object.freeze({
        splatId: target.splatId
    });
};

const copyDependencyToken = (
    dependencyToken: TargetDependencyToken
): TargetDependencyToken => {
    return Object.freeze({
        splatId: dependencyToken.splatId,
        renderStateToken: dependencyToken.renderStateToken,
        geometryToken: dependencyToken.geometryToken,
        gaussianIdentityToken: dependencyToken.gaussianIdentityToken,
        worldTransformToken: dependencyToken.worldTransformToken
    });
};

const createTargetContextId = (): string => {
    nextTargetContextOrdinal += 1;
    return `ai-target-context-${nextTargetContextOrdinal}`;
};

const nextRevision = (context: CurrentTargetContext): number => {
    if (context.revision >= Number.MAX_SAFE_INTEGER) {
        throw new Error('Current Target Context revision cannot advance safely.');
    }

    return context.revision + 1;
};

const createContext = (
    targetContextId: string,
    target: AITarget,
    dependencyToken: TargetDependencyToken,
    lifecycle: CurrentTargetContextLifecycle,
    revision: number
): CurrentTargetContext => {
    return Object.freeze({
        targetContextId,
        revision,
        target: copyTarget(target),
        dependencyToken: copyDependencyToken(dependencyToken),
        lifecycle
    });
};

const isAITarget = (value: unknown): value is AITarget => {
    return isRecord(value) && isNonEmptyString(value.splatId);
};

export const isTargetDependencyToken = (
    value: unknown
): value is TargetDependencyToken => {
    return (
        isRecord(value) &&
    isNonEmptyString(value.splatId) &&
    isNonEmptyString(value.renderStateToken) &&
    isNonEmptyString(value.geometryToken) &&
    isNonEmptyString(value.gaussianIdentityToken) &&
    isNonEmptyString(value.worldTransformToken)
    );
};

export const areTargetDependencyTokensEqual = (
    left: TargetDependencyToken,
    right: TargetDependencyToken
): boolean => {
    return (
        left.splatId === right.splatId &&
    left.renderStateToken === right.renderStateToken &&
    left.geometryToken === right.geometryToken &&
    left.gaussianIdentityToken === right.gaussianIdentityToken &&
    left.worldTransformToken === right.worldTransformToken
    );
};

export const isAIRequestBinding = (
    value: unknown
): value is AIRequestBinding => {
    return (
        isRecord(value) &&
    isNonEmptyString(value.targetContextId) &&
    Number.isSafeInteger(value.contextRevision) &&
    (value.contextRevision as number) >= 0 &&
    isTargetDependencyToken(value.dependencyToken)
    );
};

const isCurrentTargetContextInput = (
    value: unknown
): value is CurrentTargetContextInput => {
    return (
        isRecord(value) &&
    isAITarget(value.target) &&
    isTargetDependencyToken(value.dependencyToken) &&
    value.target.splatId === value.dependencyToken.splatId
    );
};

function assertCurrentTargetContextInput(
    value: unknown
): asserts value is CurrentTargetContextInput {
    if (!isCurrentTargetContextInput(value)) {
        throw new Error(
            'Current Target Context requires a target and a complete matching dependency token.'
        );
    }
}

/**
 * Owns the one user-visible Current Target Context. It intentionally contains
 * only lifecycle and stale-result protection; AI Views, Masks, and Candidates
 * remain independent future domain concerns.
 */
export class CurrentTargetContextKernel {
    private currentContext: CurrentTargetContext | null = null;

    get current(): CurrentTargetContext | null {
        return this.currentContext;
    }

    start(input: CurrentTargetContextInput): CurrentTargetContext {
        if (this.currentContext !== null) {
            throw new Error(
                'A Current Target Context is already active. Restart it instead.'
            );
        }

        assertCurrentTargetContextInput(input);

        this.currentContext = createContext(
            createTargetContextId(),
            input.target,
            input.dependencyToken,
            'active',
            0
        );

        return this.currentContext;
    }

    restart(input: CurrentTargetContextInput): CurrentTargetContext {
        this.dispose();
        return this.start(input);
    }

    dispose(): CurrentTargetContext | null {
        if (this.currentContext === null) {
            return null;
        }

        const disposed = createContext(
            this.currentContext.targetContextId,
            this.currentContext.target,
            this.currentContext.dependencyToken,
            'disposed',
            nextRevision(this.currentContext)
        );
        this.currentContext = null;

        return disposed;
    }

    revise(): CurrentTargetContext {
        const current = this.requireActiveContext();
        this.currentContext = createContext(
            current.targetContextId,
            current.target,
            current.dependencyToken,
            'active',
            nextRevision(current)
        );

        return this.currentContext;
    }

    synchronizeDependency(
        effectiveDependencyToken: unknown
    ): CurrentTargetContext | null {
        const current = this.currentContext;
        if (current === null) {
            return null;
        }

        const matchesCurrentDependency =
      isTargetDependencyToken(effectiveDependencyToken) &&
      effectiveDependencyToken.splatId === current.target.splatId &&
      areTargetDependencyTokensEqual(
          current.dependencyToken,
          effectiveDependencyToken
      );

        if (current.lifecycle === 'active') {
            return matchesCurrentDependency ? current : this.suspend(current);
        }

        if (current.lifecycle === 'suspended' && matchesCurrentDependency) {
            this.currentContext = createContext(
                current.targetContextId,
                current.target,
                current.dependencyToken,
                'active',
                nextRevision(current)
            );
        }

        return this.currentContext;
    }

    createRequestBinding(): AIRequestBinding {
        const current = this.requireActiveContext();

        return Object.freeze({
            targetContextId: current.targetContextId,
            contextRevision: current.revision,
            dependencyToken: copyDependencyToken(current.dependencyToken)
        });
    }

    acceptsResult(binding: unknown, effectiveDependencyToken: unknown): boolean {
        const current = this.synchronizeDependency(effectiveDependencyToken);

        return (
            current !== null &&
      current.lifecycle === 'active' &&
      isAIRequestBinding(binding) &&
      binding.targetContextId === current.targetContextId &&
      binding.contextRevision === current.revision &&
      areTargetDependencyTokensEqual(
          binding.dependencyToken,
          current.dependencyToken
      )
        );
    }

    private requireActiveContext(): CurrentTargetContext {
        if (
            this.currentContext === null ||
      this.currentContext.lifecycle !== 'active'
        ) {
            throw new Error(
                'Current Target Context must be active for this operation.'
            );
        }

        return this.currentContext;
    }

    private suspend(current: CurrentTargetContext): CurrentTargetContext {
        this.currentContext = createContext(
            current.targetContextId,
            current.target,
            current.dependencyToken,
            'suspended',
            nextRevision(current)
        );

        return this.currentContext;
    }
}
