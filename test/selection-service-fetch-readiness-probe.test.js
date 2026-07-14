const assert = require("node:assert/strict");
const test = require("node:test");

const {
  FetchSelectionServiceReadinessProbe,
  SelectionServiceTransportError,
} = require("../.test-dist/src/selection-service-fetch-readiness-probe.js");

const request = {
  endpoint: "https://companion.example:8787",
  profile: "trustedLan",
  editorOrigin: "https://editor.example",
};

test("uses credential-free CORS Fetch requests for the Companion health and capability checks", async () => {
  const calls = [];
  const probe = new FetchSelectionServiceReadinessProbe({
    fetch: async (url, init) => {
      calls.push({ url, init });
      return new Response(
        JSON.stringify({ serviceBuild: "selection-service/0.1.0" }),
        { status: 200 }
      );
    },
    localNetworkPermissions: {
      query: async () => "granted",
    },
  });

  const health = await probe.checkHealth(request);
  const capabilities = await probe.getCapabilities(request);

  assert.deepEqual(health, { serviceBuild: "selection-service/0.1.0" });
  assert.deepEqual(capabilities, { serviceBuild: "selection-service/0.1.0" });
  assert.deepEqual(
    calls.map((call) => call.url),
    [
      "https://companion.example:8787/health",
      "https://companion.example:8787/capabilities",
    ]
  );
  for (const call of calls) {
    assert.equal(call.init.method, "GET");
    assert.equal(call.init.mode, "cors");
    assert.equal(call.init.credentials, "omit");
    assert.equal(call.init.headers.Accept, "application/json");
  }
});

test("does not bypass a denied Chromium Local Network Access permission", async () => {
  let fetchCalls = 0;
  const probe = new FetchSelectionServiceReadinessProbe({
    fetch: async () => {
      fetchCalls += 1;
      return new Response("{}", { status: 200 });
    },
    localNetworkPermissions: {
      query: async () => "denied",
    },
  });

  await assert.rejects(
    probe.checkHealth(request),
    (error) =>
      error instanceof SelectionServiceTransportError &&
      error.code === "localNetworkPermissionDenied"
  );
  assert.equal(fetchCalls, 0);
});

test("does not treat an insecure public editor origin as a local-network fallback", async () => {
  const probe = new FetchSelectionServiceReadinessProbe({
    fetch: async () => new Response("{}", { status: 200 }),
    localNetworkPermissions: {
      query: async () => "granted",
    },
    isSecureContext: () => false,
  });

  await assert.rejects(
    probe.checkHealth(request),
    (error) =>
      error instanceof SelectionServiceTransportError &&
      error.code === "insecureEditorContext"
  );
});

test("preserves a reachable Companion's structured HTTP diagnostic", async () => {
  const probe = new FetchSelectionServiceReadinessProbe({
    fetch: async () =>
      new Response(
        JSON.stringify({
          status: "unavailable",
          message:
            "The installed Companion release lock changed; run selection-service install again.",
        }),
        { status: 503 }
      ),
    localNetworkPermissions: {
      query: async () => "granted",
    },
  });

  await assert.rejects(
    probe.getCapabilities(request),
    (error) =>
      error instanceof SelectionServiceTransportError &&
      error.code === "http" &&
      error.status === 503 &&
      /release lock changed/i.test(error.serviceMessage)
  );
});
