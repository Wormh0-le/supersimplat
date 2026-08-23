# Lifecycle and Protocol Invariants

Read this file for target, View, Mask, Evidence, Candidate, acquisition-loop, identity, retry, cancellation, suspension, asynchronous work, or native-selection behavior.

## Baseline and target

- Final Spec v2.0 is the normative target.
- Shipped runtime behavior remains v1.3 until the owning V2 ticket performs an explicit, identity-bound cutover.
- V2 tickets are not implementation-ready until the current review gate marks them agent-ready.

## Stable identity and target context

- The editor owns Stable Gaussian IDs; renderer, file, chunk, draw, and Companion tensor order never become identity.
- AI Select targets one Active Splat and exposes at most one Current Target Context.
- Anchor, Views, Masks, Participation, raw Evidence, loop state, readiness, Candidate, and Uncertain are target-local.
- Restart rotates `targetContextId`, disposes target-local AI state, and preserves Native Selection/EditHistory plus reusable runtime caches.
- Previous target AI contexts are not restored or browsed.

## View and Mask authority

- All AI observation RGB uses locked gsplat and exact CameraBinding.
- `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Stable Mask is required before formal per-view Evidence.
- Editing Mask changes do not affect current Evidence until Confirm Mask atomically publishes a new Stable revision.
- Automatic publication never silently replaces a User Confirmed Stable Mask.
- Mask/View Quality, Participation, and Observation Reliability are separate authorities.
- Participation remains explicit; reliability cannot silently exclude a View or modify its Stable Mask.

## V2 acquisition-loop target semantics

- After Anchor confirmation, the Browser drives a bounded stepwise acquisition loop over the existing validated request/response transport.
- The Companion may retain disposable loop-scoped derived state, but it does not own an autonomous user-visible session.
- Each completed View is independently identity-bound and may publish progressively only when complete.
- Provisional consensus, reliability, weighted aggregation, coverage, diversity, and readiness revisions never change Native Selection.
- A Ready result auto-publishes a Candidate only at the exact terminal accepted by ADR 0020. Candidate application remains an explicit user action.
- Limited, failed, cancelled, stale, or suspended outcomes follow the current terminal/publication matrix; no implementation may invent a fallback.
- User-added View remains shipped v1.3 behavior until its reviewed cutover ticket lands. Do not remove it early.

## Attempts, replay, and cancellation

- Semantic identity and execution-attempt identity are distinct.
- Existing endpoint-level attempt IDs remain valid; a future loop identity must compose rather than replace per-request identities.
- Same-attempt replay returns or reconstructs the previously admitted observable result; it must not depend on new wall-clock timing.
- Cancellation is **semantically immediate**: no later result may acquire publication authority and the UI may leave the running state immediately.
- GPU/kernel interruption remains best effort; stale-result correctness cannot depend on physical cancellation succeeding.
- Late or racing results never overwrite newer target, dependency, policy, or iteration identity.

## Candidate and Native Selection

- Candidate derives only from exact current Included Stable Views, matching Evidence, accepted policy identities, and the sole Lift Readiness authority.
- Candidate replacement is atomic; failure preserves the prior inspectable Candidate.
- A stale Candidate remains inspectable but cannot be applied.
- Candidate changes Native Selection only through explicit Set/Add/Remove/Intersect using native `SelectOp` and `EditHistory`.
- Applying Candidate does not exit AI Select or destroy the target context.
- Native Selection-only changes and Undo/Redo do not stale Candidate.

## Scene dependency and suspension

- Material target-dependency mutation suspends rather than destroys the context.
- Suspended state remains inspectable but cannot be edited, acquired, lifted, published, or applied.
- Exact Undo may restore the prior semantic token and AI state.
- Suspend/resume of a future acquisition loop is allowed only at a reviewed safe boundary; dependency change while suspended must stale the loop rather than silently resume.

## Atomicity and failure isolation

- Stable Mask, per-view Evidence, readiness result, and Candidate replacement publish atomically.
- Partial products never become stable user state.
- Render, Mask, Evidence, acquisition, and Lift failures remain distinguishable.
- Failure preserves every independently valid completed artifact and the prior Candidate.
