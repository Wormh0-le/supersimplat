# 02C — Automatic Runtime Readiness + Minimal Availability UI

Status: ready for implementation — 2026-07-30

Blocked by: 02, 04B

Blocks: 21 closure

## Final Spec mapping

- Final Spec v1.2 §§1–5, 27–29
- ADR 0015 — Automate AI Select readiness and keep model resolution operator-owned
- Ticket 02 — AI Select shell + authoritative gsplat Anchor

## Purpose

Replace the PoC-facing endpoint, Model Manifest selector, and manual
`Check readiness` workflow with automatic runtime readiness and one restrained
user-facing service status:

```text
Connecting / Available / Unavailable
```

The browser still validates exact protocol/runtime/model identities and binds
the Active Model Manifest to every dependent request. Hiding technical controls
must not weaken fail-closed admission.

## Ownership

### Browser Editor owns

- non-blocking startup of automatic readiness;
- one single-flight connection/compatibility check;
- lightweight foreground heartbeat and bounded retry scheduling;
- `AI Select Availability` projection and presentation;
- pending AI Select activation identity;
- stale-result and stale-activation rejection;
- same-identity recovery of connection-interrupted work;
- browser-side connection transition logs.

### Selection Service Companion owns

- operator/deployment endpoint and transport configuration;
- installed Model Manifest validation;
- resolution and initialization of one process-lifetime Active Model Manifest;
- one opaque Companion Instance ID per process;
- the versioned AI Select Runtime Profile capability response;
- Companion startup/runtime/model/readiness logs.

The browser does not install, select, activate, download, start, stop, or
upgrade models or the Companion.

# 1. Minimal availability presentation

Expose one domain state:

```ts
type AISelectAvailability = 'connecting' | 'available' | 'unavailable';
```

Required presentation:

- the AI Select entry displays a small status indicator;
- the active AI Select Dock title displays only `Connecting`, `Available`, or
  `Unavailable` as restrained secondary text;
- Available remains visible but visually subdued;
- color is not the only carrier of meaning;
- status changes use polite accessibility announcement;
- no success banner, toast, endpoint, manifest name/digest, CUDA version,
  protocol matrix, raw diagnostic, Ping, Check Readiness, or dedicated Retry
  control appears in ordinary UI;
- no new recovery action is added beside the service status;
- existing `Restart Current Target` remains in its existing overflow location.

# 2. Automatic connection lifecycle

- Editor/scene/native-tool startup never waits for AI readiness.
- The first readiness check starts after the UI is mounted.
- A click on the unavailable AI Select entry expresses activation intent and
  triggers or joins the current single-flight check; it is not a Ping button.
- A successful check enters AI Select only if the pending target/dependency
  identity still matches. Otherwise the pending activation is discarded
  silently while Availability becomes Available.
- Repeated activation retains only the latest valid intent.
- Page visibility/focus recovery triggers an immediate check.
- Background pages pause heartbeat and resume through Connecting.

## Timing and debounce

```text
Available foreground heartbeat: every 15 seconds
Unavailable retry:             1s → 2s → 5s → 10s, then every 10s
```

- The first idle heartbeat failure enters Connecting and retries immediately.
- Two consecutive idle heartbeat failures enter Unavailable.
- A real AI transport failure enters Unavailable immediately.
- Availability returns to Available only after required compatibility
  validation succeeds.

# 3. Lightweight heartbeat versus compatibility validation

Heartbeat:

- uses a lightweight health route only;
- returns service health/build plus Companion Instance ID;
- never hashes checkpoints, initializes models, enumerates manifests, probes
  renderer quality, or consumes the single AI execution slot;
- does not treat capacity Busy as service unavailability.

Compatibility Validation:

- runs on first connection, recovery, and Companion Instance ID change;
- validates the exact editor-required AI Select Runtime Profile;
- requires protocol, authoritative renderer, Active Model Manifest, initialized
  model/runtime, required operations/backends/policies, and origin/security
  compatibility;
- is cached for the current Companion Instance ID;
- must not be repeated by every steady-state heartbeat.

# 4. Operator-owned Active Model Manifest

- Exactly one compatible installed manifest becomes Active automatically.
- When multiple compatible manifests exist, the operator must select one
  through Companion startup/deployment configuration.
- No compatible manifest, ambiguous model resolution, failed model
  initialization, or incompatible runtime leaves the Companion Not Ready.
- Active Model identity is immutable for one Companion process lifetime.
- The browser consumes and binds one `activeModelManifest`; it never chooses,
  sorts, remembers, or displays installed models.
- The target protocol migrates from browser-consumed `modelManifests[]` to one
  authoritative `activeModelManifest`. Migration is versioned and fail-closed.
