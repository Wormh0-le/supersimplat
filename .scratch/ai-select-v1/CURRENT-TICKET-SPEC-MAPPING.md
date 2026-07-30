# Current Final Spec v1.2 → Ticket Mapping — v2.9

Status: **current normative ticket mapping**

This file is the authoritative mapping from active AI Select tickets to `docs/specs/ai-select-final-spec-v1.2.md`.

Ticket-local references to Final Spec v1.1 or Amendments 001–005 are retained only as historical implementation provenance. They MUST NOT be used as current requirements, closure gates, or supersession chains. Where a ticket-local mapping conflicts with this file or Final Spec v1.2, Final Spec v1.2 and this mapping prevail.

ADR 0013, ADR 0014 and DGs remain subordinate rationale.

| Ticket | Current Final Spec v1.2 mapping | Rationale / notes |
|---|---|---|
| 01 | §§1–4, 21, 25, 27–29 | CurrentTargetContext, identity, suspension/recovery |
| 02 | §§1–5, 27–29 | Native shell, authoritative Anchor RGB, runtime readiness |
| 03 | §§3–5, 18–19, 27–29 | Camera inspection, RGB publication, Retry |
| 04 | §§4–6, 15–16, 21–22, 27–29 | Editing/Stable/Evidence lifecycle |
| 05 | §§4–6, 21, 25, 27–29 | Anchor validation, Confirm, Restart |
| 04A | §§4–6, 27–30 | Prompt authoring and bounded proposal foundation |
| 04B | §§4, 6, 12–14, 27–30 | Truthful visual-Prompt adapter enablement |
| 06 | §§4–5, 15–18, 27–30 | Progressive RGB and route-A baseline compatibility |
| 07 | §§15–16, 19, 21–22, 27–29 | ViewAssessment and Participation |
| 07A | §§4–6, 27–30 | Conservative object-level Anchor ProposalDecision |
| 07B | §7, §§20, 28–29 | Floating Prompt/Edit palette |
| 08 | §§8–10, 27–29 | Visible support, bootstrap, sparse planning |
| 08A | §§11, 14–18, 26–29 | Acquisition contracts and backend registry |
| 08B | §§12–18, 27–29 | Route-B production acquisition and B2 fallback |
| 09 | §§19, 27–29 | Gallery/frustum/acquisition inspection |
| 10 | §§15, 19, 22–24, 27–29 | Cross-view Review assessment |
| 11 | §§7, 19–21, 27–29 | User-added Views and correction UX |
| 12 | §§16–18, 21, 27–29 | Refresh, dirty and stale lifecycle |
| 13 | §§19, 21–24, 27–29 | Coverage, diversity and Lift readiness |
| 14 | §§22–25, 27–29 | Reference P/N/V and Candidate |
| 15 | §§21, 24–25, 27–29 | Candidate correction and explicit Re-Lift |
| 16 | §§24–25, 27–29 | Native Set/Add/Remove/Intersect |
| 17 | §§4, 21, 24–25, 27–29 | Undo-and-Fix, Restart and target lifecycle |
| 18 | §§4, 21, 25, 27–29 | Suspended state and exact Undo recovery |
| 19 | §§3–5, 23, 27–29 | SceneSnapshot, authoritative RGB and Render Working Set |
| 20 | §§4–5, 22–24, 27–30 | Production same-decision P/N/V Evidence |
| 21 | §§4, 7, 17–18, 21–28 | Failure, calibration and release hardening |
| 22 | §§0, 23, 27–30 | Legacy product/Contributor contraction |

## Current execution-path enforcement

The next implementation path MUST use these mappings directly:

```text
04B → Final Spec v1.2 §§4, 6, 12–14, 27–30
07A → Final Spec v1.2 §§4–6, 27–30
07B → Final Spec v1.2 §7, §§20, 28–29
08  → Final Spec v1.2 §§8–10, 27–29
08A → Final Spec v1.2 §§11, 14–18, 26–29
08B → Final Spec v1.2 §§12–18, 27–29
```

No implementation agent may reconstruct Amendment 001–005 to interpret these tickets.

## Audit rule

An audit passes current-spec mapping only when:

- every ticket ID exists in this table;
- every active ticket resolves to Final Spec v1.2 sections here;
- no active closure criterion requires a historical Amendment;
- historical ticket-local v1.1 references are explicitly treated as provenance only;
- Final Spec v1.2 remains the sole source of current normative behavior.
