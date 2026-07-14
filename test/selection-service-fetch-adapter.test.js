const assert = require("node:assert/strict");
const test = require("node:test");

const {
  FetchSelectionServiceAdapter,
} = require("../.test-dist/src/selection-service-fetch-adapter.js");

const snapshot = {
  protocolVersion: "1",
  sceneId: "scene-1",
  sceneVersion: "snapshot-v1",
  gaussianCount: 3,
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
  gaussians: [3, 7, 9].map((stableId) => ({
    stableId,
    mean: [stableId, 0, 0],
    rotation: [0, 0, 0, 1],
    logScale: [0, 0, 0],
    logitOpacity: 0,
    dc: [0, 0, 0],
    sh: [],
  })),
};

const start = {
  target: { targetSplatId: "splat-1" },
  prompt: {
    promptId: "prompt-1",
    viewId: "anchor-view",
    xPx: 10,
    yPx: 20,
    polarity: "include",
  },
  snapshot,
  requestContext: {
    deterministicSeed: "seed-1",
    frameSetVersion: "anchor:anchor-view",
    modelManifestDigest: "sha256:model-v1",
  },
};

const previewRequest = (sessionId = "session-1", requestId = "request-1") => ({
  sessionId,
  requestId,
  target: start.target,
  targetSplatId: start.target.targetSplatId,
  sceneId: snapshot.sceneId,
  sceneVersion: snapshot.sceneVersion,
  operation: "New",
  correctionRound: 0,
  deterministicSeed: start.requestContext.deterministicSeed,
  promptLogRevision: 1,
  frameSetVersion: start.requestContext.frameSetVersion,
  renderConfigVersion: snapshot.renderConfiguration.version,
  modelManifestDigest: start.requestContext.modelManifestDigest,
  promptLog: [{ operation: "New", prompt: start.prompt }],
  snapshot,
});

const previewBindings = (requestId) => ({
  requestId,
  sessionId: "session-1",
  targetSplatId: start.target.targetSplatId,
  sceneId: snapshot.sceneId,
  sceneVersion: snapshot.sceneVersion,
  operation: "New",
  correctionRound: 0,
  deterministicSeed: start.requestContext.deterministicSeed,
  promptLogRevision: 1,
  frameSetVersion: start.requestContext.frameSetVersion,
  renderConfigVersion: snapshot.renderConfiguration.version,
  modelManifestDigest: start.requestContext.modelManifestDigest,
});

test("registers one immutable Scene Snapshot, resends it after a cache miss, and retries the bound preview", async () => {
  const calls = [];
  const replies = [
    { status: "accepted", sessionId: "session-1" },
    { status: "registered", sceneId: snapshot.sceneId, sceneVersion: snapshot.sceneVersion },
    {
      status: "sceneCacheMiss",
      ...previewBindings("request-1"),
    },
    { status: "registered", sceneId: snapshot.sceneId, sceneVersion: snapshot.sceneVersion },
    {
      status: "complete",
      ...previewBindings("request-1"),
      selectedIds: [3],
      uncertainIds: [7],
      rejectedIds: [9],
    },
    {
      status: "complete",
      ...previewBindings("request-2"),
      selectedIds: [3],
      uncertainIds: [7],
      rejectedIds: [9],
    },
  ];
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      calls.push({ url, init, body: init.body ? JSON.parse(init.body) : null });
      return new Response(JSON.stringify(replies.shift()), { status: 200 });
    },
  });

  const sessionId = await adapter.openSession(start);
  const first = await adapter.updatePreview(previewRequest(sessionId));
  const second = await adapter.updatePreview(previewRequest(sessionId, "request-2"));

  assert.equal(sessionId, "session-1");
  assert.deepEqual(first.selectedIds, [3]);
  assert.deepEqual(second.uncertainIds, [7]);
  assert.deepEqual(
    calls.map((call) => `${call.init.method} ${call.url}`),
    [
      "POST https://companion.example:8787/object-selection-sessions",
      "PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
      "PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
    ]
  );
  assert.deepEqual(calls[1].body, snapshot);
  assert.equal(calls[2].body.snapshot, undefined);
  assert.equal(calls[2].body.modelManifestDigest, "sha256:model-v1");
  for (const call of calls) {
    assert.equal(call.init.mode, "cors");
    assert.equal(call.init.credentials, "omit");
    assert.equal(call.init.cache, "no-store");
  }
});
