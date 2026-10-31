# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The repos, branches, GitHub, SSH, devcontainer, OpenTofu, and OpenSpec tests still start a real `git` binary. The audit of 2026-10-24 recorded 62 tests across 10 files that start `git`:
- `tests/commands/test_repos.py`
- `tests/git/test_repos_worktrees.py`
- `tests/commands/test_branches.py`
- `tests/github/test_github_pr_monitor.py`
- `tests/github/test_github_metrics.py`
- `tests/crypto/test_ssh.py`
- `tests/commands/test_devcontainer.py`
- `tests/commands/test_tf.py`
- `tests/core/test_openspec_command.py`
- `tests/commands/test_openspec_scaffold.py`

Issue #2146 delivered the `git_fake` fixture. These tests must reach `git` through `git_fake` or pure-Python directory fixtures and start no program.

## What Changes

- Tests in the 10 files above reach `git` through `git_fake` and filesystem structures instead of real `git` subprocesses.
- Fixtures and helpers that invoke `git init`, `git add`, `git commit`, `git worktree`, etc. are converted to write `.git` structures directly or script responses in `git_fake` and `process_fake`.
- Tests patch no `devops_cli` names.
- Zero tests in these 10 files start a real `git` subprocess.
- The pull request records execution duration before and after the change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/commands/test_repos.py`: Replace real git invocations and remove internal patches with `git_fake`.
- `tests/git/test_repos_worktrees.py`: Replace git fixture and commands with pure-Python worktrees and `git_fake`.
- `tests/commands/test_branches.py`: Replace git helper calls with `git_fake`.
- `tests/github/test_github_pr_monitor.py`: Replace any remaining git process calls with `git_fake`.
- `tests/github/test_github_metrics.py`: Replace real git tag repository builder with pure-Python structure and `git_fake`.
- `tests/crypto/test_ssh.py`: Replace `git init` and git config calls with pure-Python fixtures and `git_fake`.
- `tests/commands/test_devcontainer.py`: Use `git_fake` for git config reads.
- `tests/commands/test_tf.py`: Use pure-Python `nested_worktree` and replace internal patches with `process_fake`.
- `tests/core/test_openspec_command.py`: Avoid starting git during OpenSpec scenario builds.
- `tests/commands/test_openspec_scaffold.py`: Check gitignore rules without spawning git subprocesses.

## Feasibility

Checked on 2026-10-31:
- `git_fake` in `tests/support/fakes/git.py` intercepts `run_subprocess` calls for git.
- `nested_worktree` in `tests/commands/test_tf.py` uses git subprocesses from `tests/support/git_scenarios.py`; providing a pure-Python worktree removes 8 git starts.
- `tests/git/test_repos_worktrees.py` creates worktrees with git; simulating worktrees with git metadata files (`.git/worktrees/<name>/gitdir` and worktree `.git` file) enables testing `repos worktrees status` and `prune` hermetically.
- Baseline test duration: 404 tests pass in 25.36s (36.12s total).

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` and `process_fake` in `tests/support/fakes/process.py` provide hermetic seams. No new tool is needed.
