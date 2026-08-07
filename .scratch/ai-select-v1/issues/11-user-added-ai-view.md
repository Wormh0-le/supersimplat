# 11 — User-added AIView Using Current or Adjusted Camera

Status: ready — Ticket 09 prerequisite is implemented; current implementation frontier (parallel with 12)

Blocked by: 09 (satisfied), 07B (satisfied), 07 (satisfied), 05 (satisfied)

## Final Spec mapping

- Final Spec v1.3 §§5–8, 11–19, 24–26
- ADR 0016

## Purpose

Create user-owned Views through the same authoritative RGB, SAM 3 Image instance Prompt, Mask Review, Stable publication and Participation contracts as generated local Key Views.

## Required behavior

- `Use Current View` captures the current CameraBinding without moving Editor Camera;
- `Adjust New View…` uses provisional Camera Inspection and explicit Confirm View;
- authoritative RGB publication remains independent from Mask and Evidence;
- a user-added View may remain RGB Ready with no Mask and Evidence Not Requested;
- No-Mask UI offers Auto Generate Mask, Manual Draw or Exclude;
- Auto Generate Mask uses Positive/Negative Points and optional Positive Instance Box through the 04C provider;
- every provider request includes exact authoritative RGB bytes or current Companion RGB ref, not only a digest;
- one-point-only Prompt may show up to three candidates on the editing surface;
- Box/multiple-Point/refinement returns one candidate;
- previous-logits refinement uses only an opaque same-View/current-Companion ref before Accept;
- Paint/Erase use the 07B palette and never enter inference;
- automatic Mask Review/publication follows Ticket 07 semantics;
- Stable Mask publication dirties per-View Evidence but does not auto-Lift;
- View source never determines trust;
- Regenerate Auto Views cannot remove user-owned Views;
- adding/confirming a user View never resumes local generation automatically.

## Removed behavior

- no backend registry or Route B/C/D selection;
- no automatic Route-A fallback;
- no Negative Box or Prompt Brush;
- no generic ProposalSet/Decision panel for ordinary single-mask requests;
- no tracker/reference state;
- no raw previous-logits tensor in browser state.

## Failure and recovery

- render failure preserves the View record and offers Retry/Exclude;
- unresolved/mismatched RGB request fails before inference;
- Mask technical failure preserves View/RGB/prior Stable Mask and offers Retry/manual/exclude;
- semantic unavailable offers Prompt adjustment or Manual Draw;
- one-point candidate ambiguity is resolved on the editing surface;
- expired/invalid logits ref reruns current Points/Box without `mask_input`;
- Evidence failure preserves View/RGB/Stable Mask;
- palette move/hide/disposal leaves no stale input interception.

## Acceptance criteria

- [ ] Current/Adjusted View creation preserves exact CameraBinding/frustum identity.
- [ ] RGB Ready does not require Mask or Evidence.
- [ ] Auto Mask uses current SAM 3 Image adapter and v1 Prompt set.
- [ ] provider resolves authoritative RGB and validates dimensions/digest.
- [ ] candidate cardinality follows current multimask policy.
- [ ] refinement refs bind same View/RGB/Companion/candidate.
- [ ] Manual Draw and Paint/Erase remain available.
- [ ] no removed backend/tool/tracker state appears.
- [ ] Stable publication and Participation match generated Views.
- [ ] user-owned lifecycle is preserved across Regenerate Auto Views.

## Validation

- authoritative user-added RGB path;
- RGB Ready + No Mask fixture;
- one-point candidate-choice fixture;
- Box/multiple-Point single-mask fixture;
- refinement-ref expiry/Companion-replacement fixture;
- technical failure/manual recovery;
- Ticket 07B palette walkthrough;
- repository test/lint/locales/build.

## Non-goals

- No persistent cross-target View library.
- No separate acquisition architecture.
- No tracker or production Evidence kernel.
