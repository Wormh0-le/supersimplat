# Final Spec v1.3 Walkthrough Coverage — v2.35

## Typical flows

| ID    | Flow                              | Ticket path                                 | Required result                                                                                                        |
| ----- | --------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| WF-01 | SAM 3 Image migration             | `04B → 04C`                                 | Current static path uses official SAM 3 Image and rejects Multiplex manifest/artifacts                                 |
| WF-02 | Automatic availability            | `04C + 02 → 02C`                            | Only Connecting/Available/Unavailable appears; current SAM 3 Image profile validates                                   |
| WF-03 | Authoritative RGB inference       | `04C/08A`                                   | Provider resolves exact RGB bytes/ref and rejects digest-only input                                                    |
| WF-04 | One-click Anchor                  | `04C + 07 → 07A`                            | One result becomes Editing Mask; user refines/confirms; no automatic correctness claim                                 |
| WF-05 | Box/multi-point Anchor            | `04C + 07 → 07A`                            | One result becomes Editing Mask, then Edit/Confirm                                                                     |
| WF-06 | Opaque previous-logits refinement | `04C → 07A`                                 | Companion-local logits ref refines the sole automatic result and returns one Mask                                      |
| WF-07 | Floating palette                  | `07A → 07B`                                 | Positive/Negative Point, Positive Box, Paint/Erase only; no stale hit region                                           |
| WF-08 | Geometry hint                     | `07A → 08`                                  | Anchor produces deterministic compact TargetGeometryHint without ownership                                             |
| WF-09 | Initial local Views               | `08 → 16B/16G/21`                           | Schedule 4–8 framed automatic Generated Views once; no persistent planning controls                                    |
| WF-10 | Per-View contracts                | `08 + 04C → 08A`                            | RGB-bound Prompt/request/result/ref identities validate without backend registry                                       |
| WF-11 | 3D-guided per-View Mask           | `08A + 07 → 08B`                            | Projected Box/Points run SAM 3 Image single-mask inference and Mask Review                                             |
| WF-12 | Gallery inspection                | `08B → 09`                                  | Render, Prompt, inference, Review, Participation and Evidence remain separate                                          |
| WF-13 | User-added View                   | `07B + 09 → 11`                             | Same RGB/image instance path and manual correction behavior apply                                                      |
| WF-14 | Changed-intent lifecycle          | `09 → 12 → 16G`                             | Changed Prompt/manual edits create normal intents; refs invalidate correctly; no product Mask recovery command         |
| WF-15 | Lift and optional diagnostics     | `11/12 → 14/13 → 15/16`, optional `14 → 10` | Ticket 13 owns readiness; Ticket 10 may enrich conflict diagnostics but does not block release                         |
| WF-16 | Native application                | `14/15 → 16`                                | Candidate stays non-destructive until an explicit Set/Add/Remove/Intersect operation                                   |
| WF-17 | Integrated canvas-first surface   | `16A–16G → 17`                              | One Navigator/Work Area/Inspector ownership model, no Dock header/action bar, and a Ticket 17-ready lifecycle seam     |
| WF-18 | Multi-object target lifecycle     | `16G → 17 → 18`                             | Exact Undo-and-Fix, explicit A/B/C Add operations, rotated target identity and durable Native Selection/history        |
| WF-19 | Scene mutation suspension         | `17 → 18 → 19`                              | Target-scoped mutation preserves artifacts read-only; exact semantic Native Undo resumes with a fresh request revision |

## Error and recovery flows

