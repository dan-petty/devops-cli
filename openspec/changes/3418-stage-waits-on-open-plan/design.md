# Design

## Decisions

- The stage job matches a missing cited path to the `creates` paths of each open item's plan. `created_paths` reads the `(new)` marks of the plan's `tasks.md`. A plan that names a path only in a non-goal does not block an item.
- The stage job does not match identifiers in this change. A missing identifier makes no dependency. Full-text matching of identifiers would block items on a name that a plan only mentions.
- The stage job reads the plans of open items on the default branch only. `planned.py` reads `origin/<default>` (see `read_planned_changes`). A plan on an open draft branch is not read.
- The stage job reads the plans lazily, once for each run. It reads them only when the premise probe finds a missing path, or when `check_proposal` checks a reply. A run with no such case reads no plan.
- A closed or archived item is no dependency. The reader takes only the active folders of open items.
- The stage job records a dependency in `refine.blocked_by` and sets `refine.next_step` to `blocked`, with Status New. It also comments on the item. Refine already waits on that record until each open blocker closes, so refine does not rewrite the record while the blocker is open.
- The stage selection reads `refine.blocked_by` through `recorded_blockers`. It leaves out an item only while a recorded blocker is open.
- `check_proposal` refuses an overlapping `creates` path. A refused reply goes back to the model once, with the other problems of the reply.
- The dry run lists the read of the tasks of each open plan, with its condition and its repeat, as a run makes it.
- The stage eval reads no open plan. `plan_item` therefore raises the refusal sentence if the planner ever returns a dependency, and it never does in practice.

## Rejected alternatives

- Full-text matching of plan folders: a plan can name a path in a non-goal, which would block an item by mistake.
- Matching by the spec requirement names: a plan can create a path that no requirement name states.
- Reading the GitHub issue of each item during the probe: it adds a remote read for each item, and the probe would stop being local.
- A comment only: a comment does not stop the next stage round or the next refine round.
- A stage-only dependency record: it repeats the wait rule that refine already has, and it needs a second reader.
- The overlap check in `stage_paths` alone: `stage_paths` checks the staged tree, not another plan.
- The overlap check in the prompt only: a prompt rule cannot refuse a reply.
- A JSON manifest in each plan folder: it changes the plan format and needs a migration for plans on the default branch.
- Reading the plans of open draft branches: `planned.py` reads only the default branch, and each branch would need a remote read.

## Interaction with other open items

- #3301 changes how the probe decides that a path is absent. This change adds a function that reads `Probe.missing` and does not change that decision. If #3301 lands first, rebase on it before the first push.
