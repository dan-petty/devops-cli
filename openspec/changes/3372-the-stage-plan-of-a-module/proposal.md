# Proposal

## Why

The plan of a module move in #3372 passes the stage gates while it leaves top-level job modules in place, so the layout test of the plan fails on the tree that the plan produces. One sampled import for each group hides the omission.

## What Changes

- `check_proposal` reads a move of a Python module by name prefix from the old path in `changes` and the new path under `<folder>/<prefix>/` in `creates`
- `check_proposal` requires every top-level Python module of that prefix in the folder in the group `changes` or in a later group, and reads no test module and no `conftest.py`
- `check_proposal` refuses a move group whose `! git grep` verify literal equals the import path of one module of the prefix, the bare prefix included
- The stage prompt asks the planner to list every module of a moved prefix and to verify the prefix, not one sample
- A new test module asserts both refusals and the accepted later group
- The roadmap-stage spec gains the three requirements of the check and the prompt
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A move group names every module of its prefix, A move group verifies the whole prefix, The stage prompt asks for every module of a prefix

## Impact

- Code: `src/devops_cli/roadmap/stage_move.py`, `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_move_prefix.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The context holds `src/devops_cli/roadmap/stage_change.py`, and its `check_proposal` calls `_delta_problems`, `content_problems`, `form_problems`, `path_problems` and `criterion_problems`, and no prefix coverage check.
- The context holds `src/devops_cli/ai/tasks/roadmap_stage_change.md`, whose rules ask for one `verify` command for each group and name no prefix coverage.
- The probes report the bare names as no file: `The path `stage_ready.py` is no file of the staging commit. No commit in the history deleted or renamed it.` The context shows `src/devops_cli/roadmap/stage_ready.py` and `src/devops_cli/roadmap/stage_verify.py`, so the prefix `stage` has the modules that the new check reads.
- A search for `devops_cli.roadmap.stage` finds `from devops_cli.roadmap.stage import` and, after the move, `devops_cli.roadmap.stage.ready`. The literal therefore names the module `stage.py` and the new subpackage at once, so the check refuses it. A search for `devops_cli.roadmap.stage_` finds the dotted imports of the moved modules and no new path, so the check accepts it.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_move_prefix.py`, then `uv run devops ci test tests/roadmap`, then `uv run devops openspec check`.

## Existing Tool Considered

The tree walk of `StagedTree` in `src/devops_cli/roadmap/stage_paths.py` and the `git mv` that the groups run cover the need, so the change adopts no new tool. It deletes no code.
