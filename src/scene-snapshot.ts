// An editor-owned, immutable input to Selection Service inference. Service
// tensor rows and renderer sort order never cross this boundary as identity.
type StableGaussianId = number;

interface SceneSnapshotGaussian {
    stableId: StableGaussianId;
    mean: readonly [number, number, number];
    rotation: readonly [number, number, number, number];
    logScale: readonly [number, number, number];
    logitOpacity: number;
    dc: readonly [number, number, number];
    sh: readonly number[];
}

// Everything the service needs to reproduce the editor's inference RGB and
// contributor attribution. This stays inside the content version because a
// cache hit under different SH/background/alpha semantics is not safe.
interface SceneSnapshotRenderConfiguration {
    version: string;
    backgroundRgba: readonly [number, number, number, number];
    alphaMode: 'opaque-background';
    shBands: number;
    rasterizer: string;
}

interface SceneSnapshot {
    protocolVersion: string;
    sceneId: string;
    sceneVersion: string;
    gaussianCount: number;
    coordinateConvention: string;
    attributeSchema: string;
    stableIdSchema: 'uint32';
    appearancePolicy: string;
    renderConfiguration: SceneSnapshotRenderConfiguration;
    gaussians: readonly SceneSnapshotGaussian[];
}

// The binding stays in the editor. Only the immutable snapshot itself crosses
// the transport boundary. Locked state deliberately remains outside the
// snapshot version, so it can be filtered immediately before preview/commit.
interface SceneSnapshotBinding {
    getSnapshot(): SceneSnapshot;
    isCurrent(snapshot: SceneSnapshot): boolean;
    isLocked(stableId: StableGaussianId): boolean;
}

const isStableGaussianId = (value: unknown): value is StableGaussianId => {
    return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 0xffffffff;
};

const hasFiniteNumbers = (values: readonly number[], length: number) => {
    return values.length === length && values.every(value => Number.isFinite(value));
};

const assertSceneSnapshot = (snapshot: SceneSnapshot): void => {
    if (
        !snapshot.protocolVersion ||
        !snapshot.sceneId ||
        !snapshot.sceneVersion ||
        !snapshot.coordinateConvention ||
        !snapshot.attributeSchema ||
        !snapshot.appearancePolicy
    ) {
        throw new Error('Scene Snapshot must include a scene ID and immutable scene version.');
    }
    if (!Number.isInteger(snapshot.gaussianCount) || snapshot.gaussianCount < 0) {
        throw new Error('Scene Snapshot Gaussian count must be a non-negative integer.');
    }
    if (snapshot.gaussianCount !== snapshot.gaussians.length) {
        throw new Error('Scene Snapshot Gaussian count does not match its Gaussian records.');
    }
    if (snapshot.stableIdSchema !== 'uint32') {
        throw new Error('Scene Snapshot Stable Gaussian IDs must use the uint32 schema.');
    }
    const renderConfiguration = snapshot.renderConfiguration;
    if (
        !renderConfiguration ||
        !renderConfiguration.version ||
        renderConfiguration.alphaMode !== 'opaque-background' ||
        !renderConfiguration.rasterizer ||
        !Number.isInteger(renderConfiguration.shBands) ||
        renderConfiguration.shBands < 0 ||
        !hasFiniteNumbers(renderConfiguration.backgroundRgba, 4)
    ) {
        throw new Error('Scene Snapshot must include complete finite inference render configuration semantics.');
    }

    const ids = new Set<StableGaussianId>();
    snapshot.gaussians.forEach((gaussian) => {
        if (!isStableGaussianId(gaussian.stableId) || ids.has(gaussian.stableId)) {
            throw new Error('Scene Snapshot must contain unique unsigned 32-bit Stable Gaussian IDs.');
        }
        if (
            !hasFiniteNumbers(gaussian.mean, 3) ||
            !hasFiniteNumbers(gaussian.rotation, 4) ||
            !hasFiniteNumbers(gaussian.logScale, 3) ||
            !Number.isFinite(gaussian.logitOpacity) ||
            !hasFiniteNumbers(gaussian.dc, 3) ||
            !gaussian.sh.every(value => Number.isFinite(value))
        ) {
            throw new Error('Scene Snapshot Gaussian geometry and appearance must be finite numeric values.');
        }
        ids.add(gaussian.stableId);
    });
};

const freezeSceneSnapshot = (snapshot: SceneSnapshot): SceneSnapshot => {
    Object.freeze(snapshot.renderConfiguration.backgroundRgba);
    Object.freeze(snapshot.renderConfiguration);
    snapshot.gaussians.forEach((gaussian) => {
        Object.freeze(gaussian.mean);
        Object.freeze(gaussian.rotation);
        Object.freeze(gaussian.logScale);
        Object.freeze(gaussian.dc);
        Object.freeze(gaussian.sh);
        Object.freeze(gaussian);
    });
    Object.freeze(snapshot.gaussians);
    return Object.freeze(snapshot);
};

export { assertSceneSnapshot, freezeSceneSnapshot, isStableGaussianId };

export type {
    SceneSnapshot,
    SceneSnapshotBinding,
    SceneSnapshotGaussian,
    SceneSnapshotRenderConfiguration,
    StableGaussianId
};
