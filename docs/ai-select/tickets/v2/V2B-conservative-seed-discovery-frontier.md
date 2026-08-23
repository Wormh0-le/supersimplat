# V2B — Conservative Seed and component Target Scope State

Status: **reviewed parent envelope — Q7-B accepted; awaiting stage decomposition; not agent-ready**

Blocked by: V2A2 only for S1 shadow  
Blocks: V2E, V2F

## Authority

Final Spec Amendments 002 and 006; ADRs 0023 and 0027; carried-over Stable ID, SceneSnapshot, Stable Mask, Participation, and Working Set contracts.

## Goal

Evaluate S0/S1 precision-first Seeds while creating a seed-independent, component-level TargetScopeState that can discover and track support omitted by Seed without treating uncertainty as ownership or background.

## Accepted model

```text
Scope Epoch
  └─ immutable Scope Revision
       ├─ Core components
       ├─ bounded Discovery Envelope ledger
       ├─ active Frontier components
       ├─ rejected/reopened Frontier ledger
       └─ required Context
```

- S0 uses P/N/V, visibility, conflict, and scale-aware connectivity.
- S1 adds soft Gaussian-center depth consistency; failure never erases plausible Envelope support.
- Envelope sources are seed-independent and provenance-recorded.
- Frontier transitions are component-level or deterministic subcomponent-level.
- Rejected Frontier is not Context and reopens only with new authoritative evidence/provenance.
- Core grows but does not shrink inside a Scope Epoch; authoritative correction/removal may rotate the epoch.
- Discovery Envelope ledger is bounded and deduplicated within an epoch.
- Core Coverage and structured Frontier Debt remain separate.

## Outputs / handoff

- S0/S1 shadow Seed records;
- deterministic componentization and lineage records;
- TargetScopeState and exact epoch/revision identity;
- discovery-source ledger and active/rejected Frontier state;
- component promotion/rejection provenance;
- Working Set v2 migration input preserving Core/Frontier/Context roles;
- Core Coverage and Frontier Debt inputs for V2E/V2F.

## Stage-level gates

- component adjacency/lineage policy and bounds;
- epoch rotation identity and exact restoration behavior;
- Envelope source admission/deduplication/budget;
- EvidenceWorkingSet v2 schema and production identity migration;
- S0/S1 shadow benchmark and threshold ownership.

## Validation families

Seed precision/recall and thin/disconnected retention; no-seed-lock fixtures; deterministic component lineage; Core monotonicity/epoch rebuild; rejected-not-Context; reopen only on new provenance; bounded ledger; Working Set role migration; Expert Recovery discovery.

## Non-goals

No View Utility math, Candidate/Native mutation, production Seed winner, or hardcoded calibration values.
