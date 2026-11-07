# Proposal

## Why

A fix step of the Service edited paths that the plan does not name (#3824). On #3808, the fix for #3536, the step "Make check Plan Check pass" changed `src/devops_cli/roadmap/plan_check.py`, `docs/roadmap/plan-check.md` and `openspec/specs/roadmap-plan-check/spec.md`, and the next step added a test for those lines. The plan named two paths. The edit made a check pass by narrowing it, and the pull request body did not say so. One failed check led to two more edits outside the plan. The owner rule is to write no compensating code and to leave such an item for a person (AGENTS.md rule 2).

## What Changes

- After a fix step, the exit checks compare every path that the step changed, added or deleted with the paths that the plan names. A step that touched another path stops with the new class `outside_plan` and the action `wait`.
- The plan names a path in a code span of the text of any group of `tasks.md`. This holds the `Reads:` line, the `Changes:` line and the tasks. A file under the change folder of the item is always allowed.
- The stop is a normal stop of the job. Its comment holds the failed check, the end of its log, the reason with each path, and the discarded diff. The step resets the checkout. No repair round runs, for the failure has no repair paths.
- A group step is not checked. Its group names its files, and the stray rule of #3092 already covers it.
- This replaces the rule of #3488 that a fix step keeps a new file under `src/`, `tests/`, `docs/` or `openspec/`. A fix step keeps a new file only when the plan names it.
- A consumer observes the stop, the class and the comment, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A fix step changes only the paths that the plan names.
- `roadmap-failure-taxonomy`: The new class `outside_plan` waits for a person.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_strays.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`

## Feasibility

Checked against `origin/main` at `b6af763b`.

- `_exit_failure` in `implement_step.py` already stages the checkout and runs the exit checks in order. A check after the stage sees every path of the step, deletions included, with `git diff --cached --name-only --no-renames -z <base>`. For a fix step `keeper.base` is the commit at the start of the step, because a fix step ticks no task and makes no `wip:` commit.
- `implement_strays.py` already reads the paths that a group names as the code spans of its text. The new check reuses that rule for all groups, so a plan with no `Reads:` line is read the same way.
- `_extra_ask` gives an extra turn only to a failure with `repair_paths`. A `_Failure` without them stops the step at once, which is what the issue asks.
- `implement_run._stopped_by` already carries the class, the check, its log and the discarded diff into the stop comment, and `stop()` sets the item to Blocked. The issue asks to set the item back to `New` with return-style evidence. This change keeps the existing stop, which holds the same evidence, and leaves the item with a person under the action `wait`, as for `no_change_in_fix` and `tests_lost`. A return to `New` would drop the branch and the draft that the stop keeps.
- The history of #2116 shows "The agent changed no file" at the fix stage four times. #3476 covers that case with the class `no_change_in_fix`, so it needs no change here. #3645 changes `implement_run.py` for the scoped checks and does not touch `_exit_failure`. The open branch of #2804 changes `implement_step.py` in another function. Neither overlaps.

## Existing Tool Considered

No open tool judges the paths of an agent edit against a plan of this repository. The change reuses `stray_files`, `parse_task_groups` and `git diff`. It adds no dependency. To build it costs about 40k tokens to write, about 3k tokens a month to keep, and about 2 hours of elapsed time. The change deletes no internal code.