| ID    | Failure                                      | Ticket path     | Required retained state / supported recovery                                                                                  |
| ----- | -------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| EF-01 | old Multiplex manifest active                | `04C → 02C`     | Availability Unavailable; native editor usable; operator installs current manifest                                            |
| EF-02 | historical 04A Prompt artifact supplied      | `04A → 04C/08A` | Fail current schema validation; no removed Prompt-family conversion                                                           |
| EF-03 | Ticket 06 legacy fallback invoked            | `06 → 08B/21`   | Reject as current production route; preserve RGB/manual recovery                                                              |
| EF-04 | RGB digest has no resolvable bytes/ref       | `04C/08A/08B`   | Reject before inference; preserve Prompt/RGB-ready record                                                                     |
| EF-05 | RGB ref digest/dimensions mismatch           | `08A/08B`       | Fail closed; no partial Mask/ref result                                                                                       |
| EF-06 | binary Brush supplied as logits              | `04C/08A`       | Reject artifact; keep Prompt/Editing state; no inference                                                                      |
| EF-07 | Companion Instance replaces logits owner     | `02C/04C/12`    | Invalidate ref; a changed Point/Box starts a normal fresh inference                                                           |
| EF-08 | stale candidate/logits lineage               | `04C/07A/12`    | Reject cross-RGB/adapter/candidate ref; preserve prior Stable Mask                                                            |
| EF-09 | Anchor result needs correction               | `07A/16G`       | Change Point/Box input or use Paint/Erase; identical-input explicit recovery is absent                                        |
| EF-10 | no Anchor result                             | `07A/16G`       | Preserve RGB and Stable history; change Prompt or use manual editing                                                          |
| EF-11 | geometry extraction unavailable              | `08`            | Preserve Anchor; offer the bounded local/user-added View path                                                                 |
| EF-12 | local View blank or invalid                  | `08/16G`        | Keep the failed View inspectable/excluded; user may add a replacement View                                                    |
| EF-13 | per-View SAM technical failure               | `08B/09/16G`    | Preserve RGB/prior Stable Mask; change Prompt, edit manually, exclude, or add a replacement View                              |
| EF-14 | semantic per-View unavailable or Review      | `07/08B/09`     | No arbitrary Stable Mask; adjust Prompt/View/manual state or keep Review Excluded                                             |
| EF-15 | weak Gaussian support / Ticket 10 absent     | `13/21`         | Lift Readiness Limited/Not Ready; release/readiness still work without optional Ticket 10                                     |
| EF-16 | Evidence/Lift failure                        | `14/20/21`      | Preserve Views and Stable Masks; previous Candidate remains prior/stale and normal correction/Re-Lift may produce replacement |
| EF-17 | render or Candidate replacement failure      | `03/14D/16G`    | Changed/reset Anchor pose or corrected input creates a normal attempt; prior valid Candidate remains atomically inspectable   |
| EF-18 | unsafe Undo-and-Fix or late restarted work   | `01/12/17`      | Disable exact-command Undo-and-Fix without traversal; rotated target identity rejects late Mask/Evidence/Lift publication     |
| EF-19 | target mutation, non-exact Undo or late work | `01/12/18`      | Remain Suspended until exact dependency restoration; preserve artifacts and discard obsolete request revisions                |

## Ticket 18 suspension evidence

Deterministic mutation-matrix tests cover semantic render, per-Gaussian
geometry, deleted membership and world-transform identities while excluding
selection and lock flags. Controller stress tests cover immediate suspension,
read-only artifact retention, non-exact restoration, exact resume with a fresh
request revision and late Generated-View work rejection. Existing Candidate
application, toolbar and lifecycle-menu suites continue to prove that a
Suspended Candidate cannot apply and that `选择另一个对象` is not reintroduced
into the contextual 3D Toolbar. Ticket 18 is browser/editor lifecycle work and
adds no locked-GPU validation requirement or claim.

## Ticket 17 lifecycle evidence

Deterministic domain, native-history and UI contract tests cover exact
top-of-stack Undo-and-Fix, a later native edit, Native Undo/Redo refresh,
pending Lift reset, target-context rotation, confirmation policy, A/B/C
explicit Add continuity, lifecycle-menu ownership and tool-switch disposal.
Existing Anchor, Mask and Generated-View restart suites continue to prove that
late work cannot republish and target-local Mask/View/Evidence state is
released. Ticket 17 adds no locked-GPU validation requirement or claim.

## Ticket 16G operator evidence

On 2026-08-17 the fresh production bundle was opened from a clean `127.0.0.1`
origin to avoid an older service-worker cache. The tracked
`controlled_front_back_overlap.ply` fixture imported successfully as 16,384
splats, the AI Select tool opened, and the rendered DOM contained neither the
removed Dock-wide header nor removed recovery controls. The inspection covered
wide desktop, `1280×720`, and `1024×720`; the 2D canvas retained priority and
the visible controls did not overlap.

The local Companion was unavailable, so the interactive pass covered the real
Connecting/Unavailable, no-Target and loaded-Target surfaces. Deterministic UI,
presentation and controller tests cover planning/failure, RGB Ready,
confirmed/unconfirmed Mask, Review, Excluded, Candidate
current/stale/updating/failed, adjustment, filter-empty and collapsed-sidebar
projections. This walkthrough is editor UI/state evidence only; it makes no new
production GPU, Companion model-capability or camera-planner quality claim.

## Coverage result

- typical walkthroughs: 19;
- error walkthroughs: 19;
- current ready frontier: Ticket 20;
- current product recovery contract: changed intent, manual editing, exclusion,
  replacement View, or normal Re-Lift as applicable;
- obsolete product planning/recovery controls present: no;
- fresh-bundle operator evidence recorded: yes;
- production GPU validation added by Ticket 16G: no.
