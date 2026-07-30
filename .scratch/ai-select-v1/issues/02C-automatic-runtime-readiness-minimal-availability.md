# 02C — Automatic Runtime Readiness + Minimal Availability UI

Status: blocked — waits for Ticket 04C

Blocked by: 02, 04C

Blocks: 21 closure

## Final Spec mapping

- Final Spec v1.3 §§3–6, 16, 24–26
- ADR 0015
- ADR 0016

## Purpose

Replace PoC endpoint/model controls and manual readiness with automatic background readiness and one restrained user-facing state:

```text
Connecting / Available / Unavailable
```

The Companion resolves one process-lifetime Active Model Manifest. For the current profile that manifest MUST identify the SAM 3 Image instance adapter produced by Ticket 04C, not the historical SAM 3.1 Multiplex static baseline.

## Browser ownership

- non-blocking startup;
- single-flight health/compatibility checks;
- foreground heartbeat and bounded retry;
- three-state Availability presentation;
- pending activation identity and stale-result rejection;
- same-instance connection recovery;
- transition logs.

## Companion ownership

- operator/deployment endpoint configuration;
- installed manifest validation;
- exact-one Active Model resolution;
- Companion Instance ID;
- current Runtime Profile capability response;
- initialized SAM 3 Image adapter readiness;
- startup/runtime/model diagnostics.

The browser never downloads, chooses, starts, stops or upgrades models.

## Current Runtime Profile requirements

Compatibility validation requires:

- current protocol and authoritative renderer;
- exact SAM 3 Image Model Manifest/checkpoint/runtime/adapter identity from 04C;
- Positive Point, Negative Point, Positive Instance Box, previous-logits refinement and single-point multimask capabilities;
- absence/incompatibility of current clients requiring Negative Box, Prompt Brush, Mask Constraints or Text;
- no requirement for Multiplex video predictor, tracker session, backend registry or sequence extension;
- origin/security compatibility.

Historical Multiplex-only manifests are Not Ready for the current v1.3 static profile.

## Availability lifecycle

- Editor startup never waits for AI readiness.
- First check starts after UI mount.
- Available heartbeat is lightweight and does not initialize or hash models repeatedly.
- First connection, recovery or Companion Instance change runs full compatibility validation.
- Busy and task-local inference failure do not change service Availability.
- Transport/runtime/profile incompatibility enters Unavailable.
- Same-instance connection-interrupted work may retry once with a new attempt only when all identities remain current.
- model failure, semantic unavailable, cancellation, stale input or OOM is never auto-retried as connection recovery.

## UI requirements

Ordinary UI exposes only:

```text
Connecting / Available / Unavailable
```

No endpoint, Model Manifest, CUDA, protocol matrix, Ping, Check Readiness, model selector or raw diagnostic is shown.

## Acceptance criteria

- [ ] Browser performs automatic single-flight readiness.
- [ ] Heartbeat and full compatibility validation remain separate.
- [ ] One Active Model Manifest crosses the protocol.
- [ ] Current profile admits only the 04C SAM 3 Image instance adapter.
- [ ] Historical Multiplex static manifest fails compatibility.
- [ ] Removed Prompt capabilities are not required or advertised as current.
- [ ] Busy/task-local failure does not change Availability.
- [ ] same-instance recovery is fail-closed and identity-bound.
- [ ] ordinary UI contains no technical/model controls.
- [ ] Native SuperSplat remains usable while unavailable.

## Validation

- fake-timer heartbeat/backoff tests;
- first-connect/recovery/Instance-change compatibility tests;
- exact-one/zero/multiple manifest resolution tests;
- SAM 3 Image current-profile acceptance;
- Multiplex manifest rejection;
- removed-Prompt capability mismatch tests;
- Busy/task-failure non-interference tests;
- UI accessibility and no-technical-detail assertions;
- repository test/lint/locales/build.

## Non-goals

- No browser-owned Companion/model lifecycle.
- No model selection UI.
- No per-task progress UI in Availability.
- No tracker or backend-route readiness matrix.
