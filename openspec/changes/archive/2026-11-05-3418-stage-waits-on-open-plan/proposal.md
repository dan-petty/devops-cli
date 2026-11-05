# Proposal

## Why

Issue #3418: the stage job planned an item whose premise names a file that another open item's plan creates. The stage job did not see that plan. It recorded no dependency. Two plans then created the same new module, `src/devops_cli/roadmap/stage_constants.py`.

## What Changes

- The premise probe of the stage job finds each cited path that is missing at the staging commit and that an open item's plan creates. The job then returns the item to New with that open item in `refine.blocked_by`. It makes no model call for the item and adds no plan.
- The stage selection leaves out an item whose recorded `refine.blocked_by` names an open item. A closed item in that record does not leave it out.
- `check_proposal` refuses a plan that lists in `creates` a path that an open item's plan also creates. A refused reply goes back to the model once, as every other problem does.
- A plan of a closed or archived item is no dependency and no overlap.
- The change is observable: a return comment, a stage plan section, a selection reason and a refusal sentence. It carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: add the requirements of the open plan dependency, the recorded blocker, the overlapping `creates` path and the closed plan.

## Impact

- Refine already waits on `refine.blocked_by` with `NextStep.BLOCKED`. The stage job writes the same record and reads it, so no new record key is needed.
- An item with a cited path that an open plan creates waits for that plan. Before this change, the job planned it at once.
- `refine._recorded_blockers` becomes the public name `recorded_blockers`, so that the stage selection reads the record with the same parser.

## Feasibility

- Checked at `origin/main` d254410c. `git cat-file -e origin/main:src/devops_cli/roadmap/stage_constants.py` exits 128, so the module is absent.
- The plan `openspec/changes/3308-the-plan-check-compares-a-number/tasks.md` on `origin/main` names `src/devops_cli/roadmap/stage_constants.py` with `(new)` in its `Changes:` line. So an open plan creates the path.
- `git grep -n "blocked_by" origin/main -- src/devops_cli/roadmap/stage.py` finds no match. `Probe.missing` in `stage_probe.py` has no reader in `stage.py`. So the stage job never reads a recorded blocker or a missing path.
- `_overlap_problems` in `src/devops_cli/roadmap/stage_change.py` matches only the paths of open pull requests. It does not read the `creates` of a plan.
- `created_paths` in `src/devops_cli/roadmap/plan_read.py` already reads the `(new)` marks of a `tasks.md`.

## Existing Tool Considered

No open, maintained tool detects a dependency between two planned items. The change reuses the in-repo parts: `Probe.missing`, `created_paths`, the `refine.blocked_by` record, `NextStep.BLOCKED` and the overlap rule of `check_proposal`.
The written cost is about 6,000 tokens to build and test, about 1,000 tokens per month to keep and fix, and about 3 hours of elapsed time.
The change deletes no internal code. It renames `refine._recorded_blockers` to a public name.

The change fits in one pull request.
