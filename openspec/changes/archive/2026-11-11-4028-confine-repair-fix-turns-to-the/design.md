# Design

## Decisions

- The scope is the code spans of the text of every group (`plan_paths`, the same set that `unplanned_paths` uses) without the spans that hold a space, which are commands, and the change folder. One set of paths gives one rule for the check before the turn and the check after it.
- A path matches as a whole word of the log. A run path such as `/runner/work/repo/src/app.py:3` matches `src/app.py`, and `src/app.pyc` does not.
- The check runs in `_repair_after_push`, before `run_fix_step`. The stop uses the class `outside_plan`, whose action is `wait`, so the item is Blocked and the commits that passed are pushed.
- A log that is empty, because the link of the check names no run, is out of scope: no path is named.
- The scope reads the change folder that `find_change(..., archived=True)` finds, as the fix step does.

## Rejected alternatives

- A list of check names that are never in scope: a new check makes the list stale (ADR 0004 pins only the required names).
- A second path argument of `run_fix_step`: the step already confines a turn to the plan paths.
- Reading the annotations of the check run: one more request for each failed check, and the log holds the same paths.
