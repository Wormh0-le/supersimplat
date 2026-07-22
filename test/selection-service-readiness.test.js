const assert = require("node:assert/strict");
const test = require("node:test");

const {
  ReadinessGatedSelectionServiceAdapter,
  SelectionServiceReadiness,
  SelectionServiceTransportError,
} = require("../.test-dist/src/selection-service-readiness.js");

const editorOrigin = "https://editor.example";
const selectedModelDigest = "sha256:model-v1";

const configuration = (overrides = {}) => ({
  endpoint: "http://127.0.0.1:8787",
  profile: "loopback",
  editorOrigin,
  modelManifestDigest: selectedModelDigest,
  ...overrides,
});

const capabilities = (overrides = {}) => ({
  protocolVersion: "1",
  serviceBuild: "selection-service/0.1.0",
  renderer: {
    id: "gsplat",
    status: "ready",
    cudaVersion: "12.8",
  },
  supportedPromptKinds: ["point"],
  supportedOperations: [
    "aiSelectAnchorRender",
    "binarySceneSnapshotRegistrationV1",
  ],
  modelManifests: [
    {
      digest: selectedModelDigest,
      adapterId: "sam3.1",
      modelName: "SAM 3.1",
      weightsBundled: false,
    },
  ],
  capacity: {
    maximumActiveSessions: 1,
    activeSessions: 0,
  },
  allowedEditorOrigins: [editorOrigin],
  ...overrides,
});

class DeterministicReadinessProbe {
  constructor(options = {}) {
    this.healthError = options.healthError;
    this.capabilitiesError = options.capabilitiesError;
    this.capabilitiesResult = options.capabilitiesResult ?? capabilities();
    this.healthRequests = [];
    this.capabilitiesRequests = [];
  }

  async checkHealth(request) {
    this.healthRequests.push(request);
    if (this.healthError) {
      throw this.healthError;
    }
    return { serviceBuild: "selection-service/0.1.0" };
  }

  async getCapabilities(request) {
    this.capabilitiesRequests.push(request);
    if (this.capabilitiesError) {
      throw this.capabilitiesError;
    }
    return this.capabilitiesResult;
  }
}

class RecordingSelectionServiceAdapter {
  constructor() {
    this.openRequests = [];
  }

  async openSession(start) {
    this.openRequests.push(start);
    return "selection-session";
  }

  async updatePreview() {
    throw new Error("not used by readiness tests");
  }

  async cancelUpdate() {
    throw new Error("not used by readiness tests");
  }

  async closeSession() {
    throw new Error("not used by readiness tests");
  }
}

test("keeps a reachable Companion unavailable until the operator selects an installed Model Manifest", async () => {
  const probe = new DeterministicReadinessProbe();
  const readiness = new SelectionServiceReadiness({
    probe,
    configuration: configuration({ modelManifestDigest: null }),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "reachable");
  assert.equal(readiness.state.diagnostic.code, "modelNotSelected");
  assert.match(readiness.state.diagnostic.action, /select/i);
  assert.equal(probe.healthRequests.length, 1);
  assert.equal(probe.capabilitiesRequests.length, 1);
});

test("admits a Selection Service session only after compatible readiness succeeds", async () => {
  const probe = new DeterministicReadinessProbe();
  const readiness = new SelectionServiceReadiness({
    probe,
    configuration: configuration(),
  });
  const adapter = new RecordingSelectionServiceAdapter();
  const gatedAdapter = new ReadinessGatedSelectionServiceAdapter({
    readiness,
    adapter,
  });

  await readiness.refresh();
  const sessionId = await gatedAdapter.openSession({ target: {}, prompt: {} });

  assert.equal(readiness.state.status, "ready");
  assert.equal(sessionId, "selection-session");
  assert.equal(adapter.openRequests.length, 1);
});

test("keeps the production adapter gateway closed until its real transport is attached", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe(),
    configuration: configuration(),
  });
  const gateway = new ReadinessGatedSelectionServiceAdapter({ readiness });

  await readiness.refresh();

  await assert.rejects(
    gateway.openSession({ target: {}, prompt: {} }),
    /transport is not configured/i
  );
});

test("admits the attached transport only through the ready production gateway", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe(),
    configuration: configuration(),
  });
  const adapter = new RecordingSelectionServiceAdapter();
  const gateway = new ReadinessGatedSelectionServiceAdapter({ readiness });
  gateway.setAdapter(adapter);

  await readiness.refresh();
  await gateway.openSession({ target: {}, prompt: {} });

  assert.equal(adapter.openRequests.length, 1);
});

test("gates the AI Select Anchor renderer through the same readiness decision", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe(),
    configuration: configuration(),
  });
  const adapter = new RecordingSelectionServiceAdapter();
  const anchorRequests = [];
  adapter.renderAnchor = async (request) => {
    anchorRequests.push(request);
    return { status: "complete" };
  };
  const gateway = new ReadinessGatedSelectionServiceAdapter({ readiness, adapter });

  await assert.rejects(gateway.renderAnchor({}), /cannot start/i);
  await readiness.refresh();
  const result = await gateway.renderAnchor({ requestBinding: "bound" });

  assert.deepEqual(result, { status: "complete" });
  assert.deepEqual(anchorRequests, [{ requestBinding: "bound" }]);
});

