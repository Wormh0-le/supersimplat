# Eight-Pass Bidirectional Traceability Audit — v2.9

The filename is retained for compatibility. v2.9 keeps Final Spec v1.2 as the sole current product specification, adds a current Ticket mapping authority, closes acquisition diagnostics/Decision identity gaps, separates Decision `unavailable` from technical failure, and makes legacy Generated View acquisition migration explicit.

## Pass 1 — Ticket graph / dependency audit

- Ticket count: 28 total — 22 numbered + 04A + 04B + 07A + 07B + 08A + 08B
- Missing blocker references: 0
- Ticket cycle detected: False
- Structural initial frontier: [01]
- Topological order length: 28/28
- Result: **PASS**

One valid topological order:

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 08B → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

Structural parallelism:

```text
05 → 04A
05 → 06

07A → 07B
07A → 08

14 → 10
14 → 13
```

Findings:

- 07B does not block 08.
- 07B blocks complete user correction UX and Ticket 21 release validation through Tickets 11/21.
- 08A is contract foundation only.
- 08B is the production acquisition and legacy-contract migration owner.
- 09 depends on 08B, not merely an abstract contract.
- Result: **PASS**

## Pass 2 — Artifact producer / consumer graph

Current artifact chain:

```text
07A Anchor Stable Mask
→ 08 VisibleTargetSupportArtifact
→ 08 TargetBootstrapArtifact
→ 08 SparseKeyViewPlanSegment
→ 08B KeyViewPromptArtifact
→ 08B PerViewMaskAcquisitionResult
    ├── KeyViewMaskProposalSet
    └── one attempt-level backendDiagnostics authority
→ 08B KeyViewMaskDecision bound to exact ProposalSet digest + attempt
→ 07/08B ViewAssessmentResult for selected only
→ 08B MaskPublication result / Stable Mask
→ 09/12 Review + Participation + dirty state
→ 14 per-view P/N/V
→ 15 current Candidate
```

Contract-only edges:

```text
08A MaskAcquisitionBackendDescriptor
→ MaskAcquisitionBackend bundle
→ MaskAcquisitionBackendRegistry
→ MultiViewMaskAcquisitionProvider
→ optional SequenceMaskAcquisitionExtension
```

Findings:

- `VisibleTargetSupportArtifact` supplies real replayable 3D samples.
- Support and bootstrap are non-ownership artifacts.
- Provider output ends at result envelope + ProposalSet.
- Attempt-level backend diagnostics are not duplicated in ProposalSet.
- Decision, Assessment and publication are explicit later artifacts/actions.
- Decision binds exact ProposalSet digest and acquisition attempt.
- Ambiguous creates no Stable Mask.
- Unavailable creates no Stable Mask but remains a completed acquisition Decision.
- Route-A fallback creates a distinct attempt and reuses the same downstream layers.
- Sequence schemas create no current artifact dependency.
- Artifact cycle detected: False
- Result: **PASS**

## Pass 3 — Final Spec v1.2 / accepted ADRs / current Ticket mapping

The single `TRACEABILITY.md` maps **104** consolidated current requirements.

Checks:

- Invalid ticket references: 0
- Unmapped Final Spec v1.2 requirements: 0
- Historical Amendment overlay required: no
- Current mapping authority: `CURRENT-TICKET-SPEC-MAPPING.md`
- Ticket IDs missing from current mapping: 0
- Active ticket requires historical Amendment: 0
- Accepted ADR references: ADR 0013 and ADR 0014
- Missing or invalid accepted ADR references: 0
- ADR 0014 indexed and subordinate to Final Spec v1.2: yes
- Route-B comparison gate retained: no
- Mandatory tracker/Bridge/reference implementation retained: no
- Result: **PASS**

Mapping rule:

```text
Final Spec v1.2
→ CURRENT-TICKET-SPEC-MAPPING.md
→ ticket acceptance/failure/validation criteria
```

