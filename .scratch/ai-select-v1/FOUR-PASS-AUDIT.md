# Five-Pass Bidirectional Traceability Audit — v2.5

The filename is retained for compatibility. v2.5 adds Amendment 003, DG-23, and Ticket 08A; narrows Ticket 07A to conservative object-level Anchor acquisition; changes Ticket 08 to non-ownership 2.5D Key/Bridge sequence planning; and inserts object-level tracking before Gallery/repropagate/final Lift.

## Pass 1 — Graph / dependency audit

- Ticket count: 27 total — 22 numbered + 04A + 04B + 07A + 07B + 08A
- Missing blocker references: 0
- Cycle detected: False
- Structural initial frontier: [01]
- Topological order length: 27/27
- Result: **PASS**

One valid topological order:

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

v2.5 dependency corrections:

- 04B remains the next implementation ticket.
- 07A follows 04B/05/07 and owns conservative object-level Anchor acquisition.
- 07B follows 07A and owns fitted-image palette interaction only.
- 08 follows 07B and owns non-ownership 2.5D bootstrap plus ordered Key/Bridge planning.
- 08A follows 08 and owns tracker spike, implementation ADR gate, production tracking, correction memory, and explicit baseline fallback.
- 09 follows 08A so Gallery contracts can present real tracking roles/status.
- 12 depends on 08A/09 and owns explicit tracker repropagate plus dirty/stale lifecycle.
- 14 still consumes only Included Stable Masks and defines reference P/N/V before 10/13.
- 20 still productionizes same-decision P/N/V only after 14/19.

## Pass 2 — Final Spec / Amendments / DGs → tickets

A curated catalog of **159** requirements is mapped in `TRACEABILITY.md`.

Checks:

- Invalid ticket references: 0
- Unmapped DG-20 requirements: 0
- Unmapped DG-21 requirements: 0
- Unmapped DG-22 requirements: 0
- Unmapped DG-23 requirements: 0
- Unmapped Amendment 001 requirements: 0
- Unmapped Amendment 002 requirements: 0
- Unmapped Amendment 003 requirements: 0
- Result: **PASS**

New v2.5 requirement groups:

- one object instance as v1 target scope;
- no mandatory whole-image inventory or arbitrary part discovery;
- confirmed Anchor Stable Mask as identity seed, not ownership;
- 2.5D TargetBootstrapArtifact limited to localization/planning/ROI;
- camera validity, observation gain, and transition cost as separate planner decisions;
- ordered Key/Bridge sequence;
- tracking membership separate from Participation;
- Bridge Views default Excluded;
- tracker backend spike and later ADR before production closure;
- current single-frame SAM retained as explicit baseline/fallback;
- confirmed correction references and explicit tracker repropagate;
- tracker confidence/bootstrap support excluded from P/N/V semantics.

Existing requirements remain:

- exact RGB-bound PromptState;
- Prompt/Edit separation and separate histories;
- truthful visual-prompt capabilities;
- deterministic bounded proposals;
- conservative ambiguity and Confirm-only Stable publication;
- fitted-image no-blind-spot interaction;
- valid-pose adaptive planning;
- Included Stable Masks as formal Lift input;
- reference P/N/V before production same-decision CUDA;
- complete Contributor as debug/reference only.

## Pass 3 — tickets → specification / reverse scope audit

- Orphan tickets: []
- 04A maps to Amendment 002 / DG-21.
- 04B maps to capability-gated visual prompts.
- 07A maps to Amendments 002–003 and DG-21/23.
- 07B maps to DG-22.
- 08 maps to Amendment 003 / DG-23 planning clauses.
- 08A maps to Amendment 003 / DG-23 tracking/correction clauses.
- 09/12 map to Amendment 003 presentation/repropagate clauses.
- 14/20 map to unchanged P/N/V ownership clauses and DG-23 deferred-ownership boundary.
- Result: **PASS**

No ticket introduces:

- persistent target-session stack;
- fixed user View count or mandatory full orbit;
- whole-image object inventory requirement;
- arbitrary part-selection requirement;
- provisional single-view Gaussian ownership as tracking truth;
- tracking membership as implicit Lift participation;
- tracker confidence as ownership confidence;
- direct Candidate 3D patching;
- unified fake Confidence percentage;
- nearest/top-k/distance attribution fallback;
- complete Contributor as production gate;
- automatic repropagate during Painting;
- automatic Re-Lift after repropagate.

## Pass 4 — final outcome → prerequisite reverse dependency audit

Native Selection backtrace:

