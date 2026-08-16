import {
    buildPackedSceneSnapshot,
    sha256Digest,
    type AuthoritativeRenderScope,
    type AuthoritativeRenderScopeEntry,
    type PackedSceneSnapshot,
    type SceneSnapshotShFloatCount
} from '../scene-snapshot-binary';

export const AUTHORITATIVE_RENDER_SCOPE_POLICY_ID =
    'visible-editor-splats-conservative/v1' as const;

interface RenderScopeSnapshotInput {
    readonly splatId: string;
    readonly snapshot: PackedSceneSnapshot;
}

const supportedShFloatCounts: readonly SceneSnapshotShFloatCount[] = [
    0, 9, 24, 45
];

const assertCompatibleSnapshot = (
    target: PackedSceneSnapshot,
    candidate: PackedSceneSnapshot
): void => {
    const targetRender = target.renderConfiguration;
    const candidateRender = candidate.renderConfiguration;
    if (
        candidate.coordinateConvention !== target.coordinateConvention ||
        candidate.stableIdSchema !== target.stableIdSchema ||
        candidateRender.version !== targetRender.version ||
        candidateRender.alphaMode !== targetRender.alphaMode ||
        candidateRender.rasterizer !== targetRender.rasterizer ||
        candidateRender.backgroundRgba.some(
            (value, index) => value !== targetRender.backgroundRgba[index]
        )
    ) {
        throw new Error(
            'AI Select cannot declare an authoritative render scope with ambiguous renderer semantics.'
        );
    }
};

const scopeIdentityDigest = (
    targetSplatId: string,
    sources: readonly RenderScopeSnapshotInput[]
): string => {
    return sha256Digest(
        new TextEncoder().encode(
            JSON.stringify({
                policyId: AUTHORITATIVE_RENDER_SCOPE_POLICY_ID,
                targetSplatId,
                sources: sources.map(({ splatId, snapshot }) => ({
                    splatId,
                    sourceContentDigest: snapshot.contentDigest,
                    gaussianCount: snapshot.gaussianCount
                }))
            })
        )
    );
};

const copyRows = (
    target: Float32Array,
    targetOffset: number,
    source: Float32Array
): void => {
    target.set(source, targetOffset);
};

/**
 * Build the immutable RGB render scope for one Active Target. The target's
 * editor-owned Stable IDs remain unchanged; visible non-target Splats receive
 * collision-free render-only IDs and stay read-only outside target Evidence.
 */
