# Final Spec v2.0 Traceability Matrix

Status: **current planning traceability — implementation coverage pending**  
Updated: 2026-08-23

This matrix maps the current normative v2.0 requirements to planned ownership. It does not claim implementation. The implemented v1.3 coverage record is preserved at `history/v1/TRACEABILITY-V1.md`.

## Carried-over requirements

| ID | Requirement | Implementation baseline | V2 regression owner |
|---|---|---|---|
| C001 | One object/Active Splat per Current Target Context | implemented v1.3 | all V2 tickets |
| C002 | authoritative gsplat RGB and exact CameraBinding | implemented v1.3 | V2A, V2F, V2I |
| C003 | official SAM 3 Image single-result Mask workflow | implemented v1.3 | V2I, V2J |
| C004 | Stable Mask, Participation and User Confirmed authority remain distinct | implemented v1.3 | V2D, V2I, V2J |
| C005 | TargetGeometryHint remains localization/Prompt context, not ownership | implemented v1.3 | V2B, V2F |
| C006 | raw per-view Evidence is exact, immutable and identity-bound | implemented v1.3 | V2A, V2E |
| C007 | missing/unusable observation is unobserved, not negative | implemented v1.3 | V2A, V2D, V2E |
| C008 | Candidate replacement is atomic and never self-applies | implemented v1.3 | V2H |
| C009 | Native Selection changes only via explicit Set/Add/Remove/Intersect | implemented v1.3 | V2H, V2J |
| C010 | stale results fail closed and failures preserve valid artifacts | implemented v1.3 | V2I |
| C011 | production behavior is bound to exact runtime/policy identity | implemented v1.3 | V2A–V2I |
| C012 | complete Contributor remains reference/debug only | implemented v1.3 | V2A, V2C |

## New v2.0 requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N001 | Anchor Direct Evidence can seed a precision-first Conservative Seed Support | V2A, V2B | review-required |
| N002 | Seed is Companion-local, diagnosable, incomplete, and not ownership/Candidate | V2B | review-required |
| N003 | Connectivity preserves qualified satellites and records filtered reasons | V2B | review-required |
| N004 | Seed unavailable does not silently fail or become a hard Evidence boundary | V2B | review-required |
| N005 | Core Target denominator starts from reviewed seed/fallback policy and never shrinks silently | V2B, V2E | review-required |
| N006 | shadow evaluation can compare seed-based and broad coverage | V2B | review-required |
| N007 | Direct Evidence gains a same-decision depth readout with explicit ABI semantics | V2A | review-required |
| N008 | Negative Mass classification has a versioned schema and migration | V2A | review-required |
| N009 | depth readout/classification does not create a second visibility authority | V2A | review-required |
| N010 | Provisional consensus is defined, initialized, revisioned and disposable | V2C | review-required |
| N011 | consensus soft-mask readout is Companion-local and non-authoritative | V2C | review-required |
| N012 | consensus/reliability recurrence is bounded and replayable | V2C, V2D, V2E | review-required |
| N013 | Observation Reliability is view-level and weights semantic P/N only | V2D, V2E | review-required |
| N014 | raw V remains realized observation rather than Mask trust | V2D, V2E | review-required |
| N015 | reliability never mutates Stable Mask, Participation, or Native Selection | V2D | review-required |
| N016 | anti-self-confirmation guardrails are structurally enforced and calibrated | V2D | review-required |
| N017 | weighted incremental aggregation equals full recomputation | V2E | review-required |
| N018 | realized Coverage/Diversity, prospective View Utility, and Readiness stay separate | V2F, V2G | review-required |
| N019 | first post-Anchor View follows a deterministic reviewed rule | V2F | review-required |
| N020 | subsequent Views use a deterministic, versioned utility policy | V2F | review-required |
| N021 | utility prediction has an explicit probe/approximation and cost contract | V2F | review-required |
| N022 | acquisition is bounded by reviewed View and deterministic cost budgets | V2G | review-required |
| N023 | View outcomes, replacement, circuit-breaker and budget accounting are explicit | V2G | review-required |
| N024 | every terminal emits a structured stop reason | V2G | review-required |
| N025 | Candidate publication is defined for every Readiness × StopReason combination | V2H | review-required |
| N026 | ready-and-low-marginal-gain may auto-publish atomically but never auto-apply | V2H | review-required |
| N027 | Limited publication requires explicit, legible user consent | V2H, V2J | review-required |
| N028 | Browser drives the loop over existing validated request/response transport | V2I | review-required |
| N029 | loop, iteration and endpoint attempts have non-conflicting identities | V2I | review-required |
| N030 | replay is deterministic despite operational timing variation | V2G, V2I | review-required |
| N031 | Cancel revokes publication authority immediately and preserves completed artifacts | V2I, V2J | review-required |
| N032 | suspend/resume, stale dependency and late-result behavior are explicit | V2I | review-required |
| N033 | UI presents phase, readiness and terminal reason without a diagnostics dashboard | V2J | review-required |
| N034 | recovery remains possible when automatic acquisition cannot reach a useful terminal | V2J | review-required |
| N035 | User-added View removal, if retained, occurs only at an explicit reviewed cutover | V2J | review-required |
| N036 | calibration, policy freeze, production identity promotion and release qualification have explicit owners | graph review | unmapped-blocker |

## Coverage result

```text
current v2 requirements: 48
carried-over implemented requirements: 12
new requirements implemented: 0
new requirements mapped to V2A–V2J: 35
unmapped release requirement: N036
agent-ready tickets: 0
current review frontier: V2A, V2C
```

The matrix does not pass an implementation-closure audit until every new requirement is implemented, validated, and linked to immutable evidence.
