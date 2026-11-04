# Design

## Context

The stage job selects items with `select_stageable`. `_Judge.reason` decides, for one item, the first rule that leaves it out, and `devops roadmap explain` reads the same reasons with the item as `probe`. The inbox lists what waits for a person.

## Decisions

- **The limit is a rule in `_Judge`, the last of the rules that `--item` does not overrule.** An item that fails an earlier rule keeps that reason. An item that would be taken gets the limit as its reason. So `explain` gives the true first failing rule, and the plan lists a reason for each item.
- **The count is the open Planned items.** It comes from the list that `_open_items` read for the filter, so the job makes no extra request. `planned_count` in `src/devops_cli/roadmap/planned.py` is the one function that the job and the inbox call.
- **An item of priority `P0-Critical` passes the limit.** The issue asks for this. The item still waits on the other rules.
- **`--item` passes the limit.** A person who names an item overrules the filter, the limit of a round and the record of an earlier split. The limit follows the same rule.
- **The default is 20.** The Service delivers about 2 items a day, so 20 items wait about 10 days. A longer wait lets the default branch move under the plan.
- **The limit counts Planned items, not Staged drafts.** The issue defines the queue as Planned items. The requirement "The limit bounds a round, not the open drafts" stays true.
- **The inbox line has no number and no age.** It states a state of the queue. A delivery or a higher limit clears it.

## Rejected Alternatives

- **A share of places for each kind of item.** The issue says that items do not compete for places: `priority_order` takes the lowest number first within a priority.
- **A check before the model call in `plan_stage` only.** `explain` would not name the limit, and the plan would not list the reason for each item.
- **A cap of `limit` by the room that is left (`planned_limit - count`).** It would stop the overshoot, but it adds a second number to explain. The overshoot is less than `roadmap.stage.limit`, which is 3 by default.
