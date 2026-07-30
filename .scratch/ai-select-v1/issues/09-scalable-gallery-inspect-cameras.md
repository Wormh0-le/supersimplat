# 09 — Scalable Gallery + Frustum sync + acquisition inspection

Status: blocked — waits for Ticket 08B production acquisition

Blocked by: 08B

Blocks: 11, 12

## Final Spec mapping

- Final Spec v1.2 §§19, 27–29
- DG-26 Decisions 4–8
- ADR 0014 as subordinate Route-B-first rationale

## Inputs / preconditions

- Progressive AIView registry;
- independent render/mask/evidence states;
- Ticket 08 immutable sparse Key-View plan segments;
- Ticket 08A backend/proposal/decision/publication contracts;
- Ticket 08B generic acquisition, fallback, decision, assessment and publication states;
- Participation;
- Generated frustums;
- Camera Inspection;
- optional sequence/reference state only when a future adopted backend actually provides it.

## Outputs / handoff artifacts

- single-row scalable Gallery;
- summary/filter/review queue;
- bidirectional card↔frustum sync;
- Inspect AI Cameras;
- Anchor/Key/User-added role presentation;
- separate render/acquisition/proposal-decision/Mask-quality/Participation/Evidence presentation;
- backend and route-A fallback provenance;
- explicit distinction between acquisition technical failure and Decision `unavailable`;
- optional future auxiliary/tracker/reference presentation only when capability exists.

## What to build

Build Gallery and frustum synchronization without collapsing state boundaries.

Cards MUST distinguish:

```text
Render status
Acquisition status / attempt
Backend + fallback provenance
ProposalDecision status
Mask quality / Stable Mask presence
Participation
Evidence status
Candidate stale/current status where applicable
```

Required state examples:

```text
acquisition = ready
Decision = unavailable
Stable Mask = none
Participation = excluded
```

is distinct from:

```text
acquisition = failed
Decision = not-produced
Stable Mask = prior-or-none
Participation = unchanged/excluded by current policy
```

Navigation and filtering never change Prompt, ProposalSet, Decision, Stable Mask, Participation, optional reference memory, Evidence or Candidate identity.

## Acceptance criteria

- [ ] Stable order is Anchor, planner segments in creation order, then user-added creation order.
- [ ] Cards remain compact: thumbnail, View ID, primary status, Participation, selection and compact role/backend metadata.
- [ ] Anchor/Key/User-added roles are visible without being conflated with Participation.
- [ ] Plan segment/local index are inspectable; stable `viewId` remains identity.
- [ ] Render, Prompt synthesis, acquisition, ProposalDecision, Mask quality, Evidence and Participation are not one flag.
- [ ] `selected`, `ambiguous`, and `unavailable` are inspectable Decision states.
- [ ] `unavailable` is shown as a completed acquisition with no eligible proposal, not as backend/protocol/OOM failure.
- [ ] Technical acquisition failure has no fabricated `unavailable` Decision.
- [ ] Ambiguous exposes review/refine/choose/Paint actions and does not pretend a Stable Mask exists.
- [ ] Unavailable exposes Retry / Regenerate Prompts / Adjust View / Manual Draw / Exclude actions without automatic route-A fallback.
- [ ] Backend/fallback identity is inspectable and does not imply trust or Included.
- [ ] Route-B technical failure and route-A fallback result remain separately inspectable.
- [ ] Optional correction-reference status is absent unless a future backend advertises and implements it.
- [ ] Optional Auxiliary/Bridge/tracker roles appear only when a future adopted backend creates them.
- [ ] Status priority is deterministic; Evidence Failed appears only when Evidence was requested and never replaces RGB Ready.
- [ ] Summary counts separate unavailable Decisions from technical acquisition failures.
- [ ] Summary counts do not pretend to be Lift Readiness.
- [ ] Filters support All / Needs Attention / Included / Excluded / Key / User-added and do not mutate state.
- [ ] Needs Attention includes ambiguous, unavailable, unresolved Review, no Stable Mask, Prompt/acquisition failure, Render Failed and actionable Evidence Failed.
- [ ] Filtering de-emphasizes nonmatching frustums without deleting/reclassifying them.
- [ ] Card↔frustum selection works without moving Editor Camera.
- [ ] Inspect AI Cameras reuses Camera Inspection and never retargets Anchor.
- [ ] A selected off-screen frustum has explicit locate/inspect recovery.
- [ ] Generated frustums remain read-only in v1.2.
- [ ] Thumbnail/resource handling supports 10–20+ Views without one full Mask Editor per card.
- [ ] Sticky add exposes Generate More / Use Current View / Adjust New View; Stop remains visible while active.
- [ ] Generate More appends a planner segment and does not visually stale prior completed Views.
- [ ] No ordinary Delete View; Exclude is normal participation removal, record deletion is Restart/Regenerate-owned.
- [ ] Needs Attention empty state provides return to All.

## Failure / recovery criteria

- Failed thumbnails/resources keep recoverable View records.
- Prompt/acquisition/decision/publication failure remains distinguishable from View Render Failure.
- Route-A fallback is shown as fallback, never as route B.
- Ambiguous retains its ProposalSet and review actions.
- Unavailable retains its successful acquisition result/diagnostics and no-Stable state.
- Optional tracker failure/drift remains capability-gated and distinguishable from ordinary per-view failure.
- Filtering/navigation never mutates formal state.
- Stale acquisition/decision/assessment result is shown as stale rather than attached to a newer View revision.

## Validation

- `npm test`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- manual 10–20+ View walkthrough
- selected/ambiguous/unavailable Gallery fixtures
- unavailable-versus-technical-acquisition-failure fixture
- route-B failure → route-A fallback provenance walkthrough
- RGB Ready + acquisition pending/failed + Evidence Failed combinations
- frustum↔card tests
- browser walkthrough with every Generated Frustum initially behind observer
- optional Auxiliary/Bridge walkthrough only under an adopted capability fixture

## Non-goals

- No acquisition backend execution.
- No Prompt synthesis or ProposalDecision algorithm.
- No tracker/reference mutation.
- No manual sequence reorder/search.
- No Candidate provenance inspector.
