# Tasks

## 1. Add the parallel limit setting

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `docs/CLUSTER.md`. Changes: `src/devops_cli/config/settings.py`, `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `docs/CLUSTER.md`.

- [ ] 1.1 the case `test_the_parallel_limit_defaults_to_one` in `tests/roadmap/implement/test_roadmap_implement_size.py`, which asserts that the setting is 1 and that `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` sets it, fails first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` fails on the base
- [ ] 1.2 Write the failing case first. Add the field `max_parallel_jobs: Annotated[int, Variable()] = Field(...)` with the default 1, `ge=1` and a description to `RoadmapImplementConfig` in `src/devops_cli/config/settings.py`, beside `max_memory_limit`, which the round already reads. Add `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` to `_VARIABLES_OF_LATER_SETTINGS` in `tests/security/test_config_declarations.py`, the set at line 135 that holds each variable of a later setting
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` passes
- [ ] 1.3 Edit `docs/CLUSTER.md` to name `roadmap.implement.max_parallel_jobs`, its default of 1, and the disjoint-file rule of the implement row
  - Verification: `$ uv run devops ci docs` passes

## 2. Regenerate the settings documents

Kind: other. Reads: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `src/devops_cli/config/settings.py`. Changes: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [ ] 2.1 Run `uv run devops docs generate`, so `docs/ENV_VARS.md` lists `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` with the description of the field, and the `RoadmapImplementConfig` row of `docs/CONFIGURATION.md` lists `max_parallel_jobs=1`. Commit the generated text as the generator wrote it, and edit no row by hand
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 3. Decide which plans conflict

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/implement/implement_parallel.py` (new), `tests/roadmap/implement/test_implement_parallel.py` (new).

- [ ] 3.1 the case `test_two_items_that_share_a_path_conflict` in `tests/roadmap/implement/test_implement_parallel.py` fails first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel.py` fails on the base
- [ ] 3.2 Write the failing cases first. Add `change_files(tasks_md)` to `src/devops_cli/roadmap/implement/implement_parallel.py`: the `changes` of `group_files` over each group of `parse_task_groups`, and an empty set when a group has no `Reads:` and `Changes:` line. Add `conflicts(one, other)`: true when either set is empty, and true when a path of one set equals, is the parent of, or is the child of a path of the other set
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel.py` passes

## 4. Create up to N Jobs for disjoint items

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/roadmap/stage/stage_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`. Changes: `src/devops_cli/roadmap/implement/implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`.

- [ ] 4.1 the cases `test_two_disjoint_items_of_one_repository_get_two_jobs`, `test_two_items_that_share_a_path_get_one_job` and `test_two_items_whose_plans_name_no_change_file_get_one_job` in `tests/roadmap/implement/test_roadmap_implement_submit.py` fail first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` fails on the base
- [ ] 4.2 Write the failing cases first, with `config(roadmap={"implement": {"max_parallel_jobs": 2}})` and two Staged items whose branches add a file and whose tasks name it in `Changes:` (`push_staged_branch` takes the tasks text and the files). In `run_implement_round`, read the setting, count the Jobs of the repository label that have not ended, take `slots = max(limit - running, 0)` and return `waiting` when it is 0; plan with `limit=slots`; read the tasks of each selected target once with `_tasks_of`, and use them for `runner_size(plan_file_count(tasks))` and for `change_files`; skip a target whose number a running Job carries in `ITEM_LABEL`; create one Job for each target whose change set `conflicts` with none of the taken sets, and add `ITEM_LABEL` beside the repository label; set `created` to the last Job created and `left` to the first item whose create returned None; delete `_runs` and the wait it holds; update the module docstring
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` passes

## 5. Prove that two disjoint branches merge

Kind: other. Reads: `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/core/process.py`, `tests/support/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_planned.py`. Changes: `tests/roadmap/implement/test_implement_parallel_merge.py` (new).

- [ ] 5.1 Add the case `test_two_branches_of_disjoint_files_merge`: it answers the `git` program on `process_fake` with `git_for_real`, builds a repository under `tmp_path` through `run_subprocess`, commits one file on each of two branches from one base commit, asserts that `conflicts` of the two change sets is false, merges one branch into the other, and asserts that the merge exits 0 and that the merged tree holds both changes
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel_merge.py` passes

## 6. State the rule in the glossary

Kind: other. Reads: `CONTEXT.md`, `docs/CLUSTER.md`. Changes: `CONTEXT.md`.

- [ ] 6.1 Rewrite the Runner term: the Service creates one Job for one item, may create several Jobs for one repository when their change file sets are disjoint, and creates no second Job for an item. The term states the rule today at `CONTEXT.md:150:` `creates no second Job for a repository while one runs`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 Edit `CONTEXT.md` to state the per-item Job rule and the disjoint-file rule in the Runner term
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: A replay with two items of disjoint files starts two Jobs; two items that share a file start one.
- Group 1: N is a setting (default 1).
- Group 4: The GitHub request budget and the model lane limit still hold.
- Group 5: A test proves that a merge conflict between two Jobs of one round cannot happen for disjoint files.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
