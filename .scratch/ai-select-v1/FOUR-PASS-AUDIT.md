# Six-Pass Bidirectional Traceability Audit — v2.8

The filename is retained for compatibility. v2.8 adopts Final Spec v1.2 as the only current specification, adds `VisibleTargetSupportArtifact`, splits 08A/08B, parallelizes 07B and 08, separates acquisition/decision/assessment/publication, locks B2 technical-only route-A fallback, and indexes accepted ADR 0014 as subordinate architectural rationale.

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

- 07B no longer blocks 08.
- 07B blocks complete user correction UX and Ticket 21 release validation through Tickets 11/21.
- 08A is contract foundation only.
- 08B is the production acquisition owner.
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
→ 08B KeyViewMaskProposalSet
→ 08B KeyViewMaskDecision
→ 07/08B ViewAssessmentResult
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

Future-only edges:

```text
future C/D backend
→ sequence extension implementation
→ common ProposalSet/Decision/Assessment/Publication path
```

Findings:

- `VisibleTargetSupportArtifact` supplies real replayable 3D samples; bootstrap is no longer an insufficient center/extent-only source for projected Point prompts.
- Support and bootstrap are non-ownership artifacts.
- 08B consumes Prompt artifacts; providers do not reinterpret raw support.
- Provider output ends at ProposalSet.
- Decision, Assessment and publication are explicit later artifacts/actions.
- Ambiguous creates no Stable Mask.
- Route-A fallback creates a distinct attempt and reuses the same downstream layers.
- Sequence schemas create no current artifact dependency.
- Generate More remains append-only.
- Artifact cycle detected: False
- Result: **PASS**

## Pass 3 — Final Spec v1.2 / accepted ADRs → tickets

The single `TRACEABILITY.md` maps **100** consolidated current requirements.

Checks:

- Invalid ticket references: 0
- Unmapped Final Spec v1.2 requirements: 0
- Historical Amendment overlay required: no
- Unmapped DG-26 decisions: 0
- Accepted ADR references: ADR 0013 and ADR 0014
- Missing or invalid accepted ADR references: 0
- ADR 0014 indexed in `docs/specs/README.md`: yes
- ADR 0014 registered in `manifest.json`: yes
- ADR 0014 explicitly subordinate to Final Spec v1.2: yes
- Route-B comparison gate retained: no
- Mandatory tracker/Bridge/reference implementation retained: no
- Result: **PASS**

Key mapped groups:

- product scope and Native Selection lifecycle;
- authoritative RGB and identity fail-closed behavior;
- Anchor Prompt/proposal/ambiguity/confirmation;
- Floating Palette interaction;
- Visible Target Support and bootstrap;
- sparse planner and append-only segments;
- acquisition contracts and backend registry;
- independent Prompt synthesis;
- ProposalSet/Decision/Assessment/publication separation;
- B2 technical-only fallback;
- Gallery/user View/dirty lifecycle;
- formal P/N/V ownership;
- future C/D ADR boundary;
- production failure/calibration hardening.

## Pass 4 — tickets → Final Spec v1.2 / reverse scope audit

- Orphan tickets: []
- 04A maps to Prompt/proposal foundation.
- 04B maps to truthful visual-Prompt adapter capabilities.
- 07A maps to conservative object-level Anchor acquisition.
- 07B maps to fitted-image no-blind-spot interaction.
- 08 maps to support/bootstrap/sparse planner.
- 08A maps to acquisition artifacts and registry.
- 08B maps to route-B production execution and fallback.
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
- Ticket 14 does not consume acquisition confidence as Evidence.
- Ticket 21 introduces no new product route.

## Pass 5 — outcome → prerequisites audit

```text
Native operation
← current Candidate
← readiness + version-bound P/N/V
← Included Stable View Annotations
← publication from selected+assessed per-view Masks
← ProposalSet + conservative KeyViewMaskDecision
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
- No ambiguous per-view result can silently become Stable.
- No semantic Review can be hidden by automatic route-A fallback.
- Later Included Views can expand Evidence Working Set beyond Anchor support/bootstrap.
- Result: **PASS**

## Pass 6 — walkthrough / failure audit

- Typical/architecture walkthroughs: 20
- Error/degradation walkthroughs: 20
- 07B/08 parallel execution: covered
- Visible support extraction and invalid-support recovery: covered
- Sparse planning and Generate More preservation: covered
- 08A contract-only boundary: covered
- Route-B layered execution: covered
- Key-View ambiguity without Stable publication: covered
- B2 technical fallback: covered
- semantic Review without fallback: covered
- User Confirmed authority: covered
- Prompt-only regeneration versus SAM Retry: covered
- per-view correction without propagation: covered
- formal P/N/V ownership boundary: covered
- future C/D extension readiness: covered
- result: **PASS**

## Critical phrase and contradiction audit

Required current statements:

```text
Final Spec v1.2 is the only current specification
ADR 0014 is indexed and subordinate to Final Spec v1.2
VisibleTargetSupportArtifact precedes TargetBootstrapArtifact
07B and 08 are parallel after 07A
08A is contracts/registry only
08B implements production route B
provider returns ProposalSet only
ambiguous publishes no arbitrary Stable Mask
route-A fallback is technical/capability-only
route-A Auto Good uses same or stricter gates
support/bootstrap/Prompt/acquisition are not P/N/V
```

Prohibited active statements:

```text
07B blocks Ticket 08
Ticket 08A directly implements production SAM
TargetBootstrapArtifact precedes VisibleTargetSupportArtifact
provider returns final Mask + ViewAssessmentResult
highest model score is authoritative
ambiguous automatically falls back to route A
support sample Gaussian ID implies ownership
route B exposes fake sequence/reference methods
v1.1 Amendment chain is the current implementation specification
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

v2.8 is internally consistent:

```text
reliable Anchor
→ replayable visible support
→ lightweight bootstrap
→ sparse Key Views
→ explicit Prompt artifact
→ route-B ProposalSet
→ conservative Decision
→ independent Assessment
→ atomic Stable publication
→ Included Stable Masks
→ final P/N/V ownership
```

Ticket 04B remains the next implementation gate. Final Spec v1.2 governs current implementation; ADR 0014 and DG-26 provide subordinate rationale where historical documents conflict.
