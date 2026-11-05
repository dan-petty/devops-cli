# Proposal

## Why

`path_problems` serves two readers from one rule set: the stage reply, which has a `creates` list, and the change folder, which has none. When a plan names a new file with no ` (new)` mark on its `Changes:` line, the problem tells the reader to list the file in `creates`, a list that the change folder does not have, so the reader gets no usable fix.

## What Changes

- `MESSAGES.roadmap.stage_problem_path` names the `creates` list of a reply and the ` (new)` mark of the `Changes:` line, and keeps its placeholders and its same-name hint.
- The docstring of `src/devops_cli/roadmap/stage_paths.py` states that `path_problems` judges both the stage reply and the change folder.
- `tests/roadmap/test_roadmap_stage_paths.py` asserts the new message for a missing path, the kept hint and the unchanged later-creator message.
- `tests/roadmap/test_roadmap_plan_check.py` asserts that a change folder whose `Changes:` line lacks the ` (new)` mark reports the new message.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The missing-path message names both forms, The missing-path message keeps its hint, The module docstring names both readers

## Impact

- Code: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_paths.py`
- Tests: `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_plan_check.py`

## Feasibility

- `probes` states "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/stage_paths.py` is a file of the staging commit.", so both paths that the issue cites exist at the staged commit and the premise holds.
- `probes` states "The path `src/devops_cli/new_module.py` is no file of the staging commit." and "The path `src/devops_cli/new/stage.py` is no file at the root of the staging commit.", which are the missing-path examples that the new message must cover, and no work of the issue is already done.
- `read_file` of `src/devops_cli/roadmap/stage_paths.py` showed `_problem` formatting one message with the group, the path, the place and the hint, and the same-name hint appended after it, so one string covers both readers.
- `search_code` for `Name a file that exists` found the one message string and the tests that assert it, so the change edits an existing text and adds no module.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` must show the new message on a missing path and the same-name hint after it.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` must show the new message for a change folder whose `Changes:` line lacks the ` (new)` mark.
- Third check: `uv run devops openspec check` must pass with the spec delta of this change.

## Existing Tool Considered

No open, maintained tool or library covers this need: the change edits one message string and deletes no product code. The written cost to build, keep and fix that text is about 300 tokens and 10 minutes.

## Dependencies

None.
