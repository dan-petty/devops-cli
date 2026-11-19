# Tasks

## 1. Give a git child that reaches a remote the credential helper

Kind: behavior. Reads: `src/devops_cli/core/process.py`, `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_boundary.py`, `tests/core/test_process.py`, `tests/support/github_identity.py`. Changes: `src/devops_cli/core/process.py`, `tests/core/test_subprocess_env_boundary.py`.
Adds: `git_credential_args`

- [ ] 1.1 Write `test_a_network_git_child_gets_the_credential_helper` in `tests/core/test_subprocess_env_boundary.py` for the scenarios `The reproduction form with a token` and `A fetch with prune`: it runs `git -C <clone> ls-remote --heads origin main` and `git fetch --prune origin` through `run_subprocess`, and asserts that each recorded argv holds the two `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` after `git` and before the subcommand, with the session's token in the environment of the child. Write `test_a_local_git_child_gets_no_credential_helper` in the same module for the scenario `A local status`, and assert that `git status` records no `-c` value and no `GH_TOKEN`. Update the three assertions that compare the recorded argv of a network git child in `test_a_lookup_that_cannot_run_leaves_git_working_and_says_why`, `test_gh_and_git_children_get_only_the_pinned_token` and `test_git_runs_without_a_token_when_gh_has_no_login`
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py` fails on the base
- [ ] 1.2 Add `git_credential_args` to `src/devops_cli/core/process.py`: it returns `["-c", value, "-c", value]` from `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` when `_github_client_name` names git and `git_reaches_remote(cmd[1:])` is true, and an empty list otherwise. In `DefaultProcessRunner.run`, insert the result at index 1 of `full_cmd` right after `pin = _github_pin(full_cmd, env)`, and do the same in `run_async` after its `asyncio.to_thread` call, so the pin reads the caller's own words. Extend the docstring of `_github_pin`: a git child that reaches a remote gets the token and the helper together
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py` passes

## 2. Read origin before worktrees add reclaims

Kind: behavior. Reads: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `tests/git/test_repos_worktrees_reclaim.py`, `tests/git/conftest.py`, `tests/roadmap/implement/test_roadmap_implement_git_isolation.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_repos.py`, `tests/core/test_repos_worktrees_add.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/steps/test_roadmap_step_scaffold.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_faults.py`. Changes: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `tests/git/test_repos_worktrees_reclaim.py`.
Adds: `PreReadOrigin`

- [ ] 2.1 Write `test_a_failed_read_of_origin_removes_no_worktree` in `tests/git/test_repos_worktrees_reclaim.py` for the requirement `The run reads origin before the reclaim` and its scenario `The read of origin exits 128`: it adds a merged worktree under the managed folder, sets `origin` of the clone to a path that does not exist, runs `add 2345 --type feat --slug next` through `_add`, and asserts that the command exits 1, that the merged worktree stays, that `w-2345` does not exist, that `git rev-parse HEAD` of the clone is the same as before the run, that the GitHub fake got no request, and that the error names `git ls-remote --heads origin` with no `-c` value. The existing `test_add_removes_a_merged_worktree_and_creates_the_new_one` covers the scenario `The read of origin succeeds`
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim.py` fails on the base
- [ ] 2.2 Add `PreReadOrigin` to `src/devops_cli/git/worktree_add.py`: it implements `OriginReads`, `heads` returns the output of one earlier `read_remote_heads`, and `fetch` runs `_CloneOrigin(repo_root).fetch`. In `worktrees_add` in `src/devops_cli/commands/repos.py`, build it from `read_remote_heads(root)` when `reclaim` is true and `is_plan` is false, before the `reclaim_merged_worktrees` call, import `read_remote_heads` beside `add_worktree`, and pass it as `origin=` to `add_worktree`. In `_run` of `src/devops_cli/git/worktree_add.py`, name the failed command from the words after the `-c` values and the `-C <path>` prefix, so the message keeps its form. Extend the docstring of `worktrees_add`: the command reads `origin` before it reclaims, so a failed read removes no worktree and leaves HEAD as it was
  - Verification: `$ uv run devops ci test tests/git/test_repos_worktrees_reclaim.py` passes

## 3. Regenerate the command page of repos

Kind: other. Reads: `docs/commands/repos.md`, `src/devops_cli/commands/repos.py`. Changes: `docs/commands/repos.md`.

- [ ] 3.1 Run `uv run devops docs generate` after the docstring change of the previous group, and keep the regenerated `docs/commands/repos.md`, whose text of `worktrees add` now says that the command reads `origin` before it reclaims the merged worktrees. Change no text of the page by hand
  - Verification: `$ uv run devops ci --check --only docs` passes
- [ ] 3.2 Regenerate `docs/commands/repos.md` with `uv run devops docs generate` from the new docstring of `worktrees add`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a git child that reaches a remote gets the credential helper of the session. It fails on `main` (`devops ci fail-to-pass`).
- Group 2: A test: when the read of `origin` fails, `worktrees add` removes no worktree and does not change the HEAD of the clone.
- Pending person: A live run of `devops repos worktrees add` on a clone of a private repository creates the worktree., The live run needs a clone of a private repository and the credential of a person, which no test and no runner holds.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
