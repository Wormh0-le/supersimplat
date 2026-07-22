import { Mat3, Mat4, Quat, Vec3 } from 'playcanvas';

import { ColorGrade, dcDecode, dcEncode } from './color-grade';
import type { StableGaussianIdMap } from './object-selection-session-editor';
import {
    freezeSceneSnapshot,
    type SceneSnapshot,
    type SceneSnapshotBinding,
    type SceneSnapshotGaussian,
    type SceneSnapshotRenderConfiguration,
    type StableGaussianId
} from './scene-snapshot';
import {
    buildPackedSceneSnapshot,
    type PackedSceneSnapshot,
    type SceneSnapshotShFloatCount
} from './scene-snapshot-binary';
import { SHRotation } from './sh-utils';
import type { Splat } from './splat';
import { State } from './splat-state';

const stableIdsBySplat = new WeakMap<Splat, Uint32Array>();

interface SplatSnapshotSemanticRevision {
    readonly renderStateToken: string;
    readonly geometryToken: string;
    readonly gaussianIdentityToken: string;
    readonly worldTransformToken: string;
}

interface EffectiveTransform {
    readonly rotation: Quat;
    readonly scale: Vec3;
    readonly shRotation: SHRotation | null;
    readonly matrix: Mat4;
}

const requiredFloatProperty = (splat: Splat, name: string) => {
    const property = splat.splatData.getProp(name) as Float32Array | undefined;
    if (!property) {
        throw new Error(
            `Target Splat cannot build a Scene Snapshot without ${name}.`
        );
    }
    return property;
};

const shProperties = (splat: Splat) => {
    const properties: Float32Array[] = [];
    for (let index = 0; index < 45; ++index) {
        const property = splat.splatData.getProp(`f_rest_${index}`) as
            Float32Array | undefined;
        if (!property) {
            break;
        }
        properties.push(property);
    }
    if (properties.length % 3 !== 0) {
        throw new Error(
            'Target Splat has an incomplete spherical-harmonic appearance schema.'
        );
    }
    return properties;
};

const shBandCount = (coefficientsPerChannel: number) => {
    return ({ 0: 0, 3: 1, 8: 2, 15: 3 } as Record<number, number>)[coefficientsPerChannel] ?? -1;
};

const semanticRenderConfigurationToken = (
    configuration: SceneSnapshotRenderConfiguration
): string => {
    return [
        configuration.version,
        configuration.alphaMode,
        configuration.rasterizer,
        configuration.shBands,
        ...configuration.backgroundRgba
    ].join('|');
};

const snapshotRevisionKey = (
    revision: SplatSnapshotSemanticRevision
): string => {
    return [
        revision.renderStateToken,
        revision.geometryToken,
        revision.gaussianIdentityToken,
        revision.worldTransformToken
    ].join('\u0000');
};

const copyRenderConfiguration = (
    configured: SceneSnapshotRenderConfiguration,
    bandCount: number
): SceneSnapshotRenderConfiguration => {
    return {
        version: configured.version,
        backgroundRgba: [
            configured.backgroundRgba[0],
            configured.backgroundRgba[1],
            configured.backgroundRgba[2],
            configured.backgroundRgba[3]
        ],
        alphaMode: configured.alphaMode,
        shBands: Math.min(configured.shBands, bandCount),
        rasterizer: configured.rasterizer
    };
};

const legacySceneSnapshotFromPacked = (
    packed: PackedSceneSnapshot
): SceneSnapshot => {
    const gaussians: SceneSnapshotGaussian[] = new Array(packed.gaussianCount);
    for (let index = 0; index < packed.gaussianCount; index += 1) {
        const meanOffset = index * 3;
        const rotationOffset = index * 4;
        const shOffset = index * packed.shFloatCountPerGaussian;
        const sh: number[] = new Array(packed.shFloatCountPerGaussian);
        for (let coefficient = 0; coefficient < sh.length; coefficient += 1) {
            sh[coefficient] = packed.sh[shOffset + coefficient];
        }
        gaussians[index] = {
            stableId: packed.stableIds[index],
            mean: [
                packed.means[meanOffset],
                packed.means[meanOffset + 1],
                packed.means[meanOffset + 2]
            ],
            rotation: [
                packed.rotationsXyzw[rotationOffset],
                packed.rotationsXyzw[rotationOffset + 1],
                packed.rotationsXyzw[rotationOffset + 2],
                packed.rotationsXyzw[rotationOffset + 3]
            ],
            logScale: [
                packed.logScales[meanOffset],
                packed.logScales[meanOffset + 1],
                packed.logScales[meanOffset + 2]
            ],
            logitOpacity: packed.logitOpacities[index],
            dc: [
                packed.dc[meanOffset],
                packed.dc[meanOffset + 1],
                packed.dc[meanOffset + 2]
            ],
            sh
        };
    }
    return freezeSceneSnapshot({
        protocolVersion: packed.protocolVersion,
        sceneId: packed.sceneId,
        sceneVersion: packed.sceneVersion,
        gaussianCount: packed.gaussianCount,
        coordinateConvention: packed.coordinateConvention,
        attributeSchema: packed.attributeSchema,
        stableIdSchema: packed.stableIdSchema,
        appearancePolicy: packed.appearancePolicy,
        renderConfiguration: packed.renderConfiguration,
        gaussians
    });
};

