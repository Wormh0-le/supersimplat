# Selection Service Lifecycle Decision

Status: confirmed design decision for [Choose local Selection Service packaging and lifecycle](https://github.com/Wormh0-le/supersimplat/issues/11).

This record packages the already-defined Selection Service Interface for the Object Selection PoC. It fixes how an operator obtains and runs the service without changing editor-owned Scene Snapshot identity, Selection Commit, or the ObjectSelectionSession seam.

## Decision

The service is an explicitly started **Selection Service Companion**: a separately installed, versioned Python package in a `uv`-managed private Python 3.12 environment. It is neither bundled into SuperSplat's npm/browser distribution nor required to run in Docker. A Docker image may later reproduce a development or benchmark environment, but is not a user prerequisite.

The operator owns the Companion process. The editor owns only Object Selection Sessions through the injected Selection Service Adapter. The browser never starts, upgrades, or stops a local CUDA process.

## Installation and model artifacts

The supported installation flow has two explicit, independently auditable stages:

1. The operator installs a locked Companion release into its private environment. The release fixes the Companion build, Python dependencies, Torch/CUDA-compatible renderer dependencies, and adapter source revisions; it does not inherit an arbitrary global Python or Conda environment.
2. The operator separately installs a selected Model Manifest's weights. This action obtains any gated artifact, verifies its checkpoint digest, records its license and runtime configuration, and makes the manifest eligible to appear in `getCapabilities()`.

The editor never invokes a package installer, downloads model weights, or chooses a substitute model. Weights remain unbundled. A research-only or non-commercial adapter remains isolated behind the Selection Service Adapter and cannot become an implicit core dependency.

The intended CLI shape is conceptually `selection-service install`, `selection-service models install <manifest>`, `selection-service start`, `selection-service stop`, and `selection-service upgrade <release>`. Exact command spelling is not an editor contract.

## Start, discovery, capacity, and stop

The operator explicitly starts the Companion. Its default endpoint binds only to `127.0.0.1` and uses a stable, operator-configurable endpoint. The editor receives that configured endpoint; it does not scan ports, use mDNS, infer a random handshake port, or discover machines automatically.

Trusted-LAN Mode is opt-in. The operator explicitly chooses the private network listener and configures the same endpoint in the editor. The Companion must not bind a public Internet address, and the PoC does not add accounts, API keys, multitenant access, remote job scheduling, or a public service registry.

One Companion admits exactly one active Object Selection Session. An additional `openMaskSession` fails with a visible `busy` result; it does not queue, preempt, or share the first session. `getCapabilities()` reports this capacity.

The Companion stays running until the operator explicitly stops it or the operating system stops it. Closing or refreshing an editor tab never authoritatively kills the process. On normal session closure, cancellation, loss of the session lease, or graceful process stop, the service cancels unfinished work and releases session-specific Frame Set, Scene Snapshot, mask, and continuation caches. It must not publish a partial Mask Set, Evidence Snapshot, or preview. A warm model may remain resident while the process continues to run.

On graceful stop, the Companion first rejects new sessions, then cancels or drains active work, releases GPU resources, and exits. An idle-exit policy is deliberately not enabled by default; a later configurable timeout must preserve the same cancellation and cleanup guarantees.

## Health and readiness

The lifecycle has two distinct checks:

| Check                        | Meaning                                                                                                                                                                                                                               | Editor behavior                                                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Lightweight health operation | The configured Companion endpoint and process can respond.                                                                                                                                                                            | Report a reachable process only; do not open a session yet.                                                                          |
| `getCapabilities()`          | The service can safely accept a new session under the selected configuration. It reports protocol and service-build versions, renderer/CUDA state, supported prompt features, installed Model Manifests, and single-session capacity. | Open a session only after the required protocol, renderer, adapter, separately installed weights, and Model Manifest are compatible. |

Starting, missing weights, unavailable GPU, renderer failure, a protocol mismatch, `busy`, browser permission denial, or an invalid endpoint make the service unavailable for a new session. The editor presents an actionable local diagnostic and never silently falls back to browser inference, an older service, another model, or an earlier result. An already published Candidate Object Selection remains governed by the existing failed-update recovery rule.

## Browser transport and trusted-LAN profile

The Adapter hides transport from the ObjectSelectionSession Module. Its default control plane is Fetch over HTTP(S), preserving binary request and response bodies where the Scene Snapshot or result size requires them. A WebSocket is not a way around local-network browser controls and is not required for the PoC.

The supported reference browser is current Chromium. The editor runs in a secure context, except for the standards-defined loopback development exception. The same-machine profile may use `https://editor` to `http://127.0.0.1:<port>` only as an explicitly tested Chromium compatibility profile: it requires the browser's loopback Local Network Access permission and the configured CORS policy. It is not a cross-browser promise.

Trusted-LAN Mode uses `https://editor` to an explicitly configured `https://lan-host` endpoint with a browser-trusted certificate. It requires the browser's Local Network Access permission where applicable. Private-network HTTP is not a supported LAN fallback. A permission denial, unsupported browser, endpoint switch, or invalid certificate leaves the service unavailable; the editor reports the condition and does not bypass it with an experimental browser feature.

For every browser-callable Companion operation, including health and `getCapabilities()`, the service:

- accepts only an operator-configured exact editor-origin allowlist;
- returns the matching CORS origin and `Vary: Origin` when that value varies;
- handles the required `OPTIONS` preflight methods and headers for its actual binary requests; and
- uses `credentials: 'omit'` for this PoC.

CORS governs browser response sharing, not network authorization. Loopback-only default binding, explicit LAN listener configuration, the editor-origin allowlist, browser local-network permission, HTTPS for LAN, and the operator's firewall/VPN controls are separate layers. Public Internet exposure is unsupported.

The evidence and source links for this browser policy are in [Static editor → local Selection Service transport](../research/browser-to-local-selection-service-transport.md). Each PoC Run Record records the reference browser/version and non-secret transport profile so permission and reconnect behavior can be reproduced.

## Upgrade and rollback

Companion and model updates are explicit operator actions. There is no background update, in-place mutation of a running process, or automatic downgrade.

To upgrade, the operator closes active sessions, stops the Companion, installs a new locked release, and starts it. `getCapabilities()` then exposes the new service build, protocol revision, and installed Model Manifest digests. An incompatible protocol prevents a new session from opening. Existing sessions never migrate across a process, dependency, renderer, model, or policy version.

Model installations are content-addressed by their manifests and digests rather than overwriting a prior checkpoint. If a new release cannot pass readiness, the operator manually returns to the prior verified locked environment and restarts it. The editor does not silently roll back.

## Verification obligations

Before the lifecycle is considered usable, verify all of the following:

1. A fresh installation creates the isolated locked Python environment and does not bundle a model checkpoint.
2. A model installation records its digest, license, adapter revision, and runtime configuration; an absent or changed artifact prevents readiness.
3. The default Companion listener is loopback-only, and LAN binding requires an explicit private endpoint and editor-origin configuration.
4. Health without compatible capabilities cannot open a session; every readiness failure is diagnosable and has no fallback path.
5. The supported Chromium same-machine profile exercises Local Network Access grant, denial, CORS success/error/preflight, reconnect, and an actual binary Scene Snapshot request. The trusted-LAN profile repeats that check with its real certificate and firewall configuration.
6. A second editor receives `busy` without altering the active session; disconnect, cancellation, and graceful stop discard partial work and reclaim session resources.
7. Upgrade rejects incompatible protocols, does not migrate an active session, preserves previously installed Model Manifests, and permits an operator-controlled rollback.

## Deliberately not prescribed

The decision does not prescribe a TCP port number, filesystem layout, internal HTTP route names, certificate issuer, firewall product, exact CLI spelling, or an idle-timeout duration. Those are implementation details so long as they obey the lifecycle and transport rules above. Cross-browser parity, public service hosting, authentication, multitenancy, job scheduling, production operations, and automatic service launch remain out of scope.

## Related records

- [Promptable-Mask Service Contract Prototype](promptable-mask-service-contract.md) — logical mask and cache commands.
- [Standalone Gaussian Object Selection PoC Technical Specification](../specs/standalone-gaussian-object-selection-poc.md) — editor-facing behavior and test gates.
- [Static editor → local Selection Service transport](../research/browser-to-local-selection-service-transport.md) — current primary-source browser evidence.
