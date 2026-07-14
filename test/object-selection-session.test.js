const assert = require("node:assert/strict");
const test = require("node:test");

const {
  ObjectSelectionSession,
  anchorFrameSetVersion,
  assertCompleteMaskSet,
} = require("../.test-dist/src/object-selection-session.js");

const createSnapshot = (stableIds = [1, 2, 3, 7, 9, 11]) => ({
  protocolVersion: "1",
  sceneId: "scene-1",
  sceneVersion: "snapshot-v1",
  gaussianCount: stableIds.length,
  coordinateConvention: "right-handed/world",
  attributeSchema: "gaussian-v1",
  stableIdSchema: "uint32",
  appearancePolicy: "dc-sh-v1",
  renderConfiguration: {
    version: "effective-rgb-v1",
    backgroundRgba: [0, 0, 0, 1],
    alphaMode: "opaque-background",
    shBands: 3,
    rasterizer: "playcanvas-gsplat-classic",
  },
  gaussians: stableIds.map((stableId) => ({
    stableId,
    mean: [stableId, 0, 0],
    rotation: [0, 0, 0, 1],
    logScale: [0, 0, 0],
    logitOpacity: 0,
    dc: [0, 0, 0],
    sh: [],
  })),
});

const createScene = (snapshot = createSnapshot(), lockedIds = new Set()) => ({
  getSnapshot: () => snapshot,
  isCurrent: (value) => value === snapshot,
  isLocked: (stableId) => lockedIds.has(stableId),
});

const newSessionInput = () => ({
  target: {
    targetSplatId: "splat-1",
  },
  prompt: {
    promptId: "prompt-1",
    viewId: "anchor-view",
    frameDigest: "sha256:anchor-frame-v1",
    frameWidth: 64,
    frameHeight: 48,
    xPx: 10,
    yPx: 20,
    polarity: "include",
  },
  scene: createScene(),
  requestContext: {
    deterministicSeed: "seed-1",
    frameSetVersion: "anchor:anchor-view",
    frameSet: {
      frameSetId: "frames-1",
      frameSetVersion: "anchor:anchor-view",
      orderedViews: [
        {
          viewId: "anchor-view",
          frameDigest: "sha256:anchor-frame-v1",
          width: 64,
          height: 48,
        },
      ],
    },
    modelManifestDigest: "sha256:model-v1",
  },
});

const additionalPrompt = {
  promptId: "prompt-2",
  viewId: "anchor-view",
  frameDigest: "sha256:anchor-frame-v1",
  frameWidth: 64,
  frameHeight: 48,
  xPx: 30,
  yPx: 40,
  polarity: "exclude",
};

const removalPrompt = {
  promptId: "prompt-3",
  viewId: "anchor-view",
  frameDigest: "sha256:anchor-frame-v1",
  frameWidth: 64,
  frameHeight: 48,
  xPx: 50,
  yPx: 60,
  polarity: "exclude",
};

const candidate = {
  selectedIds: [3, 7],
  uncertainIds: [9],
  rejectedIds: [1, 2, 11],
  lockedIdsFiltered: 0,
};

const maskSetForRequest = (request) => ({
  status: "complete",
  requestId: request.requestId,
  sessionId: request.sessionId,
  promptLogRevision: request.promptLogRevision,
  frameSetVersion: request.frameSetVersion,
  modelManifestDigest: request.modelManifestDigest,
  threshold: 0,
  tracks: [
    {
      trackId: "primary",
      role: "include",
      frames: request.frameSet.orderedViews.map((view) => ({
        viewId: view.viewId,
        status: "accepted",
        binaryMask: {
          encoding: "sparse-points-v1",
          width: view.width,
          height: view.height,
          foregroundPixels: [[0, 0]],
        },
      })),
    },
  ],
});

