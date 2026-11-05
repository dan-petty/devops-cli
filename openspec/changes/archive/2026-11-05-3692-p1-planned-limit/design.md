# Design

## Context

`_Judge.reason` decides the first rule that leaves an item out, and `_queue_full` is the last of the rules that `--item` does not overrule. `devops roadmap explain` reads the same reasons. The inbox states the rule in its own line.

## Decisions

- **One constant holds the priorities that pass the limit.** `CONST_ROADMAP_PLANNED_LIMIT_PRIORITIES` holds `P0-Critical` and `P1-High`. The rule and the two texts read it, so they state the same rule.
- **The count stays the count of all open Planned items.** A P1 item that passes the limit adds to the count, so it holds lower priorities back longer. This is the behavior of P0 items now.

## Rejected Alternatives

- **Raise the default of the limit.** The owner asked to keep the limit, and the 39 to 41 Planned items are already about twice the default, so a small raise would let no item pass.
- **A new setting for the priorities that pass.** #3692 asks for no new setting, and no pattern in `RoadmapStageConfig` needs one.
- **Remove the limit.** The owner asked to keep it, and the evidence of #3487 for the limit stays true for P2 and P3 items.
