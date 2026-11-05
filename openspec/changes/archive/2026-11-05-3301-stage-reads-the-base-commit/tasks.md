# Tasks

## 1. Read the default branch of origin as the staged commit

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/stage_tools.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 1.1 Add a test to `tests/roadmap/test_roadmap_stage_plan.py` named `test_a_path_that_origin_main_adds_after_the_clone_head_is_present`. A second clone pushes `src/devops_cli/new_role.py` to `origin` after the stage clone was made. An issue that cites that path gets the probe line that says the path is a file of the staging commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base, and the failure is the probe line that says the path is missing
- [x] 1.2 Add tests to `tests/roadmap/test_roadmap_stage_plan.py` named `test_the_stage_job_moves_the_clone_to_the_staged_commit` and `test_a_clone_that_cannot_fast_forward_fails_the_run_and_asks_the_model_nothing`. The first asserts that HEAD of the clone equals the commit of `origin/main` after a plan. The second asserts that a clone with a commit that `origin` lacks raises the error and asks the model nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base for both tests
- [x] 1.3 Read the staged commit as `origin/<default branch>` after the fetch in `read_stage_selection` in `src/devops_cli/roadmap/stage.py`, keep the origin check, and move the clone with `git merge --ff-only` in `plan_stage` when an item is selected
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Start a staged branch at the staged commit

Reads: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/stage.py`, `tests/core/test_repos_worktrees_add.py`. Changes: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/stage.py`, `tests/core/test_repos_worktrees_add.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 2.1 Add a test to `tests/core/test_repos_worktrees_add.py` named `test_add_worktree_starts_the_branch_at_the_given_base`. The test passes an older commit of `main` as `base` to `add_worktree` and asserts that the new branch points at that commit
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py` fails on the base
- [x] 2.2 Add a `base` argument to `add_worktree`, `_commands` and `_create` in `src/devops_cli/git/worktree_add.py`. The argument defaults to `None`, which keeps `origin/main` as the start. The take-over path keeps the tip of the pushed branch
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py` passes
- [x] 2.3 Add a test to `tests/roadmap/test_roadmap_stage_apply.py` named `test_a_staged_branch_starts_at_the_staged_commit_when_origin_moves_on`. The branch of a staged item has the staged commit of the plan as its parent, when `origin/main` moved after the plan
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails on the base
- [x] 2.4 Pass `plan.sha` through `apply_stage`, `_stage_one` and `_worktree` in `src/devops_cli/roadmap/stage.py` to `add_worktree` as `base`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/core/test_repos_worktrees_add.py` passes

## 3. Document the staged commit

Reads: `src/devops_cli/roadmap/stage.py`, `docs/commands/roadmap.md`. Changes: `src/devops_cli/roadmap/stage.py`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`.

- [x] 3.1 Update the docstring of `plan_stage` in `src/devops_cli/roadmap/stage.py`. It names the fetched default branch as the staged commit and says that the job moves the clone to it. Remove the words that say the plan writes nothing to git
  - Verification: `! git grep -n "without a write to git or to GitHub" src/devops_cli/roadmap/stage.py`
- [x] 3.2 Regenerate the command documents with `uv run devops docs generate --sync-readme`, if the docstring of a documented command changed
  - Verification: `uv run devops ci docs` passes

## 4. Name the staged commit in the report

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 4.1 Add a test to `tests/roadmap/test_roadmap_stage_apply.py` named `test_the_report_names_the_staged_commit_that_the_probe_read`. The plan has the commit of `origin/main` after the fetch, and the text of `render_stage_plan` names that commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` fails before the change of 4.2
- [x] 4.2 Add the line `The staged commit is {sha}.` to `render_stage_plan` in `src/devops_cli/roadmap/stage.py` when the plan holds a commit, with the message `stage_staged_commit` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py` passes

## 5. Keep the dry run in step with the run

Reads: `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 5.1 Add a test to `tests/roadmap/test_roadmap_dry_runs.py` named `test_the_stage_plan_moves_the_clone_to_the_staged_commit_and_starts_each_branch_there`. The dry run lists the merge that moves the clone before the tracked files are read, and the worktree of each item that starts at the staged commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` fails before the change of 5.2
- [x] 5.2 List the move of the clone and the staged commit as the start of the worktree in `stage_requests` in `src/devops_cli/roadmap/request_plan.py`, with the messages of `stage_requests` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py` passes

## 6. Refuse a clone that is ahead of origin

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 6.1 Add a test to `tests/roadmap/test_roadmap_stage_plan.py` named `test_a_clone_ahead_of_origin_fails_the_run_and_asks_the_model_nothing`. A clone with a commit that `origin/main` lacks, and no commit of `origin/main` that it lacks, raises the error and asks the model nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py -k ahead_of_origin` fails before the change of 6.2, and the failure is that no error is raised
- [x] 6.2 Check in `_move_clone` in `src/devops_cli/roadmap/stage.py` that HEAD is the staged commit after the fast-forward, because git merges a clone that is ahead as up to date and keeps its HEAD. Otherwise raise `GitOperationError` with the message `stage_clone_ahead` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
