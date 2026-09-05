# Triage Labels

Map skill triage roles to these repository labels.

| Skill role | Repository label | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Scope or disposition still needs evaluation. |
| `needs-info` | `needs-info` | A concrete required input is missing. |
| `ready-for-agent` | `ready-for-agent` | Specified, open, in the current queue, unblocked, and inputs available. |
| `ready-for-human` | `ready-for-human` | The next executable step requires a human. |
| `wontfix` | `wontfix` | The requested work will not be pursued. |

Prepared/blocked work is not ready merely because its contract is detailed. Record its blockers in the body and remove `ready-for-agent`. Roadmap outcomes and conditional research remain unlabelled as ready.

A superseded plan closes with reason `not_planned` and a replacement pointer, not `completed`; its useful requirements may be retained under the new owner. Completed acceptance records remain historical evidence. Do not use old closed issues carrying historical ready text as implementation permission.
