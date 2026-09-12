import { Mat4, Quat, Vec3 } from 'playcanvas';

import { SelectOp } from '../edit-ops';
import { Events } from '../events';
import { GaussianInstances } from '../gaussian-instances';
import { IndexRanges } from '../index-ranges';
import { PermutedChunkSource } from '../io/read/loader';
import { Scene } from '../scene';
import { Splat } from '../splat';

// Independent worked example: T(10,20,30) * Rz(90) * S(2,3,4)
// maps these local centers to the literal world centers below.
const localCenters = [[1, 0, -2], [0, 1, -2], [-1, 0, -2], [0, -1, -2]];
const worldCenters = [[10, 22, 22], [7, 20, 22], [10, 18, 22], [13, 20, 22]];

const equal = (actual: ArrayLike<number>, expected: ArrayLike<number>) => {
    return actual.length === expected.length && Array.from(actual).every((value, i) => value === expected[i]);
};

// This owns a command-queue task because native GPU processors share readback
// storage. Call directly, without wrapping it in another queue task.
const checkNativeIdentity = async (scene: Scene, loaded: Splat) => {
    return await scene.events.invoke('queue', async () => {
        const { resource } = loaded;
        const { source } = resource;
        const device = scene.graphicsDevice;
        if (loaded.instances.count < 2) {
            throw new Error('Identity fixture requires at least two loaded instances');
        }

        const firstRow = loaded.instances.sourceRow[Math.floor(loaded.instances.count / 2)];
        const secondRow = loaded.instances.sourceRow[0];
        const rows = new Uint32Array([firstRow, firstRow, secondRow, firstRow]);
        const position = resource.sourcePool.acquire('position', source.meta.layouts.position, rows.length);
        let positions: Float32Array;
        try {
            await source.read({ indices: rows, indexOffset: 0, count: rows.length, position });
            positions = new Float32Array(position.data, 0, rows.length * 3).slice();
        } finally {
            position.release();
        }

        // Capacity four is intentional for this disposable fixture. Repeated
        // rows exercise renderer identity; restoreMissing/cloning is not tested.
        const instances = GaussianInstances.fromRecords(
            device, 4, rows, new Uint8Array([0, 0, 2, 1]), new Uint32Array(4)
        );
        const fixture = new Splat(loaded.asset, new Quat(), instances);
        const flagsBefore = loaded.instances.flags.slice(0, loaded.instances.count);
        const activeLayer = scene.events.invoke('selection');
        let historyApplyEvents = 0;
        const historyListener = scene.events.on('edit.apply', () => historyApplyEvents++);
        let stateEvents = 0;
        // Share the native GPU processors/camera, but keep disposable fixture
        // notifications away from the editor status bar and selection listeners.
        const fixtureScene: Scene = Object.create(scene);
        fixtureScene.events = new Events();
        const listener = fixtureScene.events.on('splat.stateChanged', (splat: Splat) => {
            if (splat === fixture) stateEvents++;
        });

        // Native compute reads splat.scene.camera; the fixture is deliberately
        // absent from scene.elements, rendering placements and the edit history.
        fixture.scene = fixtureScene;
        try {
            for (let i = 0; i < rows.length; i++) {
                const paletteIndex = fixture.transformPalette.alloc();
                const target = localCenters[i];
                const translation = new Vec3(
                    target[0] - positions[i * 3],
                    target[1] - positions[i * 3 + 1],
                    target[2] - positions[i * 3 + 2]
                );
                fixture.transformPalette.setTransform(paletteIndex, new Mat4().setTranslate(translation.x, translation.y, translation.z));
                instances.setTransformIndex(i, paletteIndex);
            }
            fixture.entity.setLocalPosition(10, 20, 30);
            fixture.entity.setLocalEulerAngles(0, 0, 90);
            fixture.entity.setLocalScale(2, 3, 4);
            instances.flush();

            const probe = async () => {
                const hits: number[][] = [];
                for (const center of worldCenters) {
                    const transform = new Mat4().setTRS(
                        new Vec3(center[0], center[1], center[2]), new Quat(), new Vec3(0.05, 0.05, 0.05)
                    );
                    const mask = await scene.dataProcessor.intersect({ sphere: { transform, footprint: 0 } }, fixture);
                    try {
                        hits.push(Array.from({ length: instances.count }, (_, i) => i).filter(i => mask[i] === 255));
                    } finally {
                        scene.dataProcessor.releaseMask(mask);
                    }
                }
                return hits;
            };
            const hitsBefore = await probe();
            const expectedBefore = [[0], [1], [2], [3]];
            const transformPass = hitsBefore.every((hits, i) => equal(hits, expectedBefore[i]));

            // Direct operation on the fixture tests the native selection rules
            // and undo without registering an operation in the user's history.
            const selection = new SelectOp(fixture, 'set', new Uint32Array([0, 2]));
            await selection.do();
            const selectedFlags = Array.from(instances.flags.subarray(0, instances.count));
            await selection.undo();
            const selectionRestored = equal(instances.flags.subarray(0, instances.count), [0, 0, 2, 1]);
            selection.destroy();

            const capturedCount = instances.count;
            const capturedPalette = instances.transformIndex(0);
            const eventsBeforeRemove = stateEvents;
            const removed = instances.remove(IndexRanges.fromPredicate(instances.count, i => i === 0));
            await fixture.updateState();
            const hitsAfter = await probe();
            const expectedAfter = [[], [0], [1], [2]];
            const compactionRows = Array.from(instances.sourceRow.subarray(0, instances.count));
            const compactionFlags = Array.from(instances.flags.subarray(0, instances.count));
            const compactionPass = hitsAfter.every((hits, i) => equal(hits, expectedAfter[i])) &&
                equal(compactionRows, [firstRow, secondRow, firstRow]) && equal(compactionFlags, [0, 2, 1]);
            const invalidation = {
                stateChangedEmitted: stateEvents > eventsBeforeRemove,
                capturedCountInvalid: capturedCount !== instances.count,
                staleInstanceZeroRetargeted: capturedPalette !== instances.transformIndex(0),
                sameSourceRowCannotDistinguishDuplicates: instances.sourceRow[0] === rows[0],
                diagnosticResultRejection: 'not tested by this fixture'
            };
            instances.insert(removed);
            await fixture.updateState();
            const restoredHits = await probe();
            const restored = restoredHits.every((hits, i) => equal(hits, expectedBefore[i])) &&
                equal(instances.sourceRow.subarray(0, instances.count), rows);

            // PLY deleted bit 4 removes a record on load. It is not a live flag.
            const deleted = new GaussianInstances(device, 4, new Uint8Array([0, 4, 2, 1]));
            const deletedOnLoad = {
                count: deleted.count,
                rows: Array.from(deleted.sourceRow.subarray(0, deleted.count)),
                flags: Array.from(deleted.flags.subarray(0, deleted.count))
            };
            deleted.destroy();
            const deletedPass = deletedOnLoad.count === 3 && equal(deletedOnLoad.rows, [0, 2, 3]) &&
                equal(deletedOnLoad.flags, [0, 2, 1]);
            const unchanged = equal(loaded.instances.flags.subarray(0, loaded.instances.count), flagsBefore) &&
                scene.events.invoke('selection') === activeLayer && historyApplyEvents === 0;

            return {
                passed: transformPass && compactionPass && restored && selectionRestored &&
                    equal(selectedFlags, [1, 0, 2, 0]) && deletedPass && unchanged &&
                    invalidation.stateChangedEmitted && invalidation.capturedCountInvalid && invalidation.staleInstanceZeroRetargeted,
                fixture: 'shared native asset, four disposable instances, three references to one source row',
                sourceRows: Array.from(rows),
                inputRows: Array.from(rows, row => (source instanceof PermutedChunkSource ? source.order[row] : row)),
                sourcePositions: Array.from(positions),
                expectedWorldCenters: worldCenters,
                gpuCenterProbe: { expected: expectedBefore, actual: hitsBefore, radius: 0.025, passed: transformPass },
                nativeSelection: { expectedFlags: [1, 0, 2, 0], actualFlags: selectedFlags, undoRestored: selectionRestored },
                compaction: { expected: expectedAfter, actual: hitsAfter, rows: compactionRows, flags: compactionFlags, passed: compactionPass, restored },
                invalidation,
                deletedOnLoad,
                mainSelectionAndHistoryUnchanged: unchanged,
                historyApplyEvents,
                limits: [
                    'World positions are qualified within a 0.025-unit GPU sphere, not an exact position readback.',
                    'GPU center intersection includes locked instances; the separate Native SelectOp check enforces locked eligibility.',
                    'Picking, sort/compact draw payload, overlay invalidation and camera capture are not exercised by this fixture.',
                    'Duplicate rows are an adversarial identity fixture, not production cloning or restoreMissing qualification.'
                ]
            };
        } finally {
            listener.off();
            historyListener.off();
            fixture.scene = null;
            fixture.destroy();
        }
    });
};

export { checkNativeIdentity };