const previewResponse = (request, result = candidate) => ({
  status: "complete",
  requestId: request.requestId,
  sessionId: request.sessionId,
  targetSplatId: request.target.targetSplatId,
  sceneId: request.snapshot.sceneId,
  sceneVersion: request.snapshot.sceneVersion,
  operation: request.operation,
  correctionRound: request.correctionRound,
  deterministicSeed: request.deterministicSeed,
  promptLogRevision: request.promptLogRevision,
  frameSetVersion: request.frameSetVersion,
  renderConfigVersion: request.renderConfigVersion,
  modelManifestDigest: request.modelManifestDigest,
  maskSet: maskSetForRequest(request),
  ...result,
});

class DeterministicSelectionServiceAdapter {
  constructor() {
    this.openRequests = [];
    this.previewRequests = [];
    this.cancelledUpdates = [];
    this.closedSessions = [];
  }

  async openSession(request) {
    this.openRequests.push(request);
    return "deterministic-session";
  }

  async updatePreview(request) {
    this.previewRequests.push(request);
    return previewResponse(request);
  }

  async cancelUpdate(sessionId, requestId) {
    this.cancelledUpdates.push({ sessionId, requestId });
  }

  async closeSession(sessionId) {
    this.closedSessions.push(sessionId);
  }
}

class RecordingSelectionEditor {
  constructor() {
    this.selection = [1, 2];
    this.history = [];
  }

  captureSelection() {
    return [...this.selection];
  }

  async commitSelection(selectedIds) {
    this.selection = [...selectedIds];
    this.history.push([...selectedIds]);
  }

  async restoreSelection(entrySelection) {
    this.selection = [...entrySelection];
  }
}

test("keeps a New preview transient until Confirm", async () => {
  const adapter = new DeterministicSelectionServiceAdapter();
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor,
  });
  const start = newSessionInput();

  await session.startNew(start);
  session.setMode("Add");
  session.stagePrompt(additionalPrompt);
  session.setMode("Remove");
  session.stagePrompt(removalPrompt);
  await session.updatePreview();

  assert.deepEqual(adapter.openRequests, [
    {
      target: start.target,
      prompt: start.prompt,
      snapshot: start.scene.getSnapshot(),
      requestContext: start.requestContext,
    },
  ]);
  assert.deepEqual(adapter.previewRequests, [
    {
      sessionId: "deterministic-session",
      requestId: "request-1",
      target: start.target,
      targetSplatId: start.target.targetSplatId,
      sceneId: start.scene.getSnapshot().sceneId,
      sceneVersion: start.scene.getSnapshot().sceneVersion,
      operation: "Remove",
      correctionRound: 0,
      deterministicSeed: start.requestContext.deterministicSeed,
      promptLogRevision: 3,
      frameSetVersion: start.requestContext.frameSetVersion,
      renderConfigVersion:
        start.scene.getSnapshot().renderConfiguration.version,
      modelManifestDigest: start.requestContext.modelManifestDigest,
      frameSet: start.requestContext.frameSet,
      snapshot: start.scene.getSnapshot(),
      promptLog: [
        {
          operation: "New",
          prompt: start.prompt,
        },
        {
          operation: "Add",
          prompt: additionalPrompt,
        },
        {
          operation: "Remove",
          prompt: removalPrompt,
        },
      ],
    },
  ]);
  assert.deepEqual(session.state.candidate, candidate);
  assert.deepEqual(editor.selection, [1, 2]);
  assert.deepEqual(editor.history, []);

  await session.confirm();

  assert.deepEqual(editor.selection, [3, 7]);
  assert.deepEqual(editor.history, [[3, 7]]);
  assert.deepEqual(adapter.closedSessions, ["deterministic-session"]);
});

test("Cancel restores the entry selection without adding history", async () => {
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: new DeterministicSelectionServiceAdapter(),
    editor,
  });

  await session.startNew(newSessionInput());
  await session.updatePreview();
  editor.selection = [99];
  await session.cancel();

  assert.equal(session.state.status, "idle");
  assert.equal(session.state.candidate, null);
  assert.deepEqual(editor.selection, [1, 2]);
  assert.deepEqual(editor.history, []);
});

