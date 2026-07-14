import { Mat3, Mat4, Quat, Vec3 } from 'playcanvas';

import { ColorGrade, dcDecode, dcEncode } from './color-grade';
import type { StableGaussianIdMap } from './object-selection-session-editor';
import {
    assertSceneSnapshot,
    freezeSceneSnapshot,
    type SceneSnapshot,
    type SceneSnapshotBinding,
    type SceneSnapshotGaussian,
    type SceneSnapshotRenderConfiguration,
    type StableGaussianId
} from './scene-snapshot';
import { SHRotation } from './sh-utils';
import type { Splat } from './splat';
import { State } from './splat-state';

const stableIdsBySplat = new WeakMap<Splat, Uint32Array>();

const fnv1a64 = (text: string) => {
    let hash = 0xcbf29ce484222325n;
    const prime = 0x100000001b3n;
    const mask = 0xffffffffffffffffn;
    new TextEncoder().encode(text).forEach((byte) => {
        hash ^= BigInt(byte);
        hash = (hash * prime) & mask;
    });
    return hash.toString(16).padStart(16, '0');
};

const tuple3 = (x: number, y: number, z: number): [number, number, number] => [x, y, z];
const tuple4 = (x: number, y: number, z: number, w: number): [number, number, number, number] => [x, y, z, w];

const requiredFloatProperty = (splat: Splat, name: string) => {
    const property = splat.splatData.getProp(name) as Float32Array | undefined;
    if (!property) {
        throw new Error(`Target Splat cannot build a Scene Snapshot without ${name}.`);
    }
    return property;
};

const shProperties = (splat: Splat) => {
    const properties: Float32Array[] = [];
    for (let index = 0; index < 45; ++index) {
        const property = splat.splatData.getProp(`f_rest_${index}`) as Float32Array | undefined;
        if (!property) {
            break;
        }
        properties.push(property);
    }
    if (properties.length % 3 !== 0) {
        throw new Error('Target Splat has an incomplete spherical-harmonic appearance schema.');
    }
    return properties;
};

const shBandCount = (coefficientsPerChannel: number) => {
    return ({ 0: 0, 3: 1, 8: 2, 15: 3 } as Record<number, number>)[coefficientsPerChannel] ?? -1;
};

// Stable IDs are allocated after loading/reordering, remain editor-owned, and
// are intentionally separate from the service's renderer/tensor positions.
class SplatSceneSnapshotBinding implements SceneSnapshotBinding, StableGaussianIdMap {
    private splat: Splat;
    private sceneId: string;
    private stableIds: Uint32Array;
    private getRenderConfiguration: () => SceneSnapshotRenderConfiguration;

    constructor(options: {
        splat: Splat;
        sceneId: string;
        getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    }) {
        if (!options.sceneId) {
            throw new Error('Target Splat Scene Snapshot requires a non-empty scene ID.');
        }
        this.splat = options.splat;
        this.sceneId = options.sceneId;
        this.getRenderConfiguration = options.getRenderConfiguration;
        this.stableIds = this.getOrCreateStableIds();
    }

    getSnapshot() {
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
            throw new Error('Target Splat uses an unsupported spherical-harmonic band count.');
        }
        const transformIndices = splat.transformTexture.getSource() as unknown as ArrayLike<number> | null;
        const colorGrade = new ColorGrade(splat);
        const gaussians: SceneSnapshotGaussian[] = [];

