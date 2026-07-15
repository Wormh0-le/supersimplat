# Restrict the first renderer to SuperSplat v1 snapshot semantics

The first gsplat/CUDA renderer accepts only Scene Snapshot protocol version `1` with the editor's `playcanvas-gsplat-classic` rasterizer semantics, opaque background, declared spherical-harmonic bands, right-handed world coordinates, and `xyzw` quaternions. It fails compatibility checks for other conventions instead of guessing conversions. This keeps Anchor parity and replayable Evidence Snapshot interpretation tied to one explicit rendering contract while alternate input conventions are designed and calibrated separately.