Ticket-local v1.1/Amendment references retained from earlier versions are historical provenance only and have no current normative force.

## Pass 4 — tickets → Final Spec v1.2 / reverse scope audit

- Orphan tickets: []
- 04A maps to Prompt/proposal foundation.
- 04B maps to truthful visual-Prompt adapter capabilities.
- 07A maps to conservative object-level Anchor acquisition.
- 07B maps to fitted-image no-blind-spot interaction.
- 08 maps to support/bootstrap/sparse planner.
- 08A maps to acquisition artifacts, result envelope, exact Decision identity and registry.
- 08B maps to route-B production, fallback and legacy acquisition migration.
- 09/11/12 map to inspection, user Views, refresh and state lifecycle.
- 14/20 remain the only formal ownership stages.
- 15–18 map to correction, Native application, Restart/Suspended lifecycle.
- 19–22 map to rendering/Evidence production hardening and legacy contraction.
- Result: **PASS**

Scope-leak checks:

- Ticket 08 does not run SAM or publish Masks.
- Ticket 08A does not implement model inference or tracker behavior.
- Ticket 08B does not generate cameras or compute P/N/V.
- Ticket 09 does not mutate acquisition/reference state.
- Ticket 12 does not automatically Re-Lift.
- Ticket 14 does not consume acquisition confidence or unavailable status as Evidence.
- Ticket 21 introduces no new product route.

## Pass 5 — outcome → prerequisites audit

```text
Native operation
← current Candidate
← readiness + version-bound P/N/V
← Included Stable View Annotations
← publication from selected+assessed per-view Masks
← exact ProposalSet-bound Decision
← PerViewMaskAcquisitionResult
← route-B inference over KeyViewPromptArtifact
← visible support + bootstrap + sparse valid Key Views
← confirmed object-level Anchor
← authoritative RGB / CameraBinding / scene identity
```

Interaction prerequisite:

```text
complete Anchor/Generated/User-added correction UX
← Ticket 07B
```

Checks:

- No final outcome depends on route comparison.
- No final outcome depends on tracker presence.
- No final outcome depends on complete Contributor publication.
- No support/bootstrap/Prompt/proposal/backend artifact can directly become Candidate.
- No ambiguous or unavailable result can silently become Stable.
- No semantic Review/unavailable outcome can be hidden by automatic route-A fallback.
- Later Included Views can expand Evidence Working Set beyond Anchor support/bootstrap.
- Result: **PASS**

## Pass 6 — walkthrough / failure audit

- Typical/architecture walkthroughs: 22
- Error/degradation walkthroughs: 22
- 07B/08 parallel execution: covered
- Visible support extraction and invalid-support recovery: covered
- Sparse planning and Generate More preservation: covered
- 08A contract-only boundary: covered
- Route-B layered execution: covered
- Key-View ambiguity without Stable publication: covered
- Decision unavailable without technical failure/fallback: covered
- B2 technical fallback: covered
- semantic Review without fallback: covered
- User Confirmed authority: covered
- Prompt-only regeneration versus SAM Retry: covered
- per-view correction without propagation: covered
- formal P/N/V ownership boundary: covered
- legacy generated-view contract migration: covered
- future C/D extension readiness: covered
- Result: **PASS**

## Pass 7 — protocol identity and diagnostics authority

Checks:

- `PerViewMaskAcquisitionResult` is explicit: PASS
- ProposalSet contains candidate artifacts/candidate-local metrics only: PASS
- Attempt-level `backendDiagnostics` has one authority on result envelope: PASS
- `KeyViewMaskDecision` binds `proposalSetArtifactDigest`: PASS
- Decision binds target/context/View/acquisition attempt: PASS
- Cross-attempt proposal-ID collision is rejected: PASS
- Publication command validates exact ProposalSet/Decision identity: PASS
- Empty successful ProposalSet can become Decision unavailable: PASS
- Result: **PASS**

Prohibited structures:

