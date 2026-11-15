# Proposal

## Why

`devops infra onboard`, `status` and `plan` found a checkout at `<repos.base_dir>/<owner>/<name>`, and a relative `repos.base_dir` resolved against the working folder. In a git worktree of devops-cli, the command looked under the worktree and stopped, although the clone is at the main checkout (#5195).

## What Changes

- `default_checkout` resolves a relative `repos.base_dir` under `main_worktree_root()`, as a data path does. An absolute base dir stays as given.
- Add the test `test_a_relative_base_dir_resolves_under_the_main_worktree` in `tests/commands/test_infra_onboard.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-onboard`: a relative repos base dir resolves under the main worktree.

## Impact

- Code: `src/devops_cli/infra/onboard.py`
- Tests: `tests/commands/test_infra_onboard.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/infra/onboard.py:85:def default_checkout(` calls `Path.resolve()`, which reads the working folder.
- `src/devops_cli/core/repo.py:283:def main_worktree_root(` follows the `commondir` of a linked worktree to the main checkout, and a data path already uses it.
- `uv run pytest tests/commands/test_infra_onboard.py tests/infra` passes after the change.

## Existing Tool Considered

The repository already holds `main_worktree_root`. The change adds one branch: about 500 tokens to build and 50 a quarter to keep.

## Dependencies

None.
