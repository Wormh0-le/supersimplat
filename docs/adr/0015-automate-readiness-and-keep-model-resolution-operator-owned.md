# Automate AI Select readiness and keep model resolution operator-owned

Status: accepted

AI Select will expose only a restrained Connecting, Available, or Unavailable status while the browser performs background health and compatibility checks automatically. The Companion resolves one process-lifetime Active Model Manifest—automatically when exactly one compatible model exists, otherwise through explicit operator configuration—and the browser binds that identity without offering endpoint, ping, or model-selection controls to ordinary users. Lightweight heartbeat, opaque Companion Instance identity, and full versioned Runtime Profile validation remain separate so recovery stays fail-closed without repeatedly hashing or initializing model artifacts.

## Consequences

- Loopback uses the product default; trusted-LAN endpoint/profile configuration remains operator/deployment-owned and is never auto-discovered.
- A lightweight heartbeat detects reachability and process replacement; first connection, recovery, or Instance ID change triggers full compatibility validation.
- Service availability remains separate from capacity, task progress, and per-operation failure.
- Browser and Companion logs retain technical connection/runtime identity while the product UI exposes no endpoint, manifest, or raw diagnostic details.