// Stable IDs are allocated after loading/reordering, remain editor-owned, and
// are intentionally separate from the service's renderer/tensor positions.
class SplatSceneSnapshotBinding implements SceneSnapshotBinding, StableGaussianIdMap {
    private readonly splat: Splat;
    private readonly sceneId: string;
    private stableIds: Uint32Array;
    private readonly getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    private packedSnapshot: PackedSceneSnapshot | null = null;
    private packedSnapshotRevision: string | null = null;
    private legacySnapshot: SceneSnapshot | null = null;

    constructor(options: {
        splat: Splat;
        sceneId: string;
        getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    }) {
        if (!options.sceneId) {
            throw new Error(
                'Target Splat Scene Snapshot requires a non-empty scene ID.'
            );
        }
        this.splat = options.splat;
        this.sceneId = options.sceneId;
        this.getRenderConfiguration = options.getRenderConfiguration;
        this.stableIds = this.getOrCreateStableIds();
    }

    /**
     * Current AI Select snapshots are Editor-owned SoA typed planes. The
     * cached digest is constructed only when a semantic editor dependency
     * changes; CurrentTargetContext checks use getSemanticRevision instead.
     */
    getPackedSnapshot(): PackedSceneSnapshot {
        const revision = this.getSemanticRevision();
        const revisionKey = snapshotRevisionKey(revision);
        if (
            this.packedSnapshot !== null &&
            this.packedSnapshotRevision === revisionKey
        ) {
            return this.packedSnapshot;
        }
        const packedSnapshot = this.buildPackedSnapshot();
        this.packedSnapshot = packedSnapshot;
        this.packedSnapshotRevision = revisionKey;
        this.legacySnapshot = null;
        return packedSnapshot;
    }

    /**
     * Legacy PoC compatibility only. New AI Select uses getPackedSnapshot and
     * never creates this per-Gaussian object compatibility view.
     */
    getSnapshot(): SceneSnapshot {
        const packedSnapshot = this.getPackedSnapshot();
        if (
            this.legacySnapshot !== null &&
            this.legacySnapshot.sceneVersion === packedSnapshot.sceneVersion
        ) {
            return this.legacySnapshot;
        }
        this.legacySnapshot = legacySceneSnapshotFromPacked(packedSnapshot);
        return this.legacySnapshot;
    }

    getSemanticRevision(): SplatSnapshotSemanticRevision {
        const configuredRender = this.getRenderConfiguration();
        return Object.freeze({
            renderStateToken: `render:${this.splat.aiSelectRenderStateRevision}:${semanticRenderConfigurationToken(configuredRender)}`,
            geometryToken: `geometry:${this.splat.aiSelectGeometryRevision}`,
            gaussianIdentityToken: `membership:${this.splat.aiSelectGaussianIdentityRevision}`,
            worldTransformToken: `world:${this.splat.aiSelectWorldTransformRevision}`
        });
    }

    isCurrent(snapshot: SceneSnapshot): boolean {
        return (
            this.packedSnapshot !== null &&
            this.packedSnapshotRevision ===
                snapshotRevisionKey(this.getSemanticRevision()) &&
            snapshot.sceneId === this.sceneId &&
            snapshot.sceneVersion === this.packedSnapshot.sceneVersion
        );
    }

    isLocked(stableId: StableGaussianId): boolean {
        const index = this.indexForStableId(stableId);
        return (
            index !== null &&
            (this.splat.state.data[index] & State.locked) !== 0
        );
    }

    toStableGaussianIds(indices: readonly number[]): StableGaussianId[] {
        return indices.map((index) => {
            if (
                !Number.isInteger(index) ||
                index < 0 ||
                index >= this.stableIds.length
            ) {
                throw new Error(
                    'Cannot resolve an out-of-range Target Splat index to a Stable Gaussian ID.'
                );
            }
            return this.stableIds[index];
        });
    }