test("does not admit an Anchor renderer when a compatible protocol does not advertise Anchor rendering", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe({
      capabilitiesResult: capabilities({ supportedOperations: [] }),
    }),
    configuration: configuration(),
  });
  const adapter = new RecordingSelectionServiceAdapter();
  adapter.renderAnchor = async () => ({ status: "complete" });
  const gateway = new ReadinessGatedSelectionServiceAdapter({ readiness, adapter });

  await readiness.refresh();

  assert.equal(readiness.state.status, "reachable");
  assert.equal(readiness.state.diagnostic.code, "aiSelectAnchorUnsupported");
  await assert.rejects(gateway.renderAnchor({}), /cannot start/i);
});

test("does not admit AI Select when the Companion lacks Binary SceneSnapshot Registration v1", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe({
      capabilitiesResult: capabilities({
        supportedOperations: ["aiSelectAnchorRender"],
      }),
    }),
    configuration: configuration(),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "reachable");
  assert.equal(
    readiness.state.diagnostic.code,
    "binarySceneSnapshotRegistrationUnsupported"
  );
});

test("reports protocol, renderer, model, origin, and one-session capacity failures without opening a session", async (t) => {
  const cases = [
    ["protocol", capabilities({ protocolVersion: "2" }), "protocolMismatch"],
    [
      "renderer",
      capabilities({ renderer: { id: "gsplat", status: "unavailable" } }),
      "rendererUnavailable",
    ],
    ["model", capabilities({ modelManifests: [] }), "modelUnavailable"],
    [
      "origin",
      capabilities({ allowedEditorOrigins: [] }),
      "editorOriginDenied",
    ],
    [
      "capacity",
      capabilities({
        capacity: { maximumActiveSessions: 1, activeSessions: 1 },
      }),
      "capacityBusy",
    ],
  ];

  for (const [name, capabilitiesResult, code] of cases) {
    await t.test(name, async () => {
      const readiness = new SelectionServiceReadiness({
        probe: new DeterministicReadinessProbe({ capabilitiesResult }),
        configuration: configuration(),
      });
      const adapter = new RecordingSelectionServiceAdapter();
      const gatedAdapter = new ReadinessGatedSelectionServiceAdapter({
        readiness,
        adapter,
      });

      await readiness.refresh();

      assert.equal(readiness.state.status, "reachable");
      assert.equal(readiness.state.diagnostic.code, code);
      await assert.rejects(
        gatedAdapter.openSession({ target: {}, prompt: {} }),
        /cannot start/i
      );
      assert.equal(adapter.openRequests.length, 0);
    });
  }
});

test("rejects an endpoint outside its selected transport profile before contacting the Companion", async () => {
  const probe = new DeterministicReadinessProbe();
  const readiness = new SelectionServiceReadiness({
    probe,
    configuration: configuration({ endpoint: "http://192.168.1.20:8787" }),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "unavailable");
  assert.equal(readiness.state.diagnostic.code, "loopbackEndpointRequired");
  assert.equal(probe.healthRequests.length, 0);

  readiness.setConfiguration(
    configuration({
      endpoint: "http://selection.lan:8787",
      profile: "trustedLan",
    })
  );
  await readiness.refresh();

  assert.equal(readiness.state.status, "unavailable");
  assert.equal(readiness.state.diagnostic.code, "trustedLanHttpsRequired");
  assert.equal(probe.healthRequests.length, 0);
});

test("surfaces a Chromium local-network permission denial as a browser transport failure", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe({
      healthError: new SelectionServiceTransportError(
        "localNetworkPermissionDenied"
      ),
    }),
    configuration: configuration(),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "unavailable");
  assert.equal(readiness.state.diagnostic.code, "localNetworkPermissionDenied");
  assert.match(readiness.state.diagnostic.action, /local network/i);
});

test("keeps a responding Companion reachable when its capability check returns an actionable HTTP error", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe({
      capabilitiesError: new SelectionServiceTransportError(
        "http",
        "The Selection Service Companion returned HTTP 503.",
        {
          status: 503,
          serviceMessage:
            "The installed Companion release lock changed; run selection-service install again.",
        }
      ),
    }),
    configuration: configuration(),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "reachable");
  assert.equal(readiness.state.diagnostic.code, "companionRejectedRequest");
  assert.match(readiness.state.diagnostic.action, /release lock changed/i);
});

test("keeps a responding Companion reachable when health returns an actionable HTTP error", async () => {
  const readiness = new SelectionServiceReadiness({
    probe: new DeterministicReadinessProbe({
      healthError: new SelectionServiceTransportError(
        "http",
        "The Selection Service Companion returned HTTP 503.",
        {
          status: 503,
          serviceMessage:
            "The installed Companion release lock changed; run selection-service install again.",
        }
      ),
    }),
    configuration: configuration(),
  });

  await readiness.refresh();

  assert.equal(readiness.state.status, "reachable");
  assert.equal(readiness.state.diagnostic.code, "companionRejectedRequest");
  assert.match(readiness.state.diagnostic.action, /release lock changed/i);
});
