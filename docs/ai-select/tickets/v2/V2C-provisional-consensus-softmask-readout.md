# V2C — Provisional Consensus and canonical bounded solve

Status: **reviewed parent envelope — Q4–Q7 accepted; awaiting stage decomposition; not agent-ready**

Blocked by: none  
Blocks: V2D

## Authority

Final Spec Amendments 003–006 and ADRs 0024–0027.

## Goal

Compute Companion-local q+s Consensus from exact current Included Stable observations and one exact frozen Scope Revision, with deterministic bounded recurrence and same-decision readout.

## Accepted contract

- q is membership tendency; s separates unknown from high-support conflict.
- Each iteration reaggregates immutable Evidence from finite scope/provenance priors.
- Reliability consumes lagged q/s only.
- Readout uses same-decision P/K/C/F moments.
- View arrival order/cache history cannot define canonical output.
- One public Consensus Revision may contain bounded private iterations.
- Scope remains frozen during solve.
- Convergence checks mean/tail/View-weight drift and period-two oscillation.
- A converged material Scope Delta advances Scope Revision and marks this result `scope-advanced`/publication-ineligible.
- The next canonical solve must bind the new Scope Revision before Readiness or Candidate.
- Non-convergence cannot mutate scope, establish Ready, or publish Candidate.

## Outputs / handoff

q/s arrays and digests; convergence diagnostics; exact Scope Epoch/Revision binding; P/K/C/F readout; proposed Scope Delta; status `current`, `scope-advanced`, `non-converged`, or `oscillating`; cold/warm equivalence diagnostics.

## Stage-level gates

GPU/CPU q/s layout; same-decision readout ABI/reference parity; canonical reduction tolerance; scope binding/status schema; journal/identity handoff to V2I; performance/OOM gates.

## Validation families

Input permutation, warm/cold equivalence, no double counting, unknown/conflict, same-round prohibition, readout parity, convergence/oscillation, frozen scope, mandatory re-solve after delta, stale scope rejection, prior Candidate preservation.

## Non-goals

No production thresholds, Browser consensus artifact, Candidate publication, Native mutation, classified-N dependency, or gradient optimizer.
