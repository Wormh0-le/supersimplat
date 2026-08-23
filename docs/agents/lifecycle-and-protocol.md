# Lifecycle and Protocol Invariants

Read this file for target, View, Mask, Evidence, Seed, Core/Frontier, Candidate, acquisition-loop, Expert Recovery, identity, replay, cancellation, suspension, or native-selection behavior.

## Baseline and implementation gate

- Final Spec v2.0 with Amendments 001/002 is the target.
- Runtime remains v1.3 until an explicit reviewed cutover.
- No parent envelope is implementation-ready; both mapping and review status must mark an exact stage agent-ready.

## Stable authority

- The editor owns Stable Gaussian IDs and one Current Target Context.
- Stable Mask, Participation, raw Evidence, Seed/Core/Frontier, provisional consensus, Candidate, and Native Selection remain distinct.
- User Confirmed/manual Stable Masks cannot be silently replaced or automatically downweighted.
- Candidate changes Native Selection only through explicit Set/Add/Remove/Intersect backed by native EditHistory.

## Seed, Core, and discovery

- Conservative Seed is precision-first, incomplete, and non-executable.
- Seed may initialize Core and early framing but never hard-bounds Evidence or discovery.
- Core may expand without shrinking inside one stable input revision.
- An authoritative Stable input revision may rotate/rebuild Core through a new identity.
- Discovery Envelope must have sources independent of the Seed.
- Discovery Frontier is reversible and never directly Candidate membership.
- Boundary contact, Core-external Stable observation support, coherent multi-view support, and User Confirmed recovery observations may enter Frontier.
- Core Observation Coverage and Frontier Debt are distinct; high Core Coverage alone cannot establish completeness.

## Rendering and Evidence

- All AI observation RGB uses locked gsplat and exact CameraBinding.
- `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Current production Evidence remains immutable single-N P/N/V.
- CWED/depth moments are internal features and not Browser depth truth.
- Classified N is experimental and cannot block Reliability/Aggregation.
- Stable Mask, per-view Evidence, and Candidate replacement publish atomically.
- Failed/stale work preserves independently valid products and the prior inspectable Candidate.

## Automatic acquisition

- Anchor confirmation starts automation by default.
- The running loop owns a bounded sequence of planner-selected Generated Views.
- View Utility must preserve both exploitation and bounded discovery exploration.
- Users do not manage cameras or invoke persistent Generate More while the loop runs.
- Cancel changes product authority immediately; kernel/process interruption is best effort.

## Expert Recovery

- Available only after the loop stops and while the target is active.
- Add Observation creates a User-added View through authoritative RGB and ordinary Stable Mask/Participation rules.
- Continue Acquisition starts a fresh bounded attempt from exact current stable artifacts.
- A new Stable observation stales the previous Candidate; it never patches Candidate or Native Selection.
- Suspended targets must restore exact compatible dependencies first.

## Replay and identity

Loop, iteration, revision, and endpoint-attempt hierarchy remains a V2I review gate. Do not collapse existing attempts or claim deterministic wall-clock replay prematurely.
