# Task: devops branches jira creates the branch instead of failing on checkout -b -- (#900)

**Issue**: [#900](https://github.com/dan-petty/devops-cli/issues/900)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p1-high
**Scope**: scope/cli

## Description

`create_branch` (`src/devops_cli/git/operations.py`) ran `repo.git.checkout("-b", "--", branch_name)`. Git's `-b` takes the next argument as the new branch's name, so git tried to create a branch called `--` starting at `branch_name`, and the call always failed (`fatal: '<name>' is not a commit and a branch '--' cannot be created from it`). Its only caller, `devops branches jira <ticket> [--slug]`, created no branch and printed a traceback, because `GitCommandError` is not the `ValueError` that `jira` catches. A mocked test asserted the broken argv, and the CLI test patched `create_branch` out.

`create_branch` now runs `git checkout -b <name>`. The leading-hyphen guard already stops the name from being read as an option, so no `--` is needed. When git refuses the branch, `create_branch` raises `GitOperationError(operation="branch_create")` with git's reason, which `jira` already catches: the user sees one error line and exit code 1.

The `devops branches` rows of `docs/cheatsheets/git_and_github.md` named commands that do not exist (`branches create`, `branches cleanup`) and behaviour the commands lack (ahead/behind counts, branching from the release branch). They now describe `branches list`, `branches jira` and `branches clean` as they work.

## Acceptance Criteria

- [x] `create_branch` runs `git checkout -b <name>` without `--`, and the leading-hyphen guard and the `BranchAlreadyExistsError` check stay: `tests/test_git_operations.py::test_create_branch`.
- [x] When git refuses the branch, `create_branch` raises `GitOperationError` with `operation="branch_create"` and git's reason as the message: `tests/test_git_operations.py::test_create_branch_raises_gits_reason_when_git_refuses`.
  - GitPython's `GitCommandError` keeps stderr only pre-formatted (`"\n  stderr: '...'"`). So `create_branch` calls `checkout` in GitPython's documented non-raising mode (`with_extended_output=True, with_exceptions=False`) and raises `GitOperationError` from git's raw stderr through `mask_secrets`. That gives the same argv, the typed error, a one-line message and exit 1, with no exception to chain from.
- [x] `test_create_branch` uses a real repository with one commit in `tmp_path`, built with the shared `git` fixture. It asserts that `create_branch(repo, "feat/test")` leaves `feat/test` checked out (`git branch --show-current`), keeps the leading-hyphen check, and checks that an existing branch raises `BranchAlreadyExistsError`. The mocked argv assertion is gone, and the test failed on the old code.
- [x] `jira PROJ-123 --slug "my feature" --repo <repo>` against a real repository exits 0 with `feature/PROJ-123-my-feature` checked out, without patching `create_branch`: `tests/test_branches.py::test_jira_creates_and_checks_out_the_feature_branch`. It failed on the old code.
- [x] `jira PROJ-123 --repo <repo>` in a repository with a branch named `feature` exits 1 through `SystemExit`, prints git's reason (`'refs/heads/feature' exists`) and no traceback: `tests/test_branches.py::test_jira_prints_gits_reason_when_git_refuses_the_branch`. It failed on the old code.
- [x] The new tests run git only on local repositories under `tmp_path`, with no network. They set `-b main` on `git init` and pass their identity through the `git` fixture, so neither the host's `init.defaultBranch` nor its git identity matters.
- [x] `docs/cheatsheets/git_and_github.md` rows 22-24 name `devops branches list [--all]`, `devops branches jira <ticket> [--slug <text>]` and `devops branches clean [--dry-run]` and say what each does. The file no longer mentions `devops branches create` or `devops branches cleanup`.
- [x] `changelog.d/900.md` records the fix under `### Fixed`. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Pending a person: in a scratch repository with one commit run `devops branches jira PROJ-1 --slug smoke`, then `git branch --show-current`; it prints `feature/PROJ-1-smoke`.