test("pins Anchor PNG bytes in the immutable Frame Set without copying them into the Prompt Log", async () => {
  const adapter = new DeterministicSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });
  const start = newSessionInput();
  start.requestContext.frameSet.orderedViews[0].imagePngBase64 = "iVBORw0KGgo=";

  await session.startNew(start);
  start.requestContext.frameSet.orderedViews[0].imagePngBase64 =
    "changed-after-start";
  await session.updatePreview();

  assert.equal(
    adapter.openRequests[0].requestContext.frameSet.orderedViews[0]
      .imagePngBase64,
    "iVBORw0KGgo="
  );
  assert.equal(
    Object.hasOwn(adapter.openRequests[0].prompt, "imagePngBase64"),
    false
  );
  assert.equal(
    Object.hasOwn(
      adapter.previewRequests[0].promptLog[0].prompt,
      "imagePngBase64"
    ),
    false
  );
});

test("derives target-scoped Frame Set versions for identical Anchor View bytes", () => {
  const digest = "sha256:identical-anchor-png";

  assert.equal(
    anchorFrameSetVersion("editor-splat:1", digest),
    "editor-splat:1:anchor:sha256:identical-anchor-png"
  );
  assert.notEqual(
    anchorFrameSetVersion("editor-splat:1", digest),
    anchorFrameSetVersion("editor-splat:2", digest)
  );
});

test("starts a fresh New session after cleanup", async () => {
  const adapter = new DeterministicSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew(newSessionInput());
  await session.updatePreview();
  await session.confirm();
  await session.startNew(newSessionInput());

  assert.equal(session.state.status, "ready");
  assert.equal(adapter.openRequests.length, 2);
});

test("cancels an in-flight preview without replacing the prior candidate", async () => {
  class DeferredSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    constructor() {
      super();
      this.resolvePreview = null;
    }

    async updatePreview(request) {
      this.previewRequests.push(request);
      return new Promise((resolve) => {
        this.resolvePreview = resolve;
      });
    }

    async cancelUpdate(sessionId, requestId) {
      await super.cancelUpdate(sessionId, requestId);
      this.resolvePreview(previewResponse(this.previewRequests.at(-1)));
    }
  }

  const adapter = new DeferredSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew(newSessionInput());
  const update = session.updatePreview();
  await session.cancelUpdate();
  await update;

  assert.equal(session.state.status, "ready");
  assert.equal(session.state.candidate, null);
  assert.deepEqual(adapter.cancelledUpdates, [
    {
      sessionId: "deterministic-session",
      requestId: "request-1",
    },
  ]);
});

test("keeps the prior preview usable when cancellation races a completed request", async () => {
  class FailingCancellationSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    constructor() {
      super();
      this.previewCount = 0;
      this.resolvePreview = null;
      this.rejectCancellation = null;
    }

    async updatePreview(request) {
      this.previewRequests.push(request);
      this.previewCount += 1;
      if (this.previewCount === 1) {
        return previewResponse(request);
      }
      return new Promise((resolve) => {
        this.resolvePreview = resolve;
      });
    }

    async cancelUpdate(sessionId, requestId) {
      this.cancelledUpdates.push({ sessionId, requestId });
      return new Promise((_resolve, reject) => {
        this.rejectCancellation = reject;
      });
    }
  }

  const adapter = new FailingCancellationSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew(newSessionInput());
  await session.updatePreview();
  const update = session.updatePreview();
  const cancel = session.cancelUpdate();
  adapter.resolvePreview(
    previewResponse(adapter.previewRequests.at(-1), {
      selectedIds: [11],
      uncertainIds: [],
      rejectedIds: [],
    })
  );
  await update;
  adapter.rejectCancellation(new Error("cancellation request failed"));

  await assert.rejects(cancel, /cancellation request failed/);
  assert.equal(session.state.status, "preview");
  assert.deepEqual(session.state.candidate, candidate);
});

