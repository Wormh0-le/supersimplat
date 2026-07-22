# Final Spec Walkthrough Coverage

## Typical Flows A–I

| ID | Flow | Ticket path |
|---|---|---|
| WF-A | Fast single-object | `02 → 04/05 → 06 (RGB + Initial Auto Mask) → 07 → 08/09 → 13 → 14 → 16` |
| WF-B | Adjust Anchor | `02 → 03 → 05` |
| WF-C | Add a missing user view | `09 → 11 → 04/05 mask semantics → 13 → 14/15` |
| WF-D | Redraw bad mask from scratch | `09 → 05 mask editor semantics → 12/15 → 14/15` |
| WF-E | Modify reference then Repropagate | `05 → 12 → 07/10 reassessment → 13 → 14/15` |
| WF-F | Select multiple objects | `16 → 17 Restart → 02... → 16 → 17` |
| WF-G | Candidate structural error | `14/15 → 09/07/11/08 corrections → 15` |
| WF-H | Fix after Candidate applied | `16 → 17 Undo and Fix → 15` |
| WF-I | Scene mutation + Undo | `18 Suspended → exact Native Undo → resume` |

## Error / degradation flows

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion Offline | 02/21 | Native editor unaffected; reconnect/settings recovery |
| ERR-2 | Preview Failure | 03/21 | Keep last valid preview; retry |
| ERR-3 | Mask Generation Failure | 06/07/11/21 | Keep View/RGB; retry auto / manual / exclude |
| ERR-4 | View Render Failure | 06/07/08/21 | Keep failed View record; retry / replacement / exclude |
| ERR-5 | Lifting Failure | 14/21 | Keep Views/Stable Masks/Gallery; Candidate not replaced |
| ERR-6 | Repropagate Failure | 12/21 | Keep old Stable Masks; no partial proposed publication |