```text
Ticket 16 native operation
← Ticket 15 current Candidate / explicit Re-Lift
← Ticket 13 readiness
← Ticket 14 reference P/N/V ownership
← Tickets 11/12 Included Stable View + repropagate/dirty identity
← Ticket 09 Gallery/review/tracking presentation
← Ticket 08A object-level tracking + correction memory
← Ticket 08 non-ownership bootstrap + ordered Key/Bridge plan
← Ticket 07B no-blind-spot palette
← Ticket 07A confirmed object-level Anchor
← Ticket 04B real Box/Mask prompts
← Ticket 04A Prompt/proposal foundation + 05/07 lifecycle/assessment
← Tickets 03/04 authoritative RGB and Mask lifecycle
← Tickets 01/02 context and authoritative renderer
```

Optional assessment branch:

```text
Ticket 10 P1 cross-view assessment
← Ticket 14 per-view P/N/V
← Tickets 07/09 assessment/presentation
```

Production Evidence backtrace:

```text
Ticket 21 hardened production
← Ticket 20 same-decision Direct Evidence
← Ticket 19 authoritative RGB / renderer identity / Render Working Set
← Ticket 14 reference P/N/V semantics and fixtures
```

Reverse checks:

- No consumer precedes formal artifact definition.
- 04B cannot claim ranking/Stable publication.
- 07A cannot close with layout fixes or fake-predictor tests.
- 07A no longer requires automatic resolution of materially distinct plausible clusters.
- Prompt/proposal changes do not invalidate formal Evidence before Confirm.
- ProposalDecision remains separate from ViewAssessment.
- 08 cannot publish Gaussian ownership or tracked Masks.
- 08A cannot select a production backend without the spike/ADR gate.
- 08A baseline fallback is explicit in artifact identity.
- Tracking role never authorizes Evidence; Bridge defaults Excluded.
- Only confirmed corrections enter tracker memory.
- 12 repropagate remains explicit and never auto-Lifts.
- 14 ignores tracker confidence/bootstrap support as ownership Evidence.
- Complete Contributor is absent from the mandatory path.
- Result: **PASS**

## Pass 5 — workflows + failures

- Typical inherited flows checked: 9
- Architecture / DG flows checked: 9
- Error/degradation flows checked: 18
- Invalid workflow references: 0
- Invalid error references: 0
- Result: **PASS**

Critical closure checks:

- RGB may publish while Mask/tracking/Evidence are absent.
- Anchor Prompt and Paint remain separate.
- 07A blocks suspicious unique proposals and exposes material ambiguity.
- 07A's benchmark measures false automatic selection/contamination rather than claiming correctness probability.
- 07B restores edge/corner editability.
- 08 bootstrap uses geometry without claiming ownership.
- 08 validates cameras before gain and records transition cost separately.
- Key/Bridge sequence is ordered and bounded.
- 08A compares baseline and candidate trackers before locking backend.
- Similar-instance identity drift becomes Review/fail closed.
- Confirmed correction becomes reference memory only through explicit repropagate.
- Bridge role and correction-reference status remain separate from Participation.
- 14/20 final ownership remains P/N/V over Included Stable Masks.
- Evidence/tracker/reference failures preserve RGB and prior valid artifacts.

## Mechanical critical-phrase audit

Critical semantics checked in Tickets 03, 04, 04A, 04B, 05, 06, 07, 07A, 07B, 08, 08A, 09, 10, 12, 13, 14, 15, 16, 18, 19, 20, 21, and 22.

Required phrases/semantics include:

- `RGB Ready` without Mask/Evidence;
- exact RGB-bound PromptState;
- truthful adapter capabilities;
- cluster before truncation;
- conservative object-level ProposalDecision;
- no generic calibrated Top-1 requirement;
- Confirm-only Stable publication;
- palette drag/collapse/Space-hide/no stale blind region;
- `TargetBootstrapArtifact` is non-ownership;
- Key / Bridge roles and ordered sequence;
- `trackingMembership ≠ participation`;
- tracker spike + later ADR;
- explicit single-frame baseline/fallback;
- confirmed CorrectionReference;
- explicit Repropagate and no automatic Re-Lift;
- `P/N/V` and `alpha × incoming transmittance`;
- tracker confidence is not ownership Evidence;
- complete Contributor debug/reference only;
- no partial proposal/Mask/Evidence/Candidate publication.

Failures: []

Result: **PASS**

## Conclusion

No known graph, traceability, reverse-dependency, workflow, or scope gap remains in the v2.5 planning graph.

This audit validates documentation and ordering, not future code or model quality. Ticket 04B still requires locked real visual-prompt validation; 07A requires conservative object-level decision/performance closure; 07B requires browser interaction validation; 08 requires bootstrap/pose/transition benchmarks; 08A requires a bounded tracker spike, implementation ADR, and locked-runtime tracking validation before production closure.