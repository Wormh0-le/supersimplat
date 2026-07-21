const assert = require("node:assert/strict");
const test = require("node:test");

const {
  CurrentTargetContextKernel,
} = require("../.test-dist/src/ai-select/current-target-context.js");

const target = (splatId = "splat-1") => ({ splatId });

const dependency = (overrides = {}) => ({
  splatId: "splat-1",
  renderStateToken: "render-v1",
  geometryToken: "geometry-v1",
  gaussianIdentityToken: "gaussians-v1",
  worldTransformToken: "transform-v1",
  ...overrides,
});

const input = (overrides = {}) => ({
  target: target(),
  dependencyToken: dependency(),
  ...overrides,
});

test("creates one active target context with an immutable structural dependency binding", () => {
  const kernel = new CurrentTargetContextKernel();
  const start = input();

  const context = kernel.start(start);

  assert.equal(context.lifecycle, "active");
  assert.equal(context.revision, 0);
  assert.deepEqual(context.target, target());
  assert.deepEqual(context.dependencyToken, dependency());
  assert.notEqual(context.target, start.target);
  assert.notEqual(context.dependencyToken, start.dependencyToken);
  assert.throws(() => kernel.start(input()), /already active/i);
});

test("rejects a result after a context revision even if cancellation did not stop it", () => {
  const kernel = new CurrentTargetContextKernel();
  kernel.start(input());
  const oldBinding = kernel.createRequestBinding();

  const revised = kernel.revise();
  const currentBinding = kernel.createRequestBinding();

  assert.equal(revised.revision, oldBinding.contextRevision + 1);
  assert.equal(kernel.acceptsResult(oldBinding, dependency()), false);
  assert.equal(kernel.acceptsResult(currentBinding, dependency()), true);
});

test("rejects a result for another target context", () => {
  const kernel = new CurrentTargetContextKernel();
  kernel.start(input());
  const binding = kernel.createRequestBinding();

  assert.equal(
    kernel.acceptsResult(
      { ...binding, targetContextId: "another-target-context" },
      dependency()
    ),
    false
  );
});

test("suspends on a dependency mismatch and resumes only on exact semantic restoration", () => {
  const kernel = new CurrentTargetContextKernel();
  kernel.start(input());
  const binding = kernel.createRequestBinding();

  const suspended = kernel.synchronizeDependency(
    dependency({ geometryToken: "geometry-v2" })
  );

  assert.equal(suspended.lifecycle, "suspended");
  assert.equal(
    kernel.acceptsResult(binding, dependency({ geometryToken: "geometry-v2" })),
    false
  );

  const resumed = kernel.synchronizeDependency(dependency());
  const resumedBinding = kernel.createRequestBinding();

  assert.equal(resumed.lifecycle, "active");
  assert.equal(resumed.revision, binding.contextRevision + 2);
  assert.equal(kernel.acceptsResult(binding, dependency()), false);
  assert.equal(kernel.acceptsResult(resumedBinding, dependency()), true);
});

test("restart disposes the previous context and does not allow a disposed context to resume", () => {
  const kernel = new CurrentTargetContextKernel();
  const original = kernel.start(input());
  const restarted = kernel.restart(
    input({
      target: target("splat-2"),
      dependencyToken: dependency({ splatId: "splat-2" }),
    })
  );

  assert.notEqual(restarted.targetContextId, original.targetContextId);
  assert.equal(kernel.current.targetContextId, restarted.targetContextId);

  const disposed = kernel.dispose();

  assert.equal(disposed.lifecycle, "disposed");
  assert.equal(kernel.current, null);
  assert.equal(
    kernel.synchronizeDependency(dependency({ splatId: "splat-2" })),
    null
  );
});

test("fails closed for empty or malformed dependency identities", () => {
  const kernel = new CurrentTargetContextKernel();

  assert.throws(
    () =>
      kernel.start(
        input({ dependencyToken: dependency({ geometryToken: "" }) })
      ),
    /dependency token/i
  );

  kernel.start(input());
  const binding = kernel.createRequestBinding();

  assert.equal(
    kernel.acceptsResult(binding, dependency({ worldTransformToken: " " })),
    false
  );
  assert.equal(kernel.current.lifecycle, "suspended");
});
