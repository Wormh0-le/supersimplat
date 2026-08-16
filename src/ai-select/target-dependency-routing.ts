/**
 * Route global render-configuration changes and mutations of the current
 * target, while excluding mutations owned by unrelated Splats.
 */
export const isCurrentTargetDependencyChange = <TTarget>(
    currentTarget: TTarget | null,
    changedTarget?: TTarget
): boolean => {
    return (
        currentTarget !== null &&
        (changedTarget === undefined || changedTarget === currentTarget)
    );
};