export const buildAuthoritativeRenderScopeSnapshot = (
    target: RenderScopeSnapshotInput,
    visibleSources: readonly RenderScopeSnapshotInput[]
): PackedSceneSnapshot => {
    const occluders = visibleSources
        .filter(({ splatId }) => splatId !== target.splatId)
        .sort((left, right) => left.splatId.localeCompare(right.splatId));
    const sources = [target, ...occluders];
    const sourceIds = new Set<string>();
    sources.forEach((source) => {
        if (!source.splatId || sourceIds.has(source.splatId)) {
            throw new Error(
                'AI Select authoritative render scope requires unique Splat identities.'
            );
        }
        sourceIds.add(source.splatId);
        assertCompatibleSnapshot(target.snapshot, source.snapshot);
    });

    const gaussianCount = sources.reduce(
        (total, source) => total + source.snapshot.gaussianCount,
        0
    );
    const shFloatCountPerGaussian = Math.max(
        ...sources.map((source) => source.snapshot.shFloatCountPerGaussian)
    ) as SceneSnapshotShFloatCount;
    if (!supportedShFloatCounts.includes(shFloatCountPerGaussian)) {
        throw new Error(
            'AI Select authoritative render scope uses an unsupported spherical-harmonic schema.'
        );
    }

    let maximumTargetId = 0;
    target.snapshot.stableIds.forEach((stableId) => {
        maximumTargetId = Math.max(maximumTargetId, stableId);
    });
    const occluderCount = gaussianCount - target.snapshot.gaussianCount;
    if (maximumTargetId + occluderCount > 0xffffffff) {
        throw new Error(
            'AI Select authoritative render scope cannot allocate collision-free occluder IDs.'
        );
    }

    const stableIds = new Uint32Array(gaussianCount);
    const means = new Float32Array(gaussianCount * 3);
    const rotationsXyzw = new Float32Array(gaussianCount * 4);
    const logScales = new Float32Array(gaussianCount * 3);
    const logitOpacities = new Float32Array(gaussianCount);
    const dc = new Float32Array(gaussianCount * 3);
    const sh = new Float32Array(gaussianCount * shFloatCountPerGaussian);
    const entries: AuthoritativeRenderScopeEntry[] = [];
    let rowOffset = 0;
    let nextOccluderId = maximumTargetId + 1;
    sources.forEach((source, sourceIndex) => {
        const snapshot = source.snapshot;
        const role = sourceIndex === 0 ? 'target' : 'occluder';
        const renderIdStart =
            role === 'target' ? snapshot.stableIds[0] : nextOccluderId;
        if (role === 'target') {
            stableIds.set(snapshot.stableIds, rowOffset);
        } else {
            for (let index = 0; index < snapshot.gaussianCount; index += 1) {
                stableIds[rowOffset + index] = nextOccluderId;
                nextOccluderId += 1;
            }
        }
        copyRows(means, rowOffset * 3, snapshot.means);
        copyRows(rotationsXyzw, rowOffset * 4, snapshot.rotationsXyzw);
        copyRows(logScales, rowOffset * 3, snapshot.logScales);
        copyRows(logitOpacities, rowOffset, snapshot.logitOpacities);
        copyRows(dc, rowOffset * 3, snapshot.dc);
        if (snapshot.shFloatCountPerGaussian > 0) {
            for (let index = 0; index < snapshot.gaussianCount; index += 1) {
                sh.set(
                    snapshot.sh.subarray(
                        index * snapshot.shFloatCountPerGaussian,
                        (index + 1) * snapshot.shFloatCountPerGaussian
                    ),
                    (rowOffset + index) * shFloatCountPerGaussian
                );
            }
        }
        entries.push(
            Object.freeze({
                splatId: source.splatId,
                role,
                sourceContentDigest: snapshot.contentDigest,
                rowOffset,
                rowCount: snapshot.gaussianCount,
                renderIdStart
            })
        );
        rowOffset += snapshot.gaussianCount;
    });

    const authoritativeRenderScope: AuthoritativeRenderScope = Object.freeze({
        policyId: AUTHORITATIVE_RENDER_SCOPE_POLICY_ID,
        targetSplatId: target.splatId,
        identityDigest: scopeIdentityDigest(target.splatId, sources),
        entries: Object.freeze(entries)
    });
    const availableBands = { 0: 0, 9: 1, 24: 2, 45: 3 }[
        shFloatCountPerGaussian
    ];
    const configuredBands = Math.max(
        ...sources.map((source) => source.snapshot.renderConfiguration.shBands)
    );

    return buildPackedSceneSnapshot({
        sceneId: target.snapshot.sceneId,
        coordinateConvention: target.snapshot.coordinateConvention,
        stableIdSchema: target.snapshot.stableIdSchema,
        appearancePolicy: `effective-editor-dc-sh-bands-${availableBands}`,
        renderConfiguration: {
            ...target.snapshot.renderConfiguration,
            backgroundRgba: [
                ...target.snapshot.renderConfiguration.backgroundRgba
            ] as readonly [number, number, number, number],
            shBands: Math.min(configuredBands, availableBands)
        },
        stableIds,
        means,
        rotationsXyzw,
        logScales,
        logitOpacities,
        dc,
        sh,
        shFloatCountPerGaussian,
        authoritativeRenderScope
    });
};

export type { RenderScopeSnapshotInput };
