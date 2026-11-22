# Tasks

## 1. Add the parallel limit setting

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `docs/CLUSTER.md`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/security/test_config_declarations.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `docs/CLUSTER.md`.

- [x] 1.1 The case `test_the_parallel_limit_defaults_to_one` in `tests/roadmap/implement/test_roadmap_implement_size.py`, which asserts that the setting is 1 and that `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` sets it, fails first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` fails on the base
- [x] 1.2 Write the failing case first. Add `DEFAULT_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS: int = 1` to `src/devops_cli/config/defaults.py`. Add the field `max_parallel_jobs` to `RoadmapImplementConfig` in `src/devops_cli/config/settings.py`. Register `DEFAULT_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` in `tests/roadmap/test_roadmap_limit_classes.py` with class `setting`. Add `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` to `_VARIABLES_OF_LATER_SETTINGS` in `tests/security/test_config_declarations.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` passes
- [x] 1.3 Edit `docs/CLUSTER.md` to name `roadmap.implement.max_parallel_jobs`, its default of 1, and the disjoint-file rule of the implement row
  - Verification: `$ uv run devops ci docs` passes

## 2. Regenerate the settings documents

Kind: other. Reads: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `src/devops_cli/config/settings.py`. Changes: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [x] 2.1 Run `uv run devops docs generate`, so `docs/ENV_VARS.md` lists `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS` with the description of the field, and the `RoadmapImplementConfig` row of `docs/CONFIGURATION.md` lists `max_parallel_jobs=1`. Commit the generated text as the generator wrote it, and edit no row by hand
  - Verification: `$ uv run devops ci docs` passes

## 3. Decide which plans conflict

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/implement/test_implement_parallel.py`. Changes: `src/devops_cli/roadmap/implement/implement_parallel.py` (new), `tests/roadmap/implement/test_implement_parallel.py` (new).

- [x] 3.1 The cases `test_two_items_that_share_a_path_conflict` and `test_two_items_that_share_a_capability_spec_conflict` in `tests/roadmap/implement/test_implement_parallel.py` fail first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel.py` fails on the base
- [x] 3.2 Write the failing cases first. Add `change_files(tasks_md, change_path=None)` to `src/devops_cli/roadmap/implement/implement_parallel.py`: extracts paths from `Changes:` lines in `tasks_md`, adds capability spec paths under openspec/specs/ for each capability folder under specs/, and adds generated docs if configuration or commands change. Add `conflicts(one, other)`: returns True if either set is empty, or if paths share an exact match or parent-child hierarchy
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel.py` passes

## 4. Create up to N Jobs for disjoint items

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/k8s/cluster_job.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [x] 4.1 The cases `test_two_disjoint_items_of_one_repository_get_two_jobs`, `test_two_items_that_share_a_path_get_one_job`, `test_two_items_that_share_a_capability_spec_get_one_job`, `test_running_job_does_not_starve_available_slot`, `test_pending_runner_pod_blocks_new_jobs`, and `test_request_budget_and_model_lane_limits_hold` fail first
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` fails on the base
- [x] 4.2 Write the failing cases first. In `src/devops_cli/roadmap/implement/implement_submit.py`, read `max_parallel_jobs`, count running Jobs, and return `waiting` if any running runner Job is Pending (`job.started is None`). Plan items with `limit`, filter out items held by running Jobs (`ITEM_LABEL`) or claims, and take up to `slots` targets that do not conflict with each other or running Jobs. Attach `ITEM_LABEL` to created Jobs. Update `SubmitResult.created` to `tuple[str, ...]` and log all created Jobs in `src/devops_cli/roadmap/run.py`. In `src/devops_cli/roadmap/implement/implement_run.py`, enforce `set_model_call_limit(1)` and install a per-job `RequestBudget`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py` passes

## 5. Prove that two disjoint branches merge

Kind: other. Reads: `src/devops_cli/roadmap/implement/implement_parallel.py`, `src/devops_cli/core/process.py`, `tests/support/implement_step.py`, `tests/roadmap/implement/test_implement_parallel.py`. Changes: `tests/roadmap/implement/test_implement_parallel.py`.

- [x] 5.1 Add the cases `test_two_branches_of_disjoint_files_merge` and `test_two_branches_touching_same_capability_spec_conflict` to `tests/roadmap/implement/test_implement_parallel.py`: answers `git` with `git_for_real`, verifies disjoint changes merge cleanly without conflict, and verifies touching the same capability spec results in a merge conflict caught by the predicate
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_implement_parallel.py` passes

## 6. State the rule in the glossary

Kind: other. Reads: `CONTEXT.md`, `docs/CLUSTER.md`. Changes: `CONTEXT.md`.

- [x] 6.1 Rewrite the Runner term in `CONTEXT.md`: the Service creates one Job for one item, may create several Jobs for one repository when their change sets are disjoint, and creates no second Job for an item while one runs
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: A replay with two items of disjoint files starts two Jobs; two items that share a file start one.
- Group 1: N is a setting (default 1).
- Group 4: The GitHub request budget and the model lane limit still hold.
- Group 5: A test proves that a merge conflict between two Jobs of one round cannot happen for disjoint files.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
