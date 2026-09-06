# Issue #115 Bonsai input bundle

This directory contains the captured inputs for issue #115. It is an input
dataset only; no 3D aggregation implementation or execution is included.

`bonsai-A-input.zip` and `bonsai-B-input.zip` contain the confirmed A7/B15
inputs. Each archive contains the authoritative 1008×672 RGB PNG, its raw
LSB-first row-major bitmask, the composed editor `CameraBinding`, request and
Stable-ID identity, and the binary Scene Snapshot. The masks are the published
user-confirmed revisions after the SAM draft and Point/Box/Paint/Erase edits;
the target is the bonsai plant and flowerpot, excluding the tabletop and
independent supporting furniture.

`bonsai-C-inspection.zip` contains the C11 RGB and composed binding for the
independent inspection view. It has no mask and is excluded from fusion.

`point_cloud.ply` is the source Bonsai model. `camera-presets.json` records the
source A7/B15/C11 poses and the 1008×672 projection proposal. `preparation.json`
records the pair-level confirmation, source and composed binding digests,
rendered RGB digests, mask digests, and the shared Scene Snapshot identity.

The PLY and input archives are tracked with Git LFS. On another checkout, run
`git lfs install` and `git lfs pull` before opening or validating the inputs.
The LFS objects total about 1.25GB, so the remote must have enough LFS storage
and bandwidth; this change creates a local commit and does not push it.

The older pending A/B exports and review-only overlay images remain outside the
repository as operator history. They are not authoritative inputs.
