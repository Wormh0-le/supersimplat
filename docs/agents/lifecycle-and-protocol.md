# Lifecycle and Protocol Invariants

Read this file for target, View, Mask, Evidence, Candidate, acquisition-loop, expert-recovery, identity, replay, cancellation, suspension, or native-selection behavior.

## Baseline and implementation gate

- Final Spec v2.0 plus Amendment 001 is the normative target.
- Runtime remains v1.3 until the owning reviewed V2 stage performs an explicit cutover.
- No V2 ticket is implementation-ready unless current mapping and review status both mark it agent-ready.

## Stable authority

- The editor owns Stable Gaussian IDs and one Current Target Context.
- Anchor, Views, Masks, Participation, raw Evidence, acquisition state, readiness, Candidate, and Uncertain are target-local.
- Stable Mask, Participation, Direct Evidence, Candidate, and Native Selection remain distinct authorities.
- User Confirmed/manual Stable Masks cannot be silently replaced or automatically downweighted.
- Candidate changes Native Selection only through explicit Set/Add/Remove/Intersect backed by native EditHistory.

## Rendering and publication

- All AI observation RGB uses locked gsplat and exact CameraBinding.
- `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Stable Mask, per-view Evidence, and Candidate replacement publish atomically.
- Failed or stale work preserves independently valid Views, Stable Masks, raw Evidence, and the prior inspectable Candidate.
- Late results never attach to a newer target/dependency/policy identity.

## Automatic acquisition

- Anchor confirmation starts automation by default.
- The running Acquisition Loop owns a bounded sequence of planner-selected Generated Views.
- Users do not manage cameras or invoke persistent Generate More while the loop runs.
- Cancel changes product authority immediately: no later result may publish. GPU/process interruption remains best effort.

## Expert Recovery

Expert Recovery is available only when:

- no acquisition loop is running;
- the target is active, not Suspended;
- the user invokes a secondary recovery/advanced action.

### Add Observation / Use Current View

- Captures an explicit Editor CameraBinding as a User-added View.
- Uses authoritative RGB and the ordinary SAM/manual Mask workflow.
- Enters Evidence only after Stable Mask publication and Included Participation.
- A new current Stable observation stales the prior Candidate; it never patches Candidate or Native Selection directly.

### Continue Acquisition

- Starts a fresh bounded loop attempt from exact current stable artifacts.
- Is not same-attempt replay, identical-input retry, or a persistent planning control.
- Does not automatically apply a Candidate.
- Eligibility, budget reset, and attempt hierarchy remain review gates for V2G/V2I/V2J.

## Recovery after terminal states

Expert Recovery may be offered after Ready, Limited, Not Ready, budget/no-feasible/stage-failure terminals, or user Cancel. Suspended targets must first restore an exact compatible dependency state.

The previous Candidate remains inspectable. Once stale, it cannot be applied until current recomputation atomically publishes a replacement.

## Replay and identity

The loop-level, iteration-level, and endpoint-attempt identity hierarchy is not yet closed. Do not collapse existing request attempts into one ID or claim exact deterministic replay from wall-clock budgets before V2I review resolves the contract.