- Changing Active Model requires a new Companion Instance ID and full browser
  revalidation.

# 5. Failure, interruption, and recovery

Availability changes only for service-level conditions:

- transport loss/timeout/refusal;
- protocol/runtime/renderer/Active Model incompatibility;
- explicit service-unavailable responses;
- Companion Instance replacement.

The following remain task-local and do not change Availability:

- Busy/capacity occupancy;
- no proposal or model-level semantic rejection;
- one View/Mask/Evidence/Lift failure;
- cancellation, stale binding, invalid request, or ordinary task OOM.

When service is unavailable:

- Native SuperSplat remains usable;
- current Anchor/Views/Masks/Candidate remain inspectable;
- local Paint/Erase and Prompt/Mask history remain usable;
- current non-stale Candidate may still use Native Set/Add/Remove/Intersect;
- remote render, SAM, planning, Evidence, and Lift work pauses;
- at most the latest unsubmitted user intent is retained; no unbounded request
  queue is created.

On same-identity recovery:

- the Current Target Context remains intact;
- an operation interrupted specifically by connection loss may execute once
  with a new attempt ID if all target/input identities still match;
- user cancellation, model failure, stale input, OOM, or semantic unavailable
  is never auto-retried.

On changed runtime/model identity:

- Availability remains Unavailable for the existing context;
- the context stays inspectable and no new recovery control is added;
- technical restart guidance is logged only;
- existing lifecycle actions remain in their normal locations.

# 6. Logging

Browser console logs state transitions only:

- first check;
- Available;
- first heartbeat failure;
- Unavailable;
- retry schedule/aggregate;
- recovered;
- Companion Instance or runtime identity change.

Companion terminal logs:

- startup/listen identity;
- Active Model/runtime resolution and initialization;
- first editor readiness connection;
- readiness rejection cause;
- shutdown/service-side failure.

Successful periodic heartbeat is silent. Repeated identical retry failures are
aggregated and recovery records the failure count and interruption duration.

# 7. Acceptance criteria

## User experience

- [ ] Ordinary UI contains no endpoint/profile/model selector or manual
      readiness/Ping controls.
- [ ] Entry indicator and Dock title present the same three-state Availability.
- [ ] Available is continuously visible but visually restrained.
- [ ] No technical identity or raw diagnostic enters ordinary UI.
- [ ] AI service failure never blocks native editor startup or native tools.
- [ ] Unavailable entry activation joins one check and enters only for a still
      current target identity.

## Runtime correctness

- [ ] Heartbeat is lightweight and never re-hashes model weights.
- [ ] Compatibility validation is single-flight and scoped to Companion
      Instance ID.
- [ ] Exactly one initialized Active Model Manifest crosses the protocol.
- [ ] Multiple compatible manifests require operator selection.
- [ ] Active Model/runtime identity changes fail closed.
- [ ] Busy and task-local failures do not change Availability.
- [ ] Same-identity recovery retries only connection-interrupted current work,
      once, under a new attempt ID.
- [ ] Changed-identity recovery preserves inspectable state without silently
      replaying work.

## Logging and accessibility

- [ ] Stable heartbeat creates no periodic log noise.
- [ ] Connection transitions and aggregated retry history are reconstructible
      from browser logs.
- [ ] Startup, Active Model/runtime, readiness rejection, and shutdown are
      reconstructible from Companion logs.
- [ ] Status is localized, not color-only, and politely announced.

# 8. Validation

- deterministic fake-timer heartbeat/backoff/visibility tests;
- single-flight startup and repeated-entry tests;
- target-change-during-pending-activation regression;
- one-failure debounce and real-transport-failure tests;
- Companion Instance replacement and full-revalidation tests;
- exact-one, zero, and multiple-compatible-manifest tests;
- initialized-model failure and runtime-profile mismatch tests;
- capacity Busy and task-failure non-interference tests;
- same-identity interrupted-operation new-attempt retry tests;
- changed-identity no-replay/preserved-context tests;
- terminal/browser transition-log snapshot tests;
- UI accessibility and no-technical-detail assertions;
- `npm test`;
- `npm run test:companion`;
- `npm run lint`;
- `npm run lint:locales`;
- `npm run build`.

# Non-goals

- Browser-owned Companion installation or process lifecycle.
- Browser model download, selection, activation, or upgrade.
- Endpoint discovery or trusted-LAN scanning.
- Public/multi-user backend monitoring.
- Per-subsystem status matrix in ordinary UI.
- Treating task progress, Busy, Mask unavailable, or Lift readiness as service
  Availability.
