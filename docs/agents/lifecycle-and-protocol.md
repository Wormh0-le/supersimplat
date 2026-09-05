# Lifecycle and Protocol Invariants

Read [Domain authority](domain.md) for current scope and the distinction between target behavior and shipped implementation. The retained Q10/Q11 user contract lives in Issue #37.

## Requests and bounded acquisition

Bind requests/results to the actual target, dependency/input revision, relevant View/artifacts, and endpoint attempt identity. Accept a result only while the current controller still expects that exact work. Exact duplicate publication is idempotent; conflicting duplicates fail closed. Keep accepted artifacts immutable.

Browser-owned serial control may use current immutable state, a request/result index, concrete counters, and an ordinary exportable event log. A full hash-chained Decision Journal, generic prepaid cost ledger, and exact historical-run replay after cache loss are not first-release requirements.

Bound successful observations, total attempts including failures, retries, any enabled refinement/recompute, and cumulative work across Continue. Duplicate delivery must not consume twice. Actual latency and timeout support diagnostics/safe stopping, not transient semantic reranking.

Cancel closes the running attempt's mutation and automatic-publication gates immediately; transport cancellation is best effort. Late results cannot revive it. Preserve independently valid completed artifacts and the prior inspectable Candidate.

Pause precedes authoritative editing. One-click auto-Pause retains and revalidates the original intent, executes it once at a safe boundary, and remains paused. Passive inspection does not pause. Resume requires compatible unchanged input, retained execution state, and remaining limits; changed input or terminal recovery uses an explicit fresh Continue attempt. Continue never resets cumulative protection into unbounded work.

Cache loss or incompatible restoration may require a diagnosed stop and a new explicit attempt. Do not call new computation an exact Resume. Preserve existing exact dependency/Undo restoration where it is actually supported; never remap stale artifacts to make recovery appear successful.

## Candidate publication and application

Publication consumes a complete immutable snapshot of exact current qualified computation and Stable inputs. Scope, roles, Evidence, readiness, and policy/runtime identity must agree. A development-only single-pass result has no production publication authority. If an iterative solver is enabled, non-convergence or oscillation remains ineligible; never invent a converged flag for another method.

Only eligible `Ready + ready-low-gain` normal success auto-publishes. Eligible forced Ready and Limited require distinct `Use Ready Candidate` and `Use Limited Candidate` consent. Use actions bind the existing snapshot, are idempotent, and do not recompute. Not Ready, stale, suspended, incomplete, late, or Scope-mismatched results cannot publish regardless of user consent.

Re-Lift recomputes exact current Stable inputs; it neither accepts an old snapshot nor starts/resumes acquisition. Eligible Ready may publish as that user-requested computation; Limited still requires separate consent.

Only a complete still-compatible snapshot committed before Cancel may later support a new explicit publication attempt. Cancel itself and post-Cancel work never create publication authority. Replacement is atomic and failures preserve the previous result.

Starting acquisition alone does not stale the prior Candidate. It remains inspectable while its Native Set/Add/Remove/Intersect operations are temporarily blocked. A real bound-input change causes ordinary staleness. Cancel or a safe terminal boundary restores application only if the Candidate remains exact current.

Candidate publication never applies Native Selection or changes Native EditHistory. Stable Mask, Participation, raw Evidence, derived Scope/Consensus, Candidate, and Native Selection remain distinct.