    toSplatIndices(stableIds: readonly StableGaussianId[]): Uint32Array {
        return Uint32Array.from(
            stableIds.map((stableId) => {
                const index = this.indexForStableId(stableId);
                if (index === null) {
                    throw new Error(
                        'Cannot resolve an unknown Stable Gaussian ID in this Target Splat.'
                    );
                }
                return index;
            })
        );
    }

    private buildPackedSnapshot(): PackedSceneSnapshot {
        this.stableIds = this.getOrCreateStableIds();
        const { splat } = this;
        const state = splat.state.data;
        const x = requiredFloatProperty(splat, 'x');
        const y = requiredFloatProperty(splat, 'y');
        const z = requiredFloatProperty(splat, 'z');
        const rot0 = requiredFloatProperty(splat, 'rot_0');
        const rot1 = requiredFloatProperty(splat, 'rot_1');
        const rot2 = requiredFloatProperty(splat, 'rot_2');
        const rot3 = requiredFloatProperty(splat, 'rot_3');
        const scale0 = requiredFloatProperty(splat, 'scale_0');
        const scale1 = requiredFloatProperty(splat, 'scale_1');
        const scale2 = requiredFloatProperty(splat, 'scale_2');
        const opacity = requiredFloatProperty(splat, 'opacity');
        const dc0 = requiredFloatProperty(splat, 'f_dc_0');
        const dc1 = requiredFloatProperty(splat, 'f_dc_1');
        const dc2 = requiredFloatProperty(splat, 'f_dc_2');
        const sh = shProperties(splat);
        const shCoefficients = sh.length / 3;
        const bandCount = shBandCount(shCoefficients);
        if (bandCount < 0) {
            throw new Error(
                'Target Splat uses an unsupported spherical-harmonic band count.'
            );
        }
        let gaussianCount = 0;
        for (let index = 0; index < splat.splatData.numSplats; index += 1) {
            if ((state[index] & State.deleted) === 0) {
                gaussianCount += 1;
            }
        }
        const shFloatCountPerGaussian = sh.length as SceneSnapshotShFloatCount;
        const stableIds = new Uint32Array(gaussianCount);
        const means = new Float32Array(gaussianCount * 3);
        const rotationsXyzw = new Float32Array(gaussianCount * 4);
        const logScales = new Float32Array(gaussianCount * 3);
        const logitOpacities = new Float32Array(gaussianCount);
        const dc = new Float32Array(gaussianCount * 3);
        const effectiveSh = new Float32Array(gaussianCount * sh.length);
        const transformIndices =
            splat.transformTexture.getSource() as unknown as ArrayLike<number> | null;
        const colorGrade = new ColorGrade(splat);
        const worldTransform = new Mat4().copy(splat.worldTransform);
        const transforms = new Map<number, EffectiveTransform>();
        const getTransform = (transformIndex: number): EffectiveTransform => {
            const cached = transforms.get(transformIndex);
            if (cached) {
                return cached;
            }
            const matrix = new Mat4().copy(worldTransform);
            if (transformIndex > 0) {
                const paletteTransform = new Mat4();
                splat.transformPalette.getTransform(
                    transformIndex,
                    paletteTransform
                );
                matrix.mul2(matrix, paletteTransform);
            }
            const rotation = new Quat().setFromMat4(matrix);
            const result: EffectiveTransform = {
                matrix,
                rotation,
                scale: matrix.getScale(new Vec3()),
                shRotation: shCoefficients > 0 ? new SHRotation(new Mat3().setFromQuat(rotation)) : null
            };
            transforms.set(transformIndex, result);
            return result;
        };
        const mean = new Vec3();
        const rotation = new Quat();
        const dcColor = { r: 0, g: 0, b: 0 };
        const shColor = { r: 0, g: 0, b: 0 };
        const shScratch = new Float32Array(sh.length);
        const shChannelScratch = new Float32Array(shCoefficients);
        let targetIndex = 0;

        for (
            let sourceIndex = 0;
            sourceIndex < splat.splatData.numSplats;
            sourceIndex += 1
        ) {
            if ((state[sourceIndex] & State.deleted) !== 0) {
                continue;
            }
            const transform = getTransform(
                transformIndices?.[sourceIndex] ?? 0
            );
            const vectorOffset = targetIndex * 3;
            const rotationOffset = targetIndex * 4;
            const shOffset = targetIndex * sh.length;
            stableIds[targetIndex] = this.stableIds[sourceIndex];

            mean.set(x[sourceIndex], y[sourceIndex], z[sourceIndex]);
            transform.matrix.transformPoint(mean, mean);
            means[vectorOffset] = mean.x;
            means[vectorOffset + 1] = mean.y;
            means[vectorOffset + 2] = mean.z;

            rotation.set(
                rot1[sourceIndex],
                rot2[sourceIndex],
                rot3[sourceIndex],
                rot0[sourceIndex]
            );
            rotation.mul2(transform.rotation, rotation);
            rotationsXyzw[rotationOffset] = rotation.x;
            rotationsXyzw[rotationOffset + 1] = rotation.y;
            rotationsXyzw[rotationOffset + 2] = rotation.z;
            rotationsXyzw[rotationOffset + 3] = rotation.w;

            logScales[vectorOffset] = Math.log(
                Math.exp(scale0[sourceIndex]) * transform.scale.x
            );
            logScales[vectorOffset + 1] = Math.log(
                Math.exp(scale1[sourceIndex]) * transform.scale.y
            );
            logScales[vectorOffset + 2] = Math.log(
                Math.exp(scale2[sourceIndex]) * transform.scale.z
            );
            logitOpacities[targetIndex] = colorGrade.applyOpacity(
                opacity[sourceIndex]
            );

            if (colorGrade.hasTint) {
                dcColor.r = dcDecode(dc0[sourceIndex]);
                dcColor.g = dcDecode(dc1[sourceIndex]);
                dcColor.b = dcDecode(dc2[sourceIndex]);
                colorGrade.applyDC(dcColor);
                dc[vectorOffset] = dcEncode(dcColor.r);
                dc[vectorOffset + 1] = dcEncode(dcColor.g);
                dc[vectorOffset + 2] = dcEncode(dcColor.b);
            } else {
                dc[vectorOffset] = dc0[sourceIndex];
                dc[vectorOffset + 1] = dc1[sourceIndex];
                dc[vectorOffset + 2] = dc2[sourceIndex];
            }

            for (let channel = 0; channel < 3; channel += 1) {
                const channelOffset = channel * shCoefficients;
                for (
                    let coefficient = 0;
                    coefficient < shCoefficients;
                    coefficient += 1
                ) {
                    shChannelScratch[coefficient] =
                        sh[channelOffset + coefficient][sourceIndex];
                }
                transform.shRotation?.apply(shChannelScratch);
                shScratch.set(shChannelScratch, channelOffset);
            }
            if (colorGrade.hasTint) {
                for (
                    let coefficient = 0;
                    coefficient < shCoefficients;
                    coefficient += 1
                ) {
                    shColor.r = shScratch[coefficient];
                    shColor.g = shScratch[shCoefficients + coefficient];
                    shColor.b = shScratch[shCoefficients * 2 + coefficient];
                    colorGrade.applySH(shColor);
                    shScratch[coefficient] = shColor.r;
                    shScratch[shCoefficients + coefficient] = shColor.g;
                    shScratch[shCoefficients * 2 + coefficient] = shColor.b;
                }
            }
            effectiveSh.set(shScratch, shOffset);
            targetIndex += 1;
        }

        return buildPackedSceneSnapshot({
            sceneId: this.sceneId,
            coordinateConvention:
                'right-handed world coordinates; quaternion xyzw',
            stableIdSchema: 'uint32',
            appearancePolicy: `effective-editor-dc-sh-bands-${bandCount}`,
            renderConfiguration: copyRenderConfiguration(
                this.getRenderConfiguration(),
                bandCount
            ),
            stableIds,
            means,
            rotationsXyzw,
            logScales,
            logitOpacities,
            dc,
            sh: effectiveSh,
            shFloatCountPerGaussian
        });
    }

    private getOrCreateStableIds(): Uint32Array {
        const count = this.splat.splatData.numSplats;
        if (count > 0x100000000) {
            throw new Error(
                'Target Splat exceeds the uint32 Stable Gaussian ID limit.'
            );
        }
        const existing = stableIdsBySplat.get(this.splat);
        if (existing && existing.length === count) {
            return existing;
        }
        const stableIds = new Uint32Array(count);
        for (let index = 0; index < count; index += 1) {
            stableIds[index] = index;
        }
        stableIdsBySplat.set(this.splat, stableIds);
        return stableIds;
    }

    private indexForStableId(stableId: StableGaussianId): number | null {
        if (
            !Number.isInteger(stableId) ||
            stableId < 0 ||
            stableId >= this.stableIds.length
        ) {
            return null;
        }
        return this.stableIds[stableId] === stableId ? stableId : null;
    }
}

export { SplatSceneSnapshotBinding };

export type { SplatSnapshotSemanticRevision };