test("makes preview cancellation single-flight", async () => {
  class DeferredCancellationSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    constructor() {
      super();
      this.resolvePreview = null;
      this.resolveCancellation = null;
    }

    async updatePreview(request) {
      this.previewRequests.push(request);
      return new Promise((resolve) => {
        this.resolvePreview = resolve;
      });
    }

    async cancelUpdate(sessionId, requestId) {
      this.cancelledUpdates.push({ sessionId, requestId });
      return new Promise((resolve) => {
        this.resolveCancellation = resolve;
      });
    }
  }

  const adapter = new DeferredCancellationSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew(newSessionInput());
  const update = session.updatePreview();
  const firstCancel = session.cancelUpdate();

  assert.equal(session.state.status, "cancellingUpdate");
  await assert.rejects(
    session.cancelUpdate(),
    /cannot run this command while cancellingUpdate/
  );
  assert.equal(adapter.cancelledUpdates.length, 1);

  adapter.resolveCancellation();
  await firstCancel;
  adapter.resolvePreview(previewResponse(adapter.previewRequests.at(-1)));
  await update;

  assert.equal(session.state.status, "ready");
});

test("retains a failed cleanup for retry without committing twice", async () => {
  class FailingOnceSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    async closeSession(sessionId) {
      await super.closeSession(sessionId);
      if (this.closedSessions.length === 1) {
        throw new Error("service cleanup failed");
      }
    }
  }

  const adapter = new FailingOnceSelectionServiceAdapter();
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor,
  });

  await session.startNew(newSessionInput());
  await session.updatePreview();
  await assert.rejects(session.confirm(), /service cleanup failed/);

  assert.equal(session.state.status, "closeFailed");
  assert.deepEqual(editor.history, [[3, 7]]);

  await session.retryCleanup();

  assert.equal(session.state.status, "idle");
  assert.deepEqual(editor.history, [[3, 7]]);
  assert.deepEqual(adapter.closedSessions, [
    "deterministic-session",
    "deterministic-session",
  ]);
});

test("accepts only a current, bound Companion result, filters locked IDs, and commits once", async () => {
  const snapshot = createSnapshot([3, 7, 9]);
  const lockedIds = new Set([7]);
  const scene = createScene(snapshot, lockedIds);
  class BoundSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    async updatePreview(request) {
      this.previewRequests.push(request);
      return previewResponse(request, {
        selectedIds: [3, 7],
        uncertainIds: [9],
        rejectedIds: [],
      });
    }
  }

  const adapter = new BoundSelectionServiceAdapter();
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor,
  });

  await session.startNew({
    ...newSessionInput(),
    scene,
  });
  await session.updatePreview();

  assert.deepEqual(adapter.previewRequests[0].snapshot, snapshot);
  assert.deepEqual(session.state.candidate, {
    selectedIds: [3],
    uncertainIds: [9],
    rejectedIds: [],
    lockedIdsFiltered: 1,
  });
  assert.deepEqual(editor.history, []);

  await session.confirm();

  assert.deepEqual(editor.history, [[3]]);
});

