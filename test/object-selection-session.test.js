const assert = require("node:assert/strict");
const test = require("node:test");

const {
  ObjectSelectionSession,
} = require("../.test-dist/src/object-selection-session.js");

const newSessionInput = () => ({
  target: {
    targetSplatId: "splat-1",
  },
  prompt: {
    promptId: "prompt-1",
    viewId: "anchor-view",
    xPx: 10,
    yPx: 20,
    polarity: "include",
  },
});

const additionalPrompt = {
  promptId: "prompt-2",
  viewId: "anchor-view",
  xPx: 30,
  yPx: 40,
  polarity: "exclude",
};

const removalPrompt = {
  promptId: "prompt-3",
  viewId: "anchor-view",
  xPx: 50,
  yPx: 60,
  polarity: "exclude",
};

const candidate = {
  selectedIds: [3, 7],
  uncertainIds: [9],
  rejectedIds: [1, 2],
};

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
    return candidate;
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

  assert.deepEqual(adapter.openRequests, [start]);
  assert.deepEqual(adapter.previewRequests, [
    {
      sessionId: "deterministic-session",
      requestId: "request-1",
      target: start.target,
      operation: "Remove",
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
      this.resolvePreview(candidate);
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
        return candidate;
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
  adapter.resolvePreview({
    selectedIds: [11],
    uncertainIds: [],
    rejectedIds: [],
  });
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
    /cannot run this command while cancellingUpdate/,
  );
  assert.equal(adapter.cancelledUpdates.length, 1);

  adapter.resolveCancellation();
  await firstCancel;
  adapter.resolvePreview(candidate);
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
