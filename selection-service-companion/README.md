# Selection Service Companion

This is the operator-owned control plane for the Object Selection PoC. It is a
separate Python 3.12 package and is never bundled into the browser editor or
its npm distribution. It intentionally contains no model weights.

## Install a locked release

Use `uv` to create an isolated environment from a tagged, locked release. The
renderer and SAM3 extras are installed into this Companion-owned `.venv`; do
not activate or search `thirdparty/sam3/.venv`:

```sh
cd selection-service-companion
uv sync --python 3.12.12 --locked --extra renderer --extra sam3
uv run --locked --extra renderer --extra sam3 selection-service install \
  --release 0.1.0 \
  --lock-file ./uv.lock
```

The `install` command hashes the supplied `uv.lock` and re-verifies that exact
file before the Companion starts. It records the selected release and lock
digest in the operator's local Companion state; it does not download a model
or modify the editor. The renderer runtime is accepted only when the running
process reports Python 3.12.12, PyTorch 2.11.0+cu128, CUDA 12.8, and gsplat
1.5.3 installed from source commit
`77ab983ffe43420b2131669cb35776b883ca4c3c`.

## Render complete Anchor contributor evidence

The production Companion registers its locked gsplat Contributor renderer by
default, but advertises it as ready only after the release lock and current
process pass the checks above. The renderer accepts only protocol-1 SuperSplat
snapshots using `playcanvas-gsplat-classic`, opaque background, right-handed
world coordinates, XYZW quaternions, the declared effective DC/SH schema, and
render configuration `supersplat-effective-rgb-v1`.
Malformed or unsupported values fail before the snapshot enters the immutable
service cache.

Renderer-owned Frame Set entries bind a pinhole camera with
`convention: "opencv-world-to-camera"`, a row-major 4x4 `worldToCamera`
matrix, a row-major 3x3 `intrinsics` matrix, and finite `nearPlane` and
`farPlane` values. One gsplat call produces service RGB and raster alpha, then
the complete contributor-ID operation consumes that call's projection and tile
data. Tensor row IDs map directly through the immutable Scene Snapshot order to
Stable Gaussian IDs; padded `-1`/zero entries are discarded. Every pixel must
conserve contributor mass against raster alpha within
`2e-6 + 1e-5 * abs(alpha)`. Missing support, invalid IDs or weights, and mass
mismatch abort the preview; there is no nearest, visible-only, top-k, or custom
backend attribution fallback.

For the editor-owned Anchor, the renderer compares its 8-bit service RGB with
the registered PNG. A mean absolute channel error of at most `2/255` is normal;
an error through `0.25` is moderate and disables outside-mask negative
evidence; a larger error, missing/invalid PNG, or dimension mismatch is severe
and aborts Evidence lifting. These thresholds are part of the first locked
renderer policy and must change with its render-configuration revision.

## Install a model separately

The operator supplies an already acquired checkpoint and a Model Manifest. The
manifest's `checkpointDigest` must match the checkpoint's SHA-256 digest.

```sh
uv run --locked --extra renderer --extra sam3 selection-service models install \
  --manifest /secure/manifests/sam31.json \
  --weights /secure/models/sam31_multiplex.pt
```

The Companion records the verified manifest and external checkpoint path. It
does not copy the checkpoint into the package or send a path to the editor.

For `adapterId: "sam3.1"`, `runtimeConfigDigest` must be
`sha256:39a47a6b641b55bf967b7b73fb7e76efa900ff69ecfed764bcce1a89683c3cba`.
It binds the Companion's fixed SAM 3.1 multiplex baseline: eight objects per
session, multiplex count 16, FA3 and compilation disabled, a 0.5 output
threshold, rejection of degenerate full-frame candidates, CPU-backed frame
storage, and GPU-backed tracker state. A changed runtime configuration needs a
new adapter baseline and Model Manifest digest.

## Produce a complete Frame Set Mask Track

The locked `sam3` extra installs the compatible SAM 3.1 runtime into the same
operator-owned Companion environment. Use a manifest whose `adapterId` is
`sam3.1`. The browser registers every ordered Frame Set PNG with its SHA-256
digest; the Companion materializes a temporary sequence, replays the point
Prompt Log, and gives only the verified external checkpoint path to SAM 3.1.
Returned masks are converted to generic immutable bitsets before they cross
the service boundary. The completed Mask Set records generic SAM candidate
selection diagnostics (candidate index, score where supplied, foreground area,
point consistency, and the selected candidate); it never exposes raw tensors
or treats model scores as cross-adapter confidence.

Each logical session admission generates a unique `openRequestId`; browser
retries reuse that one ID only within the same opening attempt. If the browser
loses an admission response, it re-registers the immutable Frame Set and
repeats that ID to recover the same session. If recovery fails, it idempotently
closes the open request before releasing the Frame Set. A Frame Set claimed by
a live session is retained until that session has cancelled and drained its
inference work.

`point-mask-v1` remains a deterministic protocol/reference adapter for local
contract tests. Production state neither registers nor advertises it. It is
not image or model inference and must not be selected as a substitute for the
SAM 3.1 adapter.

## Start the control plane

The default profile listens only on loopback. The editor must be configured
with the same endpoint and exact origin shown here.

```sh
uv run --locked --extra renderer --extra sam3 selection-service start \
  --endpoint http://127.0.0.1:8787 \
  --allow-origin https://editor.example
```

Trusted-LAN use must be explicit and HTTPS-only:

```sh
uv run --locked --extra renderer --extra sam3 selection-service start \
  --profile trusted-lan \
  --endpoint https://192.168.1.20:8787 \
  --allow-origin https://editor.example \
  --cert /secure/certs/selection.lan.pem \
  --key /secure/certs/selection.lan-key.pem
```

The process stays in the operator's terminal and stops with `Ctrl+C`. The
browser never starts, stops, upgrades, installs, or rolls back this process.
Trusted-LAN hosts must resolve only to private-network addresses; public,
unspecified, and loopback listeners are rejected.

This release exposes `/health`, `/capabilities`, and an Object Selection
Session admission lease. It verifies the locked gsplat/CUDA runtime from the
current Companion process only. Whenever the release lock or runtime identity
does not match, renderer status remains unavailable with an operator-facing
diagnostic. The control plane reserves
exactly one Object Selection Session lease at a time and returns `busy` to a
second opener; closing that lease restores capacity. It still proves the
locked-install, model-manifest, CORS, browser transport, and single-session
readiness contract.

## Run the controlled-overlap production trial

Run prediction without giving the process a Ground Truth path. The command
uses the installed locked release and SAM3.1 Model Manifest, executes the real
gsplat/CUDA Generated View path, and atomically publishes a hashed PoC Run
Record only after all required artifacts are complete:

```sh
uv run --locked --extra renderer --extra sam3 python \
  ../scripts/benchmarks/run_controlled_overlap_trial.py predict \
  --output /secure/poc-runs/controlled-overlap-seed-1
```

Only after prediction is sealed, invoke the independent scorer with the
frozen Ground Truth:

```sh
uv run --locked --extra renderer --extra sam3 python \
  ../scripts/benchmarks/run_controlled_overlap_trial.py score \
  --prediction /secure/poc-runs/controlled-overlap-seed-1 \
  --ground-truth ../docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap_ground_truth.json \
  --output /secure/poc-scores/controlled-overlap-seed-1.json
```

The scorer verifies the prediction seal and every artifact hash before it
opens Ground Truth. The older deterministic one/two-view fixture outputs are
diagnostic lifting evidence; they are not production acceptance records.
