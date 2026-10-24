# Design

## Context

`select_candidates` in `src/devops_cli/roadmap/refine.py` picks the items of a refine round. `.github/roadmap.toml`, read into `RoadmapConfig` by `src/devops_cli/roadmap/config.py`, gave refine its Ready target. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- A round takes up to `--limit` items from each place in order, and no number of Ready items stops it.
- The roadmap configuration holds only the board.

**Non-Goals:**

- Refine looks at a blocked item again when its cited code changes (#2005).
- The backlog's P2 and P3 Ready items that refine has no record of stay out of a round, as before. Only the open milestones and the backlog's P0 and P1 items give such items.

## Decisions

- **Delete the target.** Its purpose was a pool of Ready items for the next release start (#1515). ADR 0012 and ADR 0013 removed release starts, and a person plans the milestones on the board, which shows the number of Ready items. `--limit` caps the model calls of a round, and an unchanged item costs no call (#1539). The owner's comment of 2026-10-20 on #1758 asks that a run with items left in any place refine up to `--limit` of them.
  - Rejected: count the target for each open milestone. The second pass takes backlog items only, so a count in one milestone cannot tell which backlog item to take, and the first pass already takes each milestone's items with no count.
  - Rejected: count only the open milestones' Ready items. Then the backlog's own Ready items never stop the backlog pass, and refine readies backlog items while the milestones hold fewer than the target, whatever the backlog holds. The number then has no meaning that a person can set.
- **Delete the key with no replacement.** The project keeps no backward compatibility before 1.0.0. `RoadmapConfig` forbids unknown keys, so a file that sets the key fails and names it. No repository of the owner sets it.
- **Refine takes no configuration.** `plan_refine`, `refine_item` and `_run_refine_adapter` read only the target from it. The refine command still opens its store through `_open_roadmap`, which reads the board from `.github/roadmap.toml`.

## Risks / Trade-offs

- [More model calls in each hourly round] → `--limit` caps a round at three items by default, and an item that nothing changed costs no call. The calls stop when each backlog item has had its round.
