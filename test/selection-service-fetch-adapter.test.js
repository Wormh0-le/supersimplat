const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const test = require("node:test");
const { deflateSync } = require("node:zlib");

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
    frameDigest: "sha256:anchor-frame-v1",
    frameWidth: 64,
    frameHeight: 48,
    xPx: 10,
    yPx: 20,
    polarity: "include",
  },
  snapshot,
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
  frameSet: start.requestContext.frameSet,
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

const frameSetForBindings = (bindings) => ({
  ...start.requestContext.frameSet,
  frameSetVersion: bindings.frameSetVersion,
});

const coverageReport = (
  bindings,
  frameSet = frameSetForBindings(bindings)
) => ({
  frameSetVersion: bindings.frameSetVersion,
  renderConfigVersion: bindings.renderConfigVersion,
  attemptedViews: frameSet.orderedViews.length,
  acceptedViews: frameSet.orderedViews.length,
  rejectedViewCount: 0,
  status: "insufficient_coverage",
});

const maskSet = (bindings, frameSet = frameSetForBindings(bindings)) => ({
  status: "complete",
  requestId: bindings.requestId,
  sessionId: bindings.sessionId,
  promptLogRevision: bindings.promptLogRevision,
  frameSetVersion: bindings.frameSetVersion,
  modelManifestDigest: bindings.modelManifestDigest,
  threshold: 0.5,
  tracks: [
    {
      trackId: "primary",
      role: "include",
      frames: frameSet.orderedViews.map((view) => ({
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

const evidenceSnapshot = (
  bindings,
  frameSet = frameSetForBindings(bindings)
) => ({
  ...bindings,
  frameSetId: frameSet.frameSetId,
  policy: {
    id: "selection-evidence-policy/v1",
    renderConfigVersion: bindings.renderConfigVersion,
    contributorSemantics: "alpha-times-transmittance/v1",
    evidenceScale: "contributor-mass/v1",
    betaPrior: { alpha: 1, beta: 1 },
    minimumEffectiveObservation: 0.1,
    selectedPosteriorThreshold: 0.8,
    rejectedPosteriorThreshold: 0.2,
  },
  records: [
    {
      stableId: 3,
      positiveEvidence: 3,
      negativeEvidence: 0,
      effectiveObservation: 3,
      posterior: 0.8,
      uncertaintyReason: null,
      classification: "selected",
    },
    {
      stableId: 7,
      positiveEvidence: 0,
      negativeEvidence: 0,
      effectiveObservation: 0,
      posterior: 0.5,
      uncertaintyReason: "unobserved",
      classification: "uncertain",
    },
    {
      stableId: 9,
      positiveEvidence: 0,
      negativeEvidence: 3,
      effectiveObservation: 3,
      posterior: 0.2,
      uncertaintyReason: null,
      classification: "rejected",
    },
  ],
});

const anchorCameraBinding = {
  revision: 0,
  cameraToWorld: [
    1, 0, 0, 0,
    0, -1, 0, 0,
    0, 0, -1, 0,
    0, 0, 0, 1,
  ],
  projection: {
    model: "pinhole",
    fx: 100,
    fy: 100,
    cx: 32,
    cy: 24,
    width: 64,
    height: 48,
    near: 0.1,
    far: 100,
  },
  conventionVersion: "opencv-camera-to-world/v1",
};

const anchorRequest = {
  requestBinding: {
    targetContextId: "ai-target-context-1",
    contextRevision: 0,
    dependencyToken: {
      splatId: "scene-1",
      renderStateToken: "render-v1",
      geometryToken: "geometry-v1",
      gaussianIdentityToken: "gaussians-v1",
      worldTransformToken: "transform-v1",
    },
  },
  target: { splatId: "scene-1" },
  snapshot,
  cameraBinding: anchorCameraBinding,
};

const pngCrc32 = bytes => {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
};

const pngChunk = (type, data) => {
  const typeBytes = Buffer.from(type, "ascii");
  const payload = Buffer.concat([typeBytes, data]);
  const length = Buffer.alloc(4);
  const checksum = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  checksum.writeUInt32BE(pngCrc32(payload));
  return Buffer.concat([length, payload, checksum]);
};

const anchorPngBytes = (width, height, imageData = null) => {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const scanlines = Buffer.alloc((width * 3 + 1) * height);
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", header),
    pngChunk("IDAT", imageData ?? deflateSync(scanlines)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
};

const anchorPng = (width, height) => {
  const bytes = anchorPngBytes(width, height);
  return {
    pngBase64: bytes.toString("base64"),
    digest: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
  };
};

const anchorResponse = request => ({
  status: "complete",
  requestBinding: request.requestBinding,
  targetSplatId: request.target.splatId,
  sceneId: request.snapshot.sceneId,
  sceneVersion: request.snapshot.sceneVersion,
  renderConfigVersion: request.snapshot.renderConfiguration.version,
  viewId: "anchor-view",
  cameraBinding: request.cameraBinding,
  rgb: {
    ...anchorPng(
      request.cameraBinding.projection.width,
      request.cameraBinding.projection.height
    ),
    width: request.cameraBinding.projection.width,
    height: request.cameraBinding.projection.height,
  },
  contributorDigest: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  rendererId: "gsplat",
});

test("registers the editor-owned Scene Snapshot then renders a bound authoritative Anchor through the Companion", async () => {
  const calls = [];
  const replies = [
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    anchorResponse(anchorRequest),
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

  const response = await adapter.renderAnchor(anchorRequest);

  assert.deepEqual(response, anchorResponse(anchorRequest));
  assert.equal(calls.length, 2);
  assert.match(calls[0].url, /\/scene-snapshots\/scene-1\/snapshot-v1$/);
  assert.equal(calls[0].init.method, "PUT");
  assert.match(calls[1].url, /\/ai-select\/anchor-renders$/);
  assert.equal(calls[1].init.method, "POST");
  assert.deepEqual(calls[1].body.requestBinding, anchorRequest.requestBinding);
  assert.deepEqual(calls[1].body.cameraBinding, anchorRequest.cameraBinding);
});

test("rejects an Anchor target that does not bind the editor-owned Scene Snapshot", async () => {
  const calls = [];
  const mismatchedRequest = {
    ...anchorRequest,
    target: { splatId: "different-splat" },
    requestBinding: {
      ...anchorRequest.requestBinding,
      dependencyToken: {
        ...anchorRequest.requestBinding.dependencyToken,
        splatId: "different-splat",
      },
    },
  };
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () => {
      calls.push("fetch");
      throw new Error("request should not be sent");
    },
  });

  await assert.rejects(
    adapter.renderAnchor(mismatchedRequest),
    /complete bound Anchor render request/i
  );
  assert.deepEqual(calls, []);
});

test("re-registers the Scene Snapshot exactly once when an Anchor render reports a cache miss", async () => {
  const calls = [];
  const replies = [
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    {
      status: "sceneCacheMiss",
      requestBinding: anchorRequest.requestBinding,
      targetSplatId: anchorRequest.target.splatId,
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
      renderConfigVersion: snapshot.renderConfiguration.version,
      viewId: "anchor-view",
      cameraBinding: anchorCameraBinding,
    },
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    anchorResponse(anchorRequest),
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

  const response = await adapter.renderAnchor(anchorRequest);

  assert.deepEqual(response, anchorResponse(anchorRequest));
  assert.equal(calls.length, 4);
  assert.equal(calls.filter(call => call.init.method === "PUT").length, 2);
  assert.equal(calls.filter(call => call.init.method === "POST").length, 2);
});

test("rejects an Anchor PNG whose declared digest does not bind its bytes", async () => {
  const response = anchorResponse(anchorRequest);
  response.rgb.digest = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const replies = [
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    response,
  ];
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () => new Response(JSON.stringify(replies.shift()), { status: 200 }),
  });

  await assert.rejects(
    adapter.renderAnchor(anchorRequest),
    /PNG digest does not match/i
  );
});

test("rejects malformed or dimension-mismatched Anchor PNG bytes even when their digest is valid", async (t) => {
  for (const [name, rgb, message] of [
    [
      "malformed",
      {
        pngBase64: Buffer.from("not a PNG").toString("base64"),
        digest: `sha256:${createHash("sha256").update("not a PNG").digest("hex")}`,
        width: 64,
        height: 48,
      },
      /invalid Anchor PNG/i,
    ],
    [
      "wrong actual dimensions",
      {
        ...anchorPng(1, 1),
        width: 64,
        height: 48,
      },
      /PNG dimensions do not match/i,
    ],
    [
      "truncated chunk stream",
      (() => {
        const bytes = anchorPngBytes(64, 48).subarray(0, -12);
        return {
          pngBase64: bytes.toString("base64"),
          digest: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
          width: 64,
          height: 48,
        };
      })(),
      /invalid Anchor PNG/i,
    ],
    [
      "corrupted chunk checksum",
      (() => {
        const bytes = anchorPngBytes(64, 48);
        bytes[bytes.length - 1] ^= 0x01;
        return {
          pngBase64: bytes.toString("base64"),
          digest: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
          width: 64,
          height: 48,
        };
      })(),
      /invalid Anchor PNG/i,
    ],
    [
      "undecodable IDAT stream",
      (() => {
        const bytes = anchorPngBytes(64, 48, Buffer.from([0x78, 0x9c, 0x00]));
        return {
          pngBase64: bytes.toString("base64"),
          digest: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
          width: 64,
          height: 48,
        };
      })(),
      /invalid Anchor PNG/i,
    ],
  ]) {
    await t.test(name, async () => {
      const response = anchorResponse(anchorRequest);
      response.rgb = rgb;
      const replies = [
        {
          status: "registered",
          sceneId: snapshot.sceneId,
          sceneVersion: snapshot.sceneVersion,
        },
        response,
      ];
      const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
          endpoint: "https://companion.example:8787",
          modelManifestDigest: "sha256:model-v1",
        }),
        fetch: async () => new Response(JSON.stringify(replies.shift()), { status: 200 }),
      });

      await assert.rejects(adapter.renderAnchor(anchorRequest), message);
    });
  }
});

test("registers one immutable Scene Snapshot, resends it after a cache miss, and retries the bound preview", async () => {
  const calls = [];
  const replies = [
    {
      status: "registered",
      frameSetVersion: start.requestContext.frameSetVersion,
    },
    { status: "accepted", sessionId: "session-1" },
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    {
      status: "sceneCacheMiss",
      ...previewBindings("request-1"),
    },
    {
      status: "registered",
      sceneId: snapshot.sceneId,
      sceneVersion: snapshot.sceneVersion,
    },
    {
      status: "complete",
      ...previewBindings("request-1"),
      selectedIds: [3],
      uncertainIds: [7],
      rejectedIds: [9],
      frameSet: frameSetForBindings(previewBindings("request-1")),
      maskSet: maskSet(previewBindings("request-1")),
      evidenceSnapshot: evidenceSnapshot(previewBindings("request-1")),
      coverageReport: coverageReport(previewBindings("request-1")),
    },
    {
      status: "complete",
      ...previewBindings("request-2"),
      selectedIds: [3],
      uncertainIds: [7],
      rejectedIds: [9],
      frameSet: frameSetForBindings(previewBindings("request-2")),
      maskSet: maskSet(previewBindings("request-2")),
      evidenceSnapshot: evidenceSnapshot(previewBindings("request-2")),
      coverageReport: coverageReport(previewBindings("request-2")),
    },
  ];
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      const body = init.body ? JSON.parse(init.body) : null;
      calls.push({ url, init, body });
      const reply = replies.shift();
      if (reply.status === "accepted") {
        reply.openRequestId = body.openRequestId;
      }
      return new Response(JSON.stringify(reply), { status: 200 });
    },
  });

  const sessionId = await adapter.openSession(start);
  const first = await adapter.updatePreview(previewRequest(sessionId));
  const second = await adapter.updatePreview(
    previewRequest(sessionId, "request-2")
  );

  assert.equal(sessionId, "session-1");
  assert.deepEqual(first.selectedIds, [3]);
  assert.equal(first.maskSet.threshold, 0.5);
  assert.deepEqual(second.uncertainIds, [7]);
  assert.deepEqual(
    calls.map((call) => `${call.init.method} ${call.url}`),
    [
      "PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
      "POST https://companion.example:8787/object-selection-sessions",
      "PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
      "PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
      "POST https://companion.example:8787/object-selection-sessions/session-1/previews",
    ]
  );
  assert.deepEqual(calls[0].body, start.requestContext.frameSet);
  assert.deepEqual(calls[2].body, snapshot);
  assert.equal(calls[3].body.snapshot, undefined);
  assert.equal(calls[3].body.modelManifestDigest, "sha256:model-v1");
  for (const call of calls) {
    assert.equal(call.init.mode, "cors");
    assert.equal(call.init.credentials, "omit");
    assert.equal(call.init.cache, "no-store");
  }
});

