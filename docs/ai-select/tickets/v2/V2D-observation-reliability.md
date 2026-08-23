# V2D — Observation Reliability

Status: **reviewed parent envelope — Q4–Q7 accepted; awaiting stage decomposition; not agent-ready**

Blocked by: V2C  
Blocks: V2E

## Authority

Final Spec Amendments 003–006; ADRs 0024–0027; Stable Mask, Participation, User Confirmed, and immutable P/N/V contracts.

## Goal

Compute deterministic view-level semantic Reliability from lagged q/s, same-decision regional readout, and the frozen component Scope Revision without changing raw visibility or observation authority.

## Accepted contract

- production residual uses trusted positive interior, negative ring, and low-weight/diagnostic boundary; Far Neutral is excluded;
- Positive Frontier Protection is bounded/asymmetric and uses frozen active Frontier components;
- rejected Frontier receives no Frontier protection and is not automatically Context;
- User Confirmed/manual, warm-up, immature, insufficient-support, and safely unscorable Views keep weight `1.0` with reasons;
- eligible automatic Views use independent median/MAD weights with floor, not sum normalization;
- maturity-gated absolute guard may further cap weight;
- Reliability multiplies P/N only; V remains unweighted;
- leave-one-out is offline reference only;
- a scope advance invalidates dependent Reliability and requires recomputation under the new Scope Revision.

## Stage-level gates

Region/support coefficients, robust eligible set, reason schema, maturity/floor calibration, component map readout cost, LOO benchmark owner, policy freeze/identity.

## Validation families

Lag ordering, exemptions, insufficient-support neutral handling, new Frontier true positives, Core contradiction, rejected-Frontier behavior, all-poor absolute guard, raw-V invariant, scope invalidation, full-set/LOO gap.

## Non-goals

No Stable Mask mutation, Participation automation, per-pixel product weight, classified-N production dependency, or Candidate publication.
