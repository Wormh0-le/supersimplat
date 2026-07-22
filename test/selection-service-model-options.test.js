const assert = require("node:assert/strict");
const test = require("node:test");

const {
  selectionServiceModelOptions,
} = require("../.test-dist/src/ui/selection-service-model-options.js");

test("keeps registered models selectable when the empty SelectInput value is present", () => {
  const options = selectionServiceModelOptions({
    modelManifests: [
      {
        digest: "sha256:first",
        modelName: "First model",
      },
      {
        digest: "sha256:second",
        modelName: "Second model",
      },
    ],
  });

  assert.deepEqual(options, [
    { v: "sha256:first", t: "First model (sha256:first)" },
    { v: "sha256:second", t: "Second model (sha256:second)" },
    { v: "", t: "Select an installed model" },
  ]);
});