test("accepts a complete preview bound to the Companion's generated Frame Set", async () => {
  const request = previewRequest();
  const bindings = {
    ...previewBindings(request.requestId),
    frameSetVersion: "generated-frames-1:sha256:frame-set-v1",
  };
  const frameSet = {
    frameSetId: "generated-frames-1",
    frameSetVersion: bindings.frameSetVersion,
    orderedViews: [
      ...start.requestContext.frameSet.orderedViews,
      {
        viewId: "generated-ring-01",
        frameDigest: "sha256:generated-ring-01-v1",
        width: 64,
        height: 48,
      },
    ],
  };
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "complete",
          ...bindings,
          selectedIds: [3],
          uncertainIds: [7],
          rejectedIds: [9],
          frameSet,
          maskSet: maskSet(bindings, frameSet),
          evidenceSnapshot: evidenceSnapshot(bindings, frameSet),
          coverageReport: coverageReport(bindings, frameSet),
        }),
        { status: 200 }
      ),
  });

  const response = await adapter.updatePreview(request);

  assert.equal(response.frameSetVersion, frameSet.frameSetVersion);
  assert.deepEqual(
    response.frameSet.orderedViews.map((view) => view.viewId),
    ["anchor-view", "generated-ring-01"]
  );
  assert.equal(response.maskSet.frameSetVersion, frameSet.frameSetVersion);
  assert.equal(response.evidenceSnapshot.frameSetId, frameSet.frameSetId);
  assert.equal(
    response.coverageReport.frameSetVersion,
    frameSet.frameSetVersion
  );
});

