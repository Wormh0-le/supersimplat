# Six-Pass Bidirectional Traceability Audit — v2.7

The filename is retained for compatibility. v2.7 adds Amendment 005 and DG-25; selects route B for immediate implementation; removes A/B/C/D comparison and acquisition-route ADR as Ticket 08A closure gates; and requires extension-ready sequence/reference contracts for future C/D experiments.

## Pass 1 — Ticket graph / dependency audit

- Ticket count: 27 total — 22 numbered + 04A + 04B + 07A + 07B + 08A
- Missing blocker references: 0
- Ticket cycle detected: False
- Structural initial frontier: [01]
- Topological order length: 27/27
- Result: **PASS**

One valid topological order:

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

v2.7 dependency corrections:

- 04B remains the next implementation ticket.
- 07A follows 04B/05/07 and owns conservative object-level Anchor acquisition.
- 07B follows 07A and owns fitted-image palette interaction only.
- 08 follows 07B and owns non-ownership bootstrap plus sparse Key-View plan segments.
- 08A follows 08 and directly owns route-B per-view SAM plus acquisition extension seams.
- 08A no longer contains a route-selection spike or pre-route-B ADR gate.
- 09 follows 08A so Gallery contracts consume the implemented generic acquisition status.
- 12 depends on 08A/09 and owns per-view refresh plus optional future propagation capability.
- 14 consumes only Included Stable Masks and defines reference P/N/V before 10/13.
- 20 productionizes same-decision P/N/V only after 14/19.

## Pass 2 — Artifact producer / consumer graph

Checked artifact edges:

```text
07A Anchor Stable Mask
→ 08 TargetBootstrapArtifact
→ 08 SparseKeyViewPlanSegment
→ 08A route-B PerViewMaskAcquisitionRequest/Result
→ 08A per-view Stable Mask / Review / Failed
→ 09 Review + Participation
→ 12 refresh / dirty state
→ 14 per-view P/N/V
→ 15 current Candidate
```

Extension-only edges:

```text
future route C/D backend
→ SequenceMaskAcquisitionExtension
→ common acquisition result envelope
→ existing Mask validation / publication / assessment
```

Findings:

- Ticket 08 consumes no tracker transition envelope.
- Ticket 08A route B consumes sparse Key Views and feeds no prerequisite back into Ticket 08.
- `acquireView` is the mandatory base path.
- sequence/reference methods are optional capabilities and do not create current artifact dependencies.
- Route B advertises no sequence/reference capability and cannot create fake sequence artifacts.
- Generate More appends immutable plan segments and does not rotate prior segment identity.
- Confirmed correction does not automatically create reference memory.
- TargetBootstrapArtifact seeds but does not hard-bound Evidence Working Set.
- Artifact cycle detected: False
- Result: **PASS**

## Pass 3 — Final Spec / Amendments / DGs → tickets

A curated catalog of **166** requirements is mapped by `TRACEABILITY.md` plus the `TRACEABILITY-v2.7.md` overlay.

Checks:

- Invalid ticket references: 0
- Unmapped DG-20 requirements: 0
- Unmapped DG-21 requirements: 0
- Unmapped DG-22 requirements: 0
- Unmapped DG-23 historical requirements not superseded: 0
- Unmapped DG-24 requirements not superseded: 0
- Unmapped DG-25 requirements: 0
- Unmapped Amendment 001 requirements: 0
- Unmapped Amendment 002 requirements: 0
- Unmapped Amendment 003 requirements not superseded: 0
- Unmapped Amendment 004 requirements not superseded: 0
- Unmapped Amendment 005 requirements: 0
- Result: **PASS**

New v2.7 requirement groups:

- route B is selected and implemented directly;
- no A/B/C/D comparison or route-selection ADR blocks Ticket 08A;
- route A remains regression baseline/fallback;
- backend-neutral capabilities and `acquireView` are mandatory;
- sequence/reference extension contracts exist for future C/D experiments;
- unsupported extension methods fail closed without state mutation;
- C/D production still requires a future experiment-backed ADR;
- correction Confirm remains per-view by default;
- bootstrap support is not a hard Evidence Working Set upper bound.

## Pass 4 — tickets → specification / reverse scope audit

- Orphan tickets: []
- 04A maps to Amendment 002 / DG-21.
- 04B maps to capability-gated visual Prompts.
- 07A maps to Amendments 002–003 and DG-21/23.
- 07B maps to DG-22.
- 08 maps to Amendment 004 / DG-24 bootstrap and sparse planner requirements.
- 08A maps to Amendments 004–005 / DG-24–25 route-B and extension-seam requirements.
- 09/12 map to backend-agnostic review/refresh and optional capability semantics.
- 14/20 remain the only formal ownership stages.
- Result: **PASS**

## Pass 5 — outcome → prerequisites audit

```text
Native operation
← current Candidate
← readiness + version-bound P/N/V
← Included Stable View Annotations
← route-B per-view Mask acquisition
← sparse valid Key Views + bootstrap
← confirmed object-level Anchor
← authoritative RGB / CameraBinding / Scene identity
```

Checks:

- No final outcome depends on route comparison.
- No final outcome depends on tracker presence.
- No final outcome depends on complete per-pixel Contributor publication.
- No early support artifact can directly become Candidate.
- No Mask/backend confidence authorizes Lift.
- Later Included Views can expand Evidence search beyond Anchor bootstrap.
- Result: **PASS**

## Pass 6 — walkthrough / failure audit

- Typical walkthroughs: 18
- Error/degradation walkthroughs: 18
- D-double-prime route-B sparse Key-View flow: covered
- Route-B capability and `acquireView`: covered
- Future C/D sequence/reference extension readiness: covered
- Per-view correction without propagation: covered
- Optional future reference/repropagation: capability-gated and covered
- Generate More segment preservation: covered
- Per-view acquisition failure retains RGB/prior Stable: covered
- Unsupported sequence/reference method has no state mutation: covered
- Bootstrap unavailable and Working Set expansion: covered
- Result: **PASS**

## Residual implementation unknowns

These are implementation/calibration questions inside the selected route-B path, not route-selection gates:

- exact 3D-guided Prompt synthesis recipe;
- whether Mask input materially improves route B when supported;
- inference resolution and sparse View budget;
- per-view scheduler concurrency and VRAM envelope;
- fallback threshold from route B to route A;
- exact contamination and Review thresholds.

Future, non-blocking research questions:

- whether route C or D produces enough downstream benefit to justify added lifecycle complexity;
- optional transition/resource envelope if a later ADR selects C/D;
- optional propagation atomicity and reference-memory policy.

## Audit conclusion

v2.7 is internally consistent:

```text
reliable Anchor
→ sparse Key Views
→ selected route-B 3D-guided independent per-view Masks
→ Included Stable Masks
→ final P/N/V ownership
```

The code contract is extension-ready for future C/D experiments without making them current dependencies.

Ticket 04B remains the next implementation gate. Ticket 08/08A must follow Amendment 005 / DG-25 where they supersede the route-comparison clauses of Amendment 004 / DG-24.
