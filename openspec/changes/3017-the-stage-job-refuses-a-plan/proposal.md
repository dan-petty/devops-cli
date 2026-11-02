# Proposal

## Why

About 8 of 37 recent plans order their groups so that a group reads a path that only a later group creates (#3017). The stage job refuses such a plan, but its problem text names only the reading group, so the model cannot see which group to move. The issue asks that the problem name both groups.

## What Changes

- `path_problems` finds the first later group that lists a missing path in `creates` and names it in the problem.
- The problem text tells the model to move the creating group before the reading group.
- A new test in the shape of #2996 asserts that the problem names the reading group and the creating group, and says which group to move.
- A test asserts that a path no group creates keeps the message without a creating group.
- The acceptance criterion "a plan whose groups create what they read passes" has a test already: `test_a_path_that_an_earlier_group_creates_passes_in_a_later_group`. This change adds none.
- The `roadmap-stage` spec delta adds a sentence and a scenario: the problem names both groups.
- Item 15 of `k8s/README.md` describes the check, so it gets the new sentence.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan names files that exist at the staged commit

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `k8s/README.md`
- Tests: `tests/roadmap/test_roadmap_stage_paths.py`

## Feasibility

- Read of `src/devops_cli/roadmap/stage_paths.py` at the base: `path_problems` is called from `check_proposal` (`stage_change.py`) and, after a split, from `stage.py`. It reports a path that no group up to the reading group creates, and `_problem` takes only the reading group number. #3010 (archived in `openspec/changes/archive/2026-11-01-3010-stage-refuses-missing-paths/`) built this check, so the issue is partly superseded: the job already refuses a forward-read plan. What is left is the creating group in the text.
- Run on the base of the new test: a plan with group 1 that reads `tests/test_new.py` and group 3 that creates it gives the problem "Group 1 names `tests/test_new.py` in `reads`. The staged commit has no such file, and no group up to group 1 creates it. No file has this name. Name a file that exists, or make the group that creates it list it in `creates`." The text names no later group, and its tail ("make the group that creates it list it in `creates`") misleads the model, because a later group does list it. The test fails on the base.
- `path_problems` reports the sentence once for a path, at its first place, so one creating group is enough. The second call site in `stage.py` calls the same function, so it needs no change.

## Existing Tool Considered

No open, maintained tool covers this project-specific validation of plan group ordering. The project keeps the check in its own `path_problems` function in `src/devops_cli/roadmap/stage_paths.py`, which #3010 already added. The written cost is one small pure function, two test cases and the maintenance of the message text; the cost is already paid, and this change adds one lookup and one message sentence.
