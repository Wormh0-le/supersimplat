const assert = require("node:assert/strict");
const test = require("node:test");

const {
  ObjectSelectionSession,
} = require("../.test-dist/src/object-selection-session.js");

class DeterministicSelectionServiceAdapter {
  async openSession() {
    return "deterministic-session";
  }

  async updatePreview() {
    return {
      selectedIds: [3, 7],
      uncertainIds: [9],
      rejectedIds: [1, 2],
    };
  }

  async closeSession() {
    // The deterministic adapter has no external resources to release.
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
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: new DeterministicSelectionServiceAdapter(),
    editor,
  });

  await session.startNew();
  await session.updatePreview();

  assert.deepEqual(session.state.candidate, {
    selectedIds: [3, 7],
    uncertainIds: [9],
    rejectedIds: [1, 2],
  });
  assert.deepEqual(editor.selection, [1, 2]);
  assert.deepEqual(editor.history, []);

  await session.confirm();

  assert.deepEqual(editor.selection, [3, 7]);
  assert.deepEqual(editor.history, [[3, 7]]);
});

test("Cancel restores the entry selection without adding history", async () => {
  const editor = new RecordingSelectionEditor();
  const session = new ObjectSelectionSession({
    selectionService: new DeterministicSelectionServiceAdapter(),
    editor,
  });

  await session.startNew();
  await session.updatePreview();
  editor.selection = [99];
  await session.cancel();

  assert.deepEqual(session.state, {
    status: "closed",
    candidate: null,
  });
  assert.deepEqual(editor.selection, [1, 2]);
  assert.deepEqual(editor.history, []);
});
