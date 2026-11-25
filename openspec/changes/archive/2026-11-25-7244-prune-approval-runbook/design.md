# Design

## Decisions
- `Prune=confirm` on each Application, approved after a compare with the accepted list. homelab merges infra updates with no review, so a prune with no confirmation deletes what a wrong render drops.

## Rejected alternatives
- Prune with no confirmation: one wrong render deletes live objects.
