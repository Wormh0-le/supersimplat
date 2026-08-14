# Ticket 14 Decomposition — Reference P/N/V Evidence → Candidate / Uncertain

Status: **14A through 14D implemented; parent Ticket 14 complete**

Parent Ticket: `14-gaussian-lifting-candidate.md`

Normative authority remains:

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
3. parent Ticket 14 acceptance criteria

The stages below are implementation slices, not new product requirements.

## 14A — Evidence Contract & Working Set

Owns the formal admissible inputs, Evidence Policy identities, Core Target / Context / Evidence Working Set seams, Render Working Set preservation, and the versioned per-view `GaussianEvidenceArtifact` contract.

Must establish that only Included Stable Views can contribute formal Evidence and that geometry/Prompt/SAM/review metadata is provenance or Working-Set context, never Gaussian ownership Evidence.

## 14B — Reference Per-View P/N/V Evidence

Owns the trusted reference computation for per-view P/N/V (plus optional boundary diagnostics), using declared alpha-compositing contribution semantics:

```text
w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)
```

It validates reference backends and preserves raw per-view P/N/V without classifying the final Candidate.

## 14C — Multi-view Aggregation & Classification

Owns versioned multi-view aggregation over valid per-view Evidence and produces the four distinct internal classes:

```text
Selected
Rejected
Uncertain
Out of Scope
```

Candidate contains Selected only. Unobserved or materially mixed support remains Uncertain rather than default Rejected.

## 14D — Atomic Candidate Publication & Reference Validation

Owns atomic publication, stale/current binding, preservation of the previous inspectable Candidate on failed replacement, minimal Candidate/Uncertain overlay integration, and the parent Ticket 14 reference quality gate.

This stage does **not** add a Candidate provenance browser, Gaussian-level Evidence inspector, or direct Candidate editing surface.

## Dependency

```text
11 + 12
   |
   v
  14A
   |
   v
  14B
   |
   v
  14C
   |
   v
  14D
   |
   v
  13 Lift Readiness
   |
   v
  15 Candidate correction / Re-Lift
   |
   v
  16 Native Candidate operations
```

Ticket 10 remains optional and nonblocking.

Compatibility fields remain:

```text
next_implementation_ticket = 17
next_implementation_subticket = null
```
