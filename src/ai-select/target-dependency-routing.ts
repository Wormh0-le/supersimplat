/**
 * Route global render-configuration changes and mutations of any Splat that
 * can enter or leave the authoritative visible render scope. The scene list
 * includes hidden Splats so a visibility transition cannot retain stale RGB.
 */
export const isCurrentTargetDependencyChange = <TTarget>(
    currentTarget: TTarget | null,
    changedTarget?: TTarget,
    sceneTargets: readonly TTarget[] = []
): boolean => {
    return (
        currentTarget !== null &&
        (changedTarget === undefined ||
            changedTarget === currentTarget ||
            sceneTargets.includes(changedTarget))
    );
};
