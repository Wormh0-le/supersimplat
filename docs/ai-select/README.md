# AI Select Documentation

Stable AI Select documentation lives here.

## Structure

```text
docs/ai-select/
├── README.md
├── TICKET-14-SPLIT.md
├── adr/
├── spec/
├── benchmark/
└── walkthroughs/
```

## Migration policy

Move stable, long-lived project knowledge from scratch storage into this area:

- specifications
- architecture decisions
- acceptance records
- release evidence
- walkthrough documentation

Keep `.scratch/ai-select-v1` for:

- experiments
- reproduction scripts
- temporary benchmark runs
- investigation artifacts

## Current frontier

Ticket 14 is decomposed into:

- 14A Evidence Aggregation Layer
- 14B Gaussian Projection Scoring
- 14C Candidate Artifact
- 14D Candidate Review Surface

Ticket 13 Lift Readiness remains downstream of Ticket 14 completion.
