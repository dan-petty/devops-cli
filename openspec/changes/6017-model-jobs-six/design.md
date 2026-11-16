# Design

## Decisions
- Set the value in the ConfigMap template, which deploy-stack renders. The owner chose 6 for all repositories together.
- Keep the code default at 2 (ADR 0021, section 5): a cluster that sets no value keeps the semaphore `agent` of the record.

## Rejected alternatives
- Raise the code default to 6: the owner choice is for this cluster, and ADR 0021 section 5 gives the default of 2.
