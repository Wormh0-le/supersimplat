# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Final Spec v1.3 implementation traceability is preserved under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Authority

Traceability covers Final Spec v2.0 as amended by Amendment 001 and ADRs 0022/0021/0020.

## Carried-over implemented foundations

| ID | Requirement | Status |
|---|---|---|
| C001 | One Current Target Context and Stable Gaussian identity | implemented-v1.3 |
| C002 | Authoritative gsplat RGB and exact CameraBinding | implemented-v1.3 |
| C003 | SAM 3 Image single-result Mask authoring | implemented-v1.3 |
| C004 | Stable Mask and Participation authority | implemented-v1.3 |
| C005 | User Confirmed Stable Mask preservation | implemented-v1.3 |
| C006 | same-decision Direct P/N/V | implemented-v1.3 |
| C007 | Render/Evidence Working Set separation | implemented-v1.3 |
| C008 | Lift Readiness authority | implemented-v1.3 |
| C009 | atomic Candidate replacement and stale blocking | implemented-v1.3 |
| C010 | explicit Native Set/Add/Remove/Intersect | implemented-v1.3 |
| C011 | target dependency suspension and exact Undo recovery | implemented-v1.3 |
| C012 | User-added View foundation | implemented-v1.3 / retained for recovery |

## New v2 target requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N001 | contribution-weighted depth readout uses the accepted Direct Evidence sequence | V2A | review-required |
| N002 | Negative Evidence gains reviewed depth classification and identity migration | V2A | review-required |
| N003 | precision-first Conservative Seed is non-ownership and diagnosable | V2B | review-required |
| N004 | Core Target denominator expands monotonically without manufacturing coverage | V2B/V2E | review-required |
| N005 | provisional consensus is Companion-local, bounded, and non-executable | V2C | review-required |
| N006 | consensus soft-mask readout does not create an independent visibility authority | V2C | review-required |
| N007 | reliability uses lagged 3D consistency with anti-confirmation-bias guards | V2D | review-required |
| N008 | reliability affects semantic P/N but not raw V | V2D/V2E | review-required |
| N009 | weighted incremental aggregation equals full recomputation | V2E | review-required |
| N010 | View Utility is prospective and separate from realized coverage/readiness | V2F | review-required |
| N011 | candidate pool and utility selection are deterministic and replayable | V2F | review-required |
| N012 | dual budget, failure taxonomy, and bounded termination are explicit | V2G | review-required |
| N013 | Ready plus low marginal gain may auto-publish Candidate atomically | V2H | review-required |
| N014 | Limited outcomes require explicit consent and never self-apply | V2H | review-required |
| N015 | Browser drives the loop over validated request/response boundaries | V2I | review-required |
| N016 | loop/iteration/request identity and replay are hierarchical and fail closed | V2I | review-required |
| N017 | running-loop Cancel prevents later publication while preserving completed artifacts | V2I/V2J | review-required |
| N018 | automatic acquisition is the default post-Anchor path | V2I/V2J | accepted-scope |
| N019 | Expert Recovery is secondary and unavailable while the loop runs | V2J | accepted-scope / review-required |
| N020 | Add Observation retains User-added View with authoritative RGB and Stable Mask rules | V2J | accepted-scope / review-required |
| N021 | Continue Acquisition starts a fresh bounded attempt from exact current artifacts | V2G/V2I/V2J | accepted-scope / review-required |
| N022 | a new recovery observation stales Candidate and never patches Native Selection | V2H/V2J | accepted-scope / review-required |
| N023 | User Confirmed/manual observations retain reliability exemption | V2D/V2J | accepted-scope / review-required |
| N024 | persistent planning controls remain retired | V2J | accepted-scope |
| N025 | calibration, policy freeze, production identity promotion, cutover, and qualification have explicit owners | unassigned | blocker |

## Coverage result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 25
mapped new requirements             = 24
unassigned release requirement      = N025
agent-ready tickets                 = 0
next review item                    = V2A
```

No implementation closure may be claimed while N025 is unassigned or while the relevant stages remain `review-required`.