        for (let index = 0; index < splat.splatData.numSplats; ++index) {
            if ((state[index] & State.deleted) !== 0) {
                continue;
            }

            const transform = new Mat4().copy(splat.worldTransform);
            const transformIndex = transformIndices?.[index] ?? 0;
            if (transformIndex > 0) {
                const paletteTransform = new Mat4();
                splat.transformPalette.getTransform(transformIndex, paletteTransform);
                transform.mul2(transform, paletteTransform);
            }

            const mean = new Vec3(x[index], y[index], z[index]);
            transform.transformPoint(mean, mean);
            const transformRotation = new Quat().setFromMat4(transform);
            const rotation = new Quat(rot1[index], rot2[index], rot3[index], rot0[index]);
            rotation.mul2(transformRotation, rotation);
            const transformScale = transform.getScale(new Vec3());

            const dc = tuple3(dc0[index], dc1[index], dc2[index]);
            if (colorGrade.hasTint) {
                const color = {
                    r: dcDecode(dc[0]),
                    g: dcDecode(dc[1]),
                    b: dcDecode(dc[2])
                };
                colorGrade.applyDC(color);
                dc[0] = dcEncode(color.r);
                dc[1] = dcEncode(color.g);
                dc[2] = dcEncode(color.b);
            }

            const effectiveSh = sh.map(property => property[index]);
            if (shCoefficients > 0) {
                const shRotation = new SHRotation(new Mat3().setFromQuat(transformRotation));
                for (let channel = 0; channel < 3; ++channel) {
                    const offset = channel * shCoefficients;
                    const coefficients = effectiveSh.slice(offset, offset + shCoefficients);
                    shRotation.apply(coefficients);
                    effectiveSh.splice(offset, shCoefficients, ...coefficients);
                }
                if (colorGrade.hasTint) {
                    for (let coefficient = 0; coefficient < shCoefficients; ++coefficient) {
                        const color = {
                            r: effectiveSh[coefficient],
                            g: effectiveSh[coefficient + shCoefficients],
                            b: effectiveSh[coefficient + shCoefficients * 2]
                        };
                        colorGrade.applySH(color);
                        effectiveSh[coefficient] = color.r;
                        effectiveSh[coefficient + shCoefficients] = color.g;
                        effectiveSh[coefficient + shCoefficients * 2] = color.b;
                    }
                }
            }

            gaussians.push({
                stableId: this.stableIds[index],
                mean: tuple3(mean.x, mean.y, mean.z),
                rotation: tuple4(rotation.x, rotation.y, rotation.z, rotation.w),
                logScale: tuple3(
                    Math.log(Math.exp(scale0[index]) * transformScale.x),
                    Math.log(Math.exp(scale1[index]) * transformScale.y),
                    Math.log(Math.exp(scale2[index]) * transformScale.z)
                ),
                logitOpacity: colorGrade.applyOpacity(opacity[index]),
                dc,
                sh: effectiveSh
            });
        }

        const configuredRender = this.getRenderConfiguration();
        const renderConfiguration: SceneSnapshotRenderConfiguration = {
            version: configuredRender.version,
            backgroundRgba: tuple4(...configuredRender.backgroundRgba),
            alphaMode: configuredRender.alphaMode,
            shBands: Math.min(configuredRender.shBands, bandCount),
            rasterizer: configuredRender.rasterizer
        };
        const content = {
            protocolVersion: '1',
            sceneId: this.sceneId,
            gaussianCount: gaussians.length,
            coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
            attributeSchema: `mean:f32x3;rotation:f32x4;logScale:f32x3;logitOpacity:f32;dc:f32x3;sh:f32x${sh.length}`,
            stableIdSchema: 'uint32' as const,
            appearancePolicy: `effective-editor-dc-sh-bands-${bandCount}`,
            renderConfiguration,
            gaussians
        };
        const snapshot: SceneSnapshot = {
            ...content,
            sceneVersion: `fnv1a64:${fnv1a64(JSON.stringify(content))}`
        };
        assertSceneSnapshot(snapshot);
        return freezeSceneSnapshot(snapshot);
    }

    isCurrent(snapshot: SceneSnapshot) {
        const current = this.getSnapshot();
        return current.sceneId === snapshot.sceneId && current.sceneVersion === snapshot.sceneVersion;
    }

    isLocked(stableId: StableGaussianId) {
        const index = this.indexForStableId(stableId);
        return index !== null && (this.splat.state.data[index] & State.locked) !== 0;
    }

    toStableGaussianIds(indices: readonly number[]) {
        return indices.map((index) => {
            if (!Number.isInteger(index) || index < 0 || index >= this.stableIds.length) {
                throw new Error('Cannot resolve an out-of-range Target Splat index to a Stable Gaussian ID.');
            }
            return this.stableIds[index];
        });
    }

    toSplatIndices(stableIds: readonly StableGaussianId[]) {
        return Uint32Array.from(stableIds.map((stableId) => {
            const index = this.indexForStableId(stableId);
            if (index === null) {
                throw new Error('Cannot resolve an unknown Stable Gaussian ID in this Target Splat.');
            }
            return index;
        }));
    }

    private getOrCreateStableIds() {
        const count = this.splat.splatData.numSplats;
        if (count > 0x100000000) {
            throw new Error('Target Splat exceeds the uint32 Stable Gaussian ID limit.');
        }
        const existing = stableIdsBySplat.get(this.splat);
        if (existing && existing.length === count) {
            return existing;
        }
        const stableIds = new Uint32Array(count);
        for (let index = 0; index < count; ++index) {
            stableIds[index] = index;
        }
        stableIdsBySplat.set(this.splat, stableIds);
        return stableIds;
    }

    private indexForStableId(stableId: StableGaussianId) {
        if (!Number.isInteger(stableId) || stableId < 0 || stableId >= this.stableIds.length) {
            return null;
        }
        return this.stableIds[stableId] === stableId ? stableId : null;
    }
}

export { SplatSceneSnapshotBinding };
