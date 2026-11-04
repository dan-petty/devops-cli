# Tasks

## 1. Add the prefix coverage rule to the plan check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_move.py` (new), `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_move_prefix.py` (new).

- [x] 1.1 Write `tests/roadmap/test_roadmap_stage_move_prefix.py` with the four scenarios of the missing-module rule, each against a `make_stage_proposal` reply and a `StagedTree` of the paths, so the test reads `check_proposal` and not the helper
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` fails on the base
- [x] 1.2 Add `move_prefix_problems(groups, tree)` to `src/devops_cli/roadmap/stage_move.py`, and call it from `check_proposal` in `src/devops_cli/roadmap/stage_change.py`. A Python module moves by a prefix when its old path `<folder>/<stem>.py` is in `changes`, its stem is `<prefix>` or starts with `<prefix>_`, and a new path in `creates` sits under `<folder>/<prefix>/`. The prefix is the old stem up to its first `_`, or the whole stem. The check reads a `.py` file directly under the folder and skips a name that starts with `test_` and `conftest.py`. Each top-level module of `tree` in the folder whose stem is `<prefix>` or starts with `<prefix>_` SHALL appear in the `changes` of a group
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` passes

## 2. Refuse a sampled verify command of a move group

Reads: `src/devops_cli/roadmap/stage_move.py`, `src/devops_cli/roadmap/implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/stage_move.py`, `tests/roadmap/test_roadmap_stage_move_prefix.py`.

- [x] 2.1 Add cases to `tests/roadmap/test_roadmap_stage_move_prefix.py` that give a move group the verify command `! git grep -n -F devops_cli.roadmap.stage_ready src/ tests/` and expect a problem, `devops_cli.roadmap.stage` and expect a problem, and `devops_cli.roadmap.stage_` and expect none
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` fails on the base
- [x] 2.2 Read the literal of a `! git grep` command with `read_negative_search`. Refuse the literal when it equals the import path of one top-level module of the moved prefix, the bare `<prefix>.py` included. Accept the dotted prefix with the separator, such as `devops_cli.roadmap.stage_`, and accept any `uv run devops` command. A command of another form stays with `form_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` passes

## 3. Ask the stage prompt for every module of a prefix

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 3.1 Add a failing test to `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the prompt file and asserts the rule that a group moving a prefix lists every module of it and gives a check of the prefix
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 3.2 Add a rule to the stage prompt: a group that moves a set of modules by name prefix lists every module of that prefix in `changes`, and its `verify` command covers the prefix with the layout invariant test or with a `! git grep` literal that does not name one module, never one sample
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