```text
ProposalSet.backendDiagnostics + Result.backendDiagnostics dual authority
Decision with proposal IDs but no ProposalSet digest/attempt binding
provider-returned Decision or ViewAssessmentResult
```

## Pass 8 — legacy acquisition migration

Current legacy seam under migration:

```text
GeneratedViewMaskRequest
→ produceGeneratedViewMask
→ GeneratedViewMaskResponse {
     maskSource: 'propagated'
     maskPropagation
     mask
     assessment
   }
→ controller direct Stable/Participation publication
```

Required migration assertions:

- provider-returned Assessment is not current: PASS
- fixed generic `maskSource: 'propagated'` is not current: PASS
- `GeneratedViewMaskPropagation` is not the generic diagnostics authority: PASS
- legacy `generated-view-mask/v1` payload/cache fails current validation: PASS
- controller direct provider-response publication is an explicit 08B removal target: PASS
- route-A compatibility uses a new adapter/result/ProposalSet attempt: PASS
- User Confirmed Stable authority survives migration: PASS
- Result: **PASS**

## Critical phrase and contradiction audit

Required current statements:

```text
Final Spec v1.2 is the only current specification
CURRENT-TICKET-SPEC-MAPPING.md is the current Ticket mapping authority
ADR 0014 is indexed and subordinate to Final Spec v1.2
VisibleTargetSupportArtifact precedes TargetBootstrapArtifact
07B and 08 are parallel after 07A
08A is contracts/registry only
08B implements production route B and legacy acquisition migration
provider returns PerViewMaskAcquisitionResult + ProposalSet only
backendDiagnostics has one result-envelope authority
Decision binds exact ProposalSet digest + attempt
ambiguous publishes no arbitrary Stable Mask
unavailable is not technical failure and does not auto-fallback
route-A fallback is technical/capability-only
route-A Auto Good uses same or stricter gates
legacy generated-view-mask/v1 cannot validate as current
support/bootstrap/Prompt/acquisition are not P/N/V
```

Prohibited active statements:

```text
07B blocks Ticket 08
Ticket 08A directly implements production SAM
TargetBootstrapArtifact precedes VisibleTargetSupportArtifact
provider returns final Mask + ViewAssessmentResult
ProposalSet and result both own backendDiagnostics
Decision omits exact ProposalSet identity
highest model score is authoritative
ambiguous or unavailable automatically falls back to route A
unavailable equals backend/OOM/protocol failure
support sample Gaussian ID implies ownership
route B exposes fake sequence/reference methods
v1.1 Amendment chain is the current implementation specification
legacy maskSource='propagated' is generic route-B provenance
accepted current ADR exists outside the specification index or manifest
```

Audit result: **PASS**

## Residual implementation/calibration unknowns

These are bounded implementation questions, not architecture gates:

- support sample count, spatial sampling and encoding;
- whether stable Gaussian provenance is needed in the first support version;
- exact Point/Box/ROI/local-negative/Mask-input synthesis recipe;
- inference resolution and sparse View budget;
- proposal near-duplicate clustering metric/threshold;
- contamination and Review thresholds;
- route-A stricter fallback thresholds;
- per-view scheduler concurrency and peak VRAM envelope;
- Evidence Working Set expansion thresholds.

Future non-blocking research:

- whether route C or D gives enough downstream gain to justify lifecycle complexity;
- sequence transition/resource envelope;
- reference-memory and propagation atomicity policy.

## Audit conclusion

v2.9 is internally consistent:

```text
reliable Anchor
→ replayable visible support
→ lightweight bootstrap
→ sparse Key Views
→ explicit Prompt artifact
→ result envelope + ProposalSet
→ exact ProposalSet-bound Decision
→ selected-only Assessment
→ atomic Stable publication
→ Included Stable Masks
→ final P/N/V ownership
```

Ticket 04B remains the next implementation gate. Final Spec v1.2 and `CURRENT-TICKET-SPEC-MAPPING.md` govern current implementation; ADR 0014 and DG-26 provide subordinate rationale.
