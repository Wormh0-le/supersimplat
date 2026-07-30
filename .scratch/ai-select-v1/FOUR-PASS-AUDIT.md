# Six-Pass Bidirectional Traceability Audit — v2.6

The filename is retained for compatibility. v2.6 adds Amendment 004 and DG-24; replaces mandatory ordered tracking with sparse 3D-guided per-Key-View Mask acquisition; makes tracker/hybrid routes optional and ADR-gated; and adds an explicit artifact-dependency pass.

## Pass 1 — Ticket graph / dependency audit

- Ticket count: 27 total — 22 numbered + 04A + 04B + 07A + 07B + 08A
- Missing blocker references: 0
- Ticket cycle detected: False
- Structural initial frontier: [01]
- Topological order length: 27/27
- Result: **PASS**

One valid topological order:

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

v2.6 dependency corrections:

- 04B remains the next implementation ticket.
- 07A follows 04B/05/07 and owns conservative object-level Anchor acquisition.
- 07B follows 07A and owns fitted-image palette interaction only.
- 08 follows 07B and owns non-ownership bootstrap plus sparse Key-View plan segments.
- 08A follows 08 and owns acquisition-route spike, enhanced per-view SAM, and optional augmentation decision.
- 09 follows 08A so Gallery contracts can present actual acquisition backend/status.
- 12 depends on 08A/09 and owns per-view refresh plus optional propagation capability.
- 14 consumes only Included Stable Masks and defines reference P/N/V before 10/13.
- 20 productionizes same-decision P/N/V only after 14/19.

## Pass 2 — Artifact producer / consumer graph

Checked artifact edges:

```text
07A Anchor Stable Mask
→ 08 TargetBootstrapArtifact
→ 08 SparseKeyViewPlanSegment
→ 08A per-view Mask acquisition attempt / Stable Mask
→ 09 Review + Participation
→ 12 refresh / dirty state
→ 14 per-view P/N/V
→ 15 current Candidate
```

Findings:

- Ticket 08 no longer consumes a tracker transition envelope.
- Ticket 08A spike consumes sparse Key Views but does not feed a mandatory prerequisite back into Ticket 08.
- Tracker transition/Bridge artifacts exist only after an optional later ADR.
- Generate More appends immutable plan segments and does not rotate prior segment identity.
- Confirmed correction does not automatically create reference memory.
- TargetBootstrapArtifact seeds but does not hard-bound Evidence Working Set.
- Artifact cycle detected: False
- Result: **PASS**

## Pass 3 — Final Spec / Amendments / DGs → tickets

A curated catalog of **164** requirements is mapped in `TRACEABILITY.md`.

Checks:

- Invalid ticket references: 0
- Unmapped DG-20 requirements: 0
- Unmapped DG-21 requirements: 0
- Unmapped DG-22 requirements: 0
- Unmapped DG-23 historical requirements not superseded: 0
- Unmapped DG-24 requirements: 0
- Unmapped Amendment 001 requirements: 0
- Unmapped Amendment 002 requirements: 0
- Unmapped Amendment 003 requirements not superseded: 0
- Unmapped Amendment 004 requirements: 0
- Result: **PASS**

New v2.6 requirement groups:

- sparse Key Views are mandatory; dense tracking sequence is not;
- Generate More uses append-only immutable plan segments;
- enhanced 3D-guided independent SAM is the default production candidate;
- route A/B/C/D acquisition spike uses downstream Gaussian metrics;
- tracker/hybrid requires a separate ADR;
- Bridge/transition/reference/repropagate are capability-gated;
- correction Confirm is per-view by default;
- bootstrap support is not a hard Evidence Working Set upper bound;
- optional tracker failure cannot disable valid independent per-view acquisition.

## Pass 4 — tickets → specification / reverse scope audit

- Orphan tickets: []
- 04A maps to Amendment 002 / DG-21.
- 04B maps to capability-gated visual Prompts.
- 07A maps to Amendments 002–003 and DG-21/23.
- 07B maps to DG-22.
- 08 maps to Amendment 004 / DG-24 bootstrap and sparse planner requirements.
- 08A maps to Amendment 004 / DG-24 acquisition route requirements.
- 09/12 map to backend-agnostic review/refresh and optional capability semantics.
- 14/20 remain the only formal ownership stages.
- Result: **PASS**

## Pass 5 — outcome → prerequisites audit

```text
Native operation
← current Candidate
← readiness + version-bound P/N/V
← Included Stable View Annotations
← per-view multi-view Mask acquisition
← sparse valid Key Views + bootstrap
← confirmed object-level Anchor
← authoritative RGB / CameraBinding / Scene identity
```

Checks:

- No final outcome depends on tracker presence.
- No final outcome depends on complete per-pixel Contributor publication.
- No early support artifact can directly become Candidate.
- No Mask/backend confidence authorizes Lift.
- Later Included Views can expand Evidence search beyond Anchor bootstrap.
- Result: **PASS**

## Pass 6 — walkthrough / failure audit

- Typical walkthroughs: 18
- Error/degradation walkthroughs: 18
- D-double-prime sparse Key-View flow: covered
- Route A/B/C/D decision: covered
- Per-view correction without propagation: covered
- Optional reference/repropagation: capability-gated and covered
- Generate More segment preservation: covered
- Per-view acquisition failure retains RGB/prior Stable: covered
- Bootstrap unavailable and Working Set expansion: covered
- Result: **PASS**

## Residual implementation unknowns

These are intentionally delegated to Ticket 08A spike/ADR rather than guessed in planning:

- exact per-view Prompt synthesis recipe;
- whether Mask input materially improves route B;
- selected inference resolution / View budget;
- whether tracker/hybrid gives sufficient downstream benefit;
- optional transition/resource envelope if selected;
- exact backend scheduling and VRAM constraints.

## Audit conclusion

v2.6 is internally consistent for D-double-prime:

```text
reliable Anchor
→ sparse Key Views
→ 3D-guided independent per-view Masks
→ optional tracking only if justified
→ Included Stable Masks
→ final P/N/V ownership
```

Ticket 04B remains the next implementation gate. Ticket 08/08A must follow Amendment 004 / DG-24 rather than the superseded mandatory-tracking clauses of Amendment 003 / DG-23.