test("re-registers the Scene Snapshot after closing the Companion session lease", async () => {
  const calls = [];
  const replies = [
    {
      status: 200,
      body: {
        status: "registered",
        frameSetVersion: start.requestContext.frameSetVersion,
      },
    },
    { status: 200, body: { status: "accepted", sessionId: "session-1" } },
    {
      status: 200,
      body: {
        status: "registered",
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
      },
    },
    { status: 204 },
    {
      status: 200,
      body: {
        status: "registered",
        frameSetVersion: start.requestContext.frameSetVersion,
      },
    },
    { status: 200, body: { status: "accepted", sessionId: "session-2" } },
    {
      status: 200,
      body: {
        status: "registered",
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
      },
    },
  ];
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      const body = init.body ? JSON.parse(init.body) : null;
      calls.push({ url, init, body });
      const reply = replies.shift();
      if (reply.body?.status === "accepted") {
        reply.body.openRequestId = body.openRequestId;
      }
      return new Response(
        reply.body === undefined ? null : JSON.stringify(reply.body),
        { status: reply.status }
      );
    },
  });

  const firstSession = await adapter.openSession(start);
  await adapter.closeSession(firstSession);
  await adapter.openSession(start);

  assert.equal(
    calls.filter((call) => call.url.includes("/scene-snapshots/")).length,
    2
  );
});

