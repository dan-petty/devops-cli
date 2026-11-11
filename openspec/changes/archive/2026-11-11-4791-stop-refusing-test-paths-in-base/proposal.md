# Proposal: #4791

## Why

The stage gate refuses a plan for a test path that the plan did not write. `_stale_test_path_problems` read the docstrings of each changed `.py` file at the staged base commit and refused each `tests/...py` path in them that names no file of the commit. The plan cannot change the base text, so no repair reply can remove the problem, and the item fails. On 2026-11-11 this problem refused 4 of 11 stage items, and it was the only problem left after the repair of #3398 and #4401. Closes #4791.

## What Changes

- `check_proposal` reads test paths only from the specs of the plan. It does not read the docstrings of a changed file at the base commit.
- The refusal message and the same-name hint stay as they are for a spec that names a missing test file.
- The refusal list of a plan changes, so the change has a spec delta: the requirement is removed and a new one is added.
- The change fits one pull request.

## Capabilities

- `roadmap-stage`: the requirement "A test path in a docstring or a spec names a file of the commit" is removed, and "A test path in a spec of the plan names a file of the commit" is added.

## Impact

- `src/devops_cli/roadmap/stage/stage_change.py`: `_stale_test_path_problems` takes no `read_text`, and `_docstrings_in` is deleted.
- `tests/roadmap/stage/test_roadmap_stage_form.py`: a new test for the base docstring, and the same-name hint tests use a spec path.
- No setting, constant, message, document or dependency changes. The other gates that use `read_text` (citations) do not change.

## Feasibility

- `origin/main` at 84df338e, `stage_change.py`: `_stale_test_path_problems` added `_docstrings_in(read_text(path))` for each changed `.py` file. `read_text` reads the staged base commit.
- A replay of `missing_test_paths` over the base docstrings of the changed files of each refused plan gives exactly the paths of the refusal texts (#4401, #3398, #4472, #2530). The last reply of each plan holds none of these paths.
- A scan of the docstrings of all tracked `.py` files on `origin/main` finds 43 test paths in 33 files that name no file. Most are example inputs, such as `tests/test_x.py`, or old locations.
- The new test fails on `origin/main` and passes with the change.

## Existing Tool Considered

No open tool covers a gate of the stage plan. The change deletes internal code and adds none: `_docstrings_in`, the `read_text` loop of `_stale_test_path_problems` and three tests of the docstring scan.
