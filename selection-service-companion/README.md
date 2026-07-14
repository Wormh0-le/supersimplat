# Selection Service Companion

This is the operator-owned control plane for the Object Selection PoC. It is a
separate Python 3.12 package and is never bundled into the browser editor or
its npm distribution. It intentionally contains no model weights.

## Install a locked release

Use `uv` to create an isolated environment from a tagged, locked release:

```sh
uv tool install --python 3.12 --from ./selection-service-companion supersplat-selection-service-companion
selection-service install --release 0.1.0 --lock-digest sha256:RELEASE_LOCK_DIGEST
```

For a checked-out release, verify `uv.lock` before installing it. The `install`
command records the selected release and lock digest in the operator's local
Companion state; it does not download a model or modify the editor.

## Install a model separately

The operator supplies an already acquired checkpoint and a Model Manifest. The
manifest's `checkpointDigest` must match the checkpoint's SHA-256 digest.

```sh
selection-service models install \
  --manifest /secure/manifests/sam31.json \
  --weights /secure/models/sam31_multiplex.pt
```

The Companion records the verified manifest and external checkpoint path. It
does not copy the checkpoint into the package or send a path to the editor.

## Start the control plane

The default profile listens only on loopback. The editor must be configured
with the same endpoint and exact origin shown here.

```sh
selection-service start \
  --endpoint http://127.0.0.1:8787 \
  --allow-origin https://editor.example
```

Trusted-LAN use must be explicit and HTTPS-only:

```sh
selection-service start \
  --profile trusted-lan \
  --endpoint https://selection.lan:8787 \
  --allow-origin https://editor.example \
  --cert /secure/certs/selection.lan.pem \
  --key /secure/certs/selection.lan-key.pem
```

The process stays in the operator's terminal and stops with `Ctrl+C`. The
browser never starts, stops, upgrades, installs, or rolls back this process.

This release exposes only `/health` and `/capabilities`. It reports the
renderer as unavailable until a later scene-transport release installs the
actual gsplat/CUDA adapter; this is deliberate and prevents a false ready
state. It still proves the locked-install, model-manifest, CORS, browser
transport, and single-session readiness contract.