test("cleans an unrecovered opening after session admission fails", async () => {
  const calls = [];
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      calls.push({ url, init, body: init.body ? JSON.parse(init.body) : null });
      if (calls.length === 1 || calls.length === 3) {
        return new Response(
          JSON.stringify({
            status: "registered",
            frameSetVersion: start.requestContext.frameSetVersion,
          }),
          { status: 200 }
        );
      }
      if (calls.length === 2 || calls.length === 4) {
        throw new Error("connection reset after Frame Set registration");
      }
      return new Response(null, { status: 204 });
    },
  });

  await assert.rejects(
    adapter.openSession(start),
    /could not complete the Selection Service Companion request/
  );
  const openRequestId = calls[1].body.openRequestId;
  assert.deepEqual(
    calls.map((call) => `${call.init.method} ${call.url}`),
    [
      "PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
      "POST https://companion.example:8787/object-selection-sessions",
      "PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
      "POST https://companion.example:8787/object-selection-sessions",
      `DELETE https://companion.example:8787/object-selection-sessions/open-requests/${encodeURIComponent(openRequestId)}`,
      "DELETE https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
    ]
  );
  assert.equal(calls[1].body.openRequestId, openRequestId);
  assert.equal(calls[3].body.openRequestId, openRequestId);
});

test("recovers a session when its first admission response is lost", async () => {
  const calls = [];
  let admissionAttempts = 0;
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      const body = init.body ? JSON.parse(init.body) : null;
      calls.push({ url, init, body });
      if (url.includes("/frame-sets/")) {
        return new Response(
          JSON.stringify({
            status: "registered",
            frameSetVersion: start.requestContext.frameSetVersion,
          }),
          { status: 200 }
        );
      }
      if (url.endsWith("/object-selection-sessions")) {
        admissionAttempts += 1;
        if (admissionAttempts === 1) {
          throw new Error("response lost after successful Companion admission");
        }
        return new Response(
          JSON.stringify({
            status: "accepted",
            sessionId: "recovered-session",
            openRequestId: body.openRequestId,
          }),
          { status: 201 }
        );
      }
      if (url.includes("/scene-snapshots/")) {
        return new Response(
          JSON.stringify({
            status: "registered",
            sceneId: snapshot.sceneId,
            sceneVersion: snapshot.sceneVersion,
          }),
          { status: 200 }
        );
      }
      throw new Error(`unexpected request: ${url}`);
    },
  });

  const sessionId = await adapter.openSession(start);

  assert.equal(sessionId, "recovered-session");
  assert.deepEqual(
    calls.map((call) => `${call.init.method} ${call.url}`),
    [
      "PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
      "POST https://companion.example:8787/object-selection-sessions",
      "PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view",
      "POST https://companion.example:8787/object-selection-sessions",
      "PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1",
    ]
  );
  assert.equal(calls[1].body.openRequestId, calls[3].body.openRequestId);
});