test("retains the prior Candidate Object Selection when scene, response bindings, or result IDs are stale", async () => {
  const snapshot = createSnapshot([3, 7, 9]);
  let current = true;
  const scene = {
    getSnapshot: () => snapshot,
    isCurrent: () => current,
    isLocked: () => false,
  };
  const initialCandidate = {
    selectedIds: [3],
    uncertainIds: [7],
    rejectedIds: [9],
    lockedIdsFiltered: 0,
  };
  let responseFor = (request) => previewResponse(request, initialCandidate);
  class ValidatingSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    async updatePreview(request) {
      this.previewRequests.push(request);
      return responseFor(request);
    }
  }
  const adapter = new ValidatingSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew({
    ...newSessionInput(),
    scene,
  });
  await session.updatePreview();
  assert.deepEqual(session.state.candidate, initialCandidate);

  current = false;
  await assert.rejects(session.updatePreview(), /Target Splat changed/);
  assert.equal(adapter.previewRequests.length, 1);
  assert.deepEqual(session.state.candidate, initialCandidate);

  current = true;
  responseFor = (request) => ({
    ...previewResponse(request, initialCandidate),
    sceneVersion: "snapshot-v0",
  });
  await assert.rejects(
    session.updatePreview(),
    /stale Object Selection request bindings/
  );
  assert.deepEqual(session.state.candidate, initialCandidate);

  responseFor = (request) => ({
    ...previewResponse(request, initialCandidate),
    deterministicSeed: "stale-seed",
  });
  await assert.rejects(
    session.updatePreview(),
    /stale Object Selection request bindings/
  );
  assert.deepEqual(session.state.candidate, initialCandidate);

  responseFor = (request) =>
    previewResponse(request, {
      selectedIds: [3],
      uncertainIds: [3],
      rejectedIds: [],
    });
  await assert.rejects(
    session.updatePreview(),
    /overlapping Candidate Object Selection/
  );
  assert.deepEqual(session.state.candidate, initialCandidate);

  responseFor = (request) =>
    previewResponse(request, {
      selectedIds: [13],
      uncertainIds: [],
      rejectedIds: [],
    });
  await assert.rejects(
    session.updatePreview(),
    /unknown selected Stable Gaussian ID/
  );
  assert.deepEqual(session.state.candidate, initialCandidate);

  responseFor = (request) =>
    previewResponse(request, {
      selectedIds: [3],
      uncertainIds: [],
      rejectedIds: [],
    });
  await assert.rejects(
    session.updatePreview(),
    /incomplete Candidate Object Selection/
  );
  assert.deepEqual(session.state.candidate, initialCandidate);
});

test("rejects a missing or malformed complete Mask Set before candidate lifting", async () => {
  let responseFor = (request) => previewResponse(request);
  class ValidatingSelectionServiceAdapter extends DeterministicSelectionServiceAdapter {
    async updatePreview(request) {
      this.previewRequests.push(request);
      return responseFor(request);
    }
  }

  const adapter = new ValidatingSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });

  await session.startNew(newSessionInput());
  await session.updatePreview();
  assert.deepEqual(session.state.candidate, candidate);

  responseFor = (request) => {
    const response = previewResponse(request);
    delete response.maskSet;
    return response;
  };
  await assert.rejects(
    session.updatePreview(),
    /complete, version-bound Mask Set/
  );
  assert.deepEqual(session.state.candidate, candidate);

  responseFor = (request) => ({
    ...previewResponse(request),
    maskSet: {
      ...maskSetForRequest(request),
      tracks: [
        {
          trackId: "primary",
          role: "include",
          frames: [
            {
              viewId: "anchor-view",
              status: "accepted",
              binaryMask: {
                encoding: "sparse-points-v1",
                width: 1,
                height: 1,
                foregroundPixels: [[0, 0]],
              },
            },
          ],
        },
      ],
    },
  });
  await assert.rejects(
    session.updatePreview(),
    /complete, version-bound Mask Set/
  );
  assert.deepEqual(session.state.candidate, candidate);
});

test("rejects a whitespace-only neutral Mask Set reason", async () => {
  const adapter = new DeterministicSelectionServiceAdapter();
  const session = new ObjectSelectionSession({
    selectionService: adapter,
    editor: new RecordingSelectionEditor(),
  });
  const start = newSessionInput();
  start.requestContext.frameSet.orderedViews.push({
    viewId: "detail-view",
    frameDigest: "sha256:detail-frame-v1",
    width: 64,
    height: 48,
  });

  await session.startNew(start);
  await session.updatePreview();
  const request = adapter.previewRequests.at(-1);
  const maskSet = maskSetForRequest(request);
  maskSet.tracks[0].frames[1] = {
    viewId: "detail-view",
    status: "rejected",
    rejectionReason: "   ",
  };

  assert.throws(
    () => assertCompleteMaskSet(maskSet, request),
    /complete, version-bound Mask Set/
  );
});
