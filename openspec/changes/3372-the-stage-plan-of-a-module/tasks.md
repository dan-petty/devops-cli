# Tasks

## 1. Add the prefix coverage rule to the plan check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_move.py` (new), `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_move_prefix.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_move_prefix.py` with the three scenarios of the missing-module rule, each against a `StagedTree` of the two paths
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` fails on the base
- [ ] 1.2 Add `move_prefix_problems(groups, tree)` to `src/devops_cli/roadmap/stage_move.py`, and call it from `check_proposal` in `src/devops_cli/roadmap/stage_change.py`. A group moves a prefix when an old path in `changes` sits in the folder of the module and its new path in `creates` sits under a subpackage of that folder. The prefix is the old stem up to its first `_`, or the whole stem. Each top-level module of `tree` in that folder whose stem starts with the prefix SHALL appear in the `changes` of that group or of a later group
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` passes

## 2. Refuse a sampled verify command of a move group

Reads: `src/devops_cli/roadmap/stage_move.py`, `src/devops_cli/roadmap/implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/stage_move.py`, `tests/roadmap/test_roadmap_stage_move_prefix.py`.

- [ ] 2.1 Add a case to `tests/roadmap/test_roadmap_stage_move_prefix.py` that gives a move group the verify command `! git grep -n -F devops_cli.roadmap.stage_ready src/ tests/` and expects a problem, and a case with `devops_cli.roadmap.stage` that expects none
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` fails on the base
- [ ] 2.2 Read the literal of a `! git grep` command with `read_negative_search`. Refuse the literal when it equals the import path of one module of the moved prefix, and accept the literal of the prefix itself. A command of another form stays with `form_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py` passes

## 3. Ask the stage prompt for every module of a prefix

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add a failing test to `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the prompt file and asserts the rule that a group moving a prefix lists every module of it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 3.2 Add a rule to the stage prompt: a group that moves a set of modules by name prefix lists every module of that prefix in `changes`, and its `verify` command covers the whole prefix with one `! git grep` literal
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