test("uses a distinct admission ID for each logical New opening", async () => {
  const calls = [];
  let sessionNumber = 0;
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async (url, init) => {
      const body = init.body ? JSON.parse(init.body) : null;
      calls.push({ url, init, body });
      if (url.includes("/frame-sets/")) {
        return new Response(
          JSON.stringify({
            status: "registered",
            frameSetVersion: start.requestContext.frameSetVersion,
          }),
          { status: 200 }
        );
      }
      if (url.endsWith("/object-selection-sessions")) {
        sessionNumber += 1;
        return new Response(
          JSON.stringify({
            status: "accepted",
            sessionId: `session-${sessionNumber}`,
            openRequestId: body.openRequestId,
          }),
          { status: 201 }
        );
      }
      if (url.includes("/scene-snapshots/")) {
        return new Response(
          JSON.stringify({
            status: "registered",
            sceneId: snapshot.sceneId,
            sceneVersion: snapshot.sceneVersion,
          }),
          { status: 200 }
        );
      }
      if (init.method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      throw new Error(`unexpected request: ${url}`);
    },
  });
  const nextStart = {
    ...start,
    prompt: {
      ...start.prompt,
      promptId: "prompt-2",
      xPx: 11,
    },
  };

  const firstSession = await adapter.openSession(start);
  await adapter.closeSession(firstSession);
  await adapter.openSession(nextStart);

  const admissions = calls.filter(
    (call) =>
      call.init.method === "POST" &&
      call.url.endsWith("/object-selection-sessions")
  );
  assert.equal(admissions.length, 2);
  assert.match(admissions[0].body.openRequestId, /^open:/);
  assert.notEqual(
    admissions[0].body.openRequestId,
    admissions[1].body.openRequestId
  );
});

