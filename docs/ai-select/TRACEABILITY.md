# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Final Spec v1.3 implementation traceability is preserved under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Authority

Traceability covers Final Spec v2.0 with Amendments 001–004 and ADRs 0025/0024/0023/0022, residual ADR 0021, and ADR 0020.

## Carried-over implemented foundations

| ID | Requirement | Status |
|---|---|---|
| C001 | One Current Target Context and Stable Gaussian identity | implemented-v1.3 |
| C002 | Authoritative gsplat RGB and exact CameraBinding | implemented-v1.3 |
| C003 | SAM 3 Image single-result Mask authoring | implemented-v1.3 |
| C004 | Stable Mask and Participation authority | implemented-v1.3 |
| C005 | User Confirmed Stable Mask preservation | implemented-v1.3 |
| C006 | same-decision Direct P/N/V with one Negative Mass | implemented-v1.3 |
| C007 | Render/Evidence Working Set separation and boundary contact | implemented-v1.3 |
| C008 | Lift Readiness authority | implemented-v1.3 |
| C009 | atomic Candidate replacement and stale blocking | implemented-v1.3 |
| C010 | explicit Native Set/Add/Remove/Intersect | implemented-v1.3 |
| C011 | target dependency suspension and exact Undo recovery | implemented-v1.3 |
| C012 | User-added View foundation | implemented-v1.3 / retained for recovery |

## New v2 target requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N001 | projected Gaussian depth is aligned and validated through the Direct Evidence ABI | V2A1 | reviewed-parent / decomposition-pending |
| N002 | M0/M1/M2 use the accepted contribution sequence and derive CWED/variance internally | V2A2 | reviewed-parent / decomposition-pending |
| N003 | CWED is invalid at low mass and is not first-hit or authoritative surface depth | V2A2 | accepted-scope |
| N004 | depth-classified Negative Evidence is nonblocking until explicit promotion | V2AX | accepted-scope / experimental |
| N005 | S0 Seed uses semantic P/N/V, visibility, conflict, and connectivity | V2B | reviewed-parent / decomposition-pending |
| N006 | S1 adds soft center-depth consistency without permanent exclusion | V2B | reviewed-parent / decomposition-pending |
| N007 | S0/S1 run in parallel frozen shadow evaluation before production choice | V2B / calibration owner TBD | accepted-scope / owner-incomplete |
| N008 | Conservative Seed is non-ownership and never a hard Evidence/discovery boundary | V2B | accepted-scope |
| N009 | Core is high-confidence and monotonic only inside one stable input revision | V2B/V2E | accepted-scope / review-required |
| N010 | Discovery Envelope is seed-independent and may contain uncertain/context support | V2B | accepted-scope |
| N011 | Discovery Frontier is reversible, diagnosable, and never directly Candidate | V2B/V2E | accepted-scope / review-required |
| N012 | boundary contact, new Stable Views, multi-view support, and Expert Recovery discover outside Seed | V2B/V2E/V2J | accepted-scope / review-required |
| N013 | Core Coverage and Frontier Debt remain separate | V2B/V2E | accepted-scope / review-required |
| N014 | readiness considers Core Coverage, Diversity, Frontier Debt, remaining Utility, and identity | V2E/V2G | accepted-scope / review-required |
| N015 | Consensus stores continuous q and independent support/knownness s | V2C | accepted-scope / review-required |
| N016 | canonical consensus is deterministic bounded solve over exact Included Stable Evidence | V2C | accepted-scope / review-required |
| N017 | one public Consensus Revision may contain bounded private Solver Iterations | V2C | accepted-scope / review-required |
| N018 | Reliability uses lagged q/s; same-round feedback is forbidden | V2C/V2D | accepted-scope / review-required |
| N019 | weighted aggregation applies Reliability to P/N while raw V is unchanged | V2D/V2E | accepted-scope / review-required |
| N020 | View Utility is prospective and separate from Coverage/Readiness | V2F | accepted-scope / review-required |
| N021 | Utility balances Core, Frontier, Uncertain, diversity, duplication, and cost | V2F | accepted-scope / review-required |
| N022 | candidate pool, scoring, tie-break, and replay are deterministic | V2F | review-required |
| N023 | dual budget, failure taxonomy, and bounded termination are explicit | V2G | review-required |
| N024 | Ready plus low marginal gain may auto-publish Candidate atomically | V2H | review-required |
| N025 | Limited outcomes require explicit consent and never self-apply | V2H | review-required |
| N026 | Browser drives the loop over validated request/response boundaries | V2I | review-required |
| N027 | loop/iteration/request identity and replay are hierarchical and fail closed | V2I | review-required |
| N028 | Cancel prevents later publication while preserving completed artifacts | V2I/V2J | review-required |
| N029 | automatic acquisition is the default post-Anchor path | V2I/V2J | accepted-scope |
| N030 | Expert Recovery is secondary and unavailable while the loop runs | V2J | accepted-scope / review-required |
| N031 | Add Observation retains User-added View with authoritative RGB and Stable Mask rules | V2J | accepted-scope / review-required |
| N032 | Continue Acquisition starts a fresh bounded attempt from exact current artifacts | V2G/V2I/V2J | accepted-scope / review-required |
| N033 | a new recovery observation stales Candidate and never patches Native Selection | V2H/V2J | accepted-scope / review-required |
| N034 | User Confirmed/manual observations retain Reliability exemption | V2D/V2J | accepted-scope / review-required |
| N035 | persistent planning controls remain retired | V2J | accepted-scope |
| N036 | calibration, policy freeze, production identity, cutover, and qualification have explicit owners | unassigned | blocker |
| N037 | scope is frozen during a solve and Scope Delta commits only afterward | V2C/V2E | accepted-scope / review-required |
| N038 | non-converged consensus cannot establish Ready or publish Candidate | V2C/V2E/V2H | accepted-scope / review-required |
| N039 | production readout accumulates semantic-scope, foreground, knownness, Core, and Frontier moments from the same accepted sequence | V2C | accepted-scope / review-required |
| N040 | support-aware membership contracts low-support q toward neutral and readout remains Companion-local | V2C | accepted-scope / review-required |
| N041 | Reliability uses trusted region-normalized positive/negative residuals, low-weight boundary, and excludes Far Neutral | V2D | accepted-scope / review-required |
| N042 | positive Frontier protection is asymmetric; insufficient comparison support is neutral and diagnosable | V2D | accepted-scope / review-required |
| N043 | leave-one-out Reliability is a nonblocking offline reference until explicit promotion | V2D reference / calibration owner TBD | accepted-scope / owner-incomplete |

## Coverage result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 43
mapped new requirements             = 42
unassigned release requirement      = N036
reviewed parent direction           = V2A, V2B
accepted cross-ticket decisions     = Q4-B, Q5-D
agent-ready stages                  = 0
next review item                    = Q6 q/s update + Reliability normalization + convergence
```

No implementation closure may be claimed while N036 is unassigned or while relevant stages remain review-required/decomposition-pending.