test("rejects a preview response that omits its complete Mask Set", async () => {
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "complete",
          ...previewBindings("request-1"),
          selectedIds: [3],
          uncertainIds: [7],
          rejectedIds: [9],
          frameSet: frameSetForBindings(previewBindings("request-1")),
          evidenceSnapshot: evidenceSnapshot(previewBindings("request-1")),
          coverageReport: coverageReport(previewBindings("request-1")),
        }),
        { status: 200 }
      ),
  });

  await assert.rejects(
    adapter.updatePreview(previewRequest()),
    /complete, version-bound Mask Set/
  );
});

test("rejects a preview response that omits its complete Evidence Snapshot", async () => {
  const bindings = previewBindings("request-1");
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "complete",
          ...bindings,
          selectedIds: [3],
          uncertainIds: [7],
          rejectedIds: [9],
          frameSet: frameSetForBindings(bindings),
          maskSet: maskSet(bindings),
          coverageReport: coverageReport(bindings),
        }),
        { status: 200 }
      ),
  });

  await assert.rejects(
    adapter.updatePreview(previewRequest()),
    /complete, version-bound Evidence Snapshot/
  );
});

test("rejects a complete Mask Set that omits its threshold", async () => {
  const bindings = previewBindings("request-1");
  const noThresholdMaskSet = maskSet(bindings);
  delete noThresholdMaskSet.threshold;
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "complete",
          ...bindings,
          selectedIds: [3],
          uncertainIds: [7],
          rejectedIds: [9],
          frameSet: frameSetForBindings(bindings),
          maskSet: noThresholdMaskSet,
          evidenceSnapshot: evidenceSnapshot(bindings),
          coverageReport: coverageReport(bindings),
        }),
        { status: 200 }
      ),
  });

  await assert.rejects(
    adapter.updatePreview(previewRequest()),
    /invalid Mask Set threshold/
  );
});

test("rejects a Mask Set with a malformed accepted binary mask", async () => {
  const bindings = previewBindings("request-1");
  const malformedMaskSet = maskSet(bindings);
  malformedMaskSet.tracks[0].frames[0].binaryMask = {
    encoding: "sparse-points-v1",
    width: 1,
    height: 1,
    foregroundPixels: [[0, 0]],
  };
  const adapter = new FetchSelectionServiceAdapter({
    getConfiguration: () => ({
      endpoint: "https://companion.example:8787",
      modelManifestDigest: "sha256:model-v1",
    }),
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "complete",
          ...bindings,
          selectedIds: [3],
          uncertainIds: [7],
          rejectedIds: [9],
          frameSet: frameSetForBindings(bindings),
          maskSet: malformedMaskSet,
          evidenceSnapshot: evidenceSnapshot(bindings),
          coverageReport: coverageReport(bindings),
        }),
        { status: 200 }
      ),
  });

  await assert.rejects(
    adapter.updatePreview(previewRequest()),
    /complete, version-bound Mask Set/
  );
});
