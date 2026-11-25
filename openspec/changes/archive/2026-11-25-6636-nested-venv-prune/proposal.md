# Proposal: #6636

## Why
`CONST_WORKTREE_REGENERABLE_PATHSPECS` (`src/devops_cli/config/constants.py:794-814`) excludes `.venv` only at the root of a worktree (`:(exclude).venv`), whereas other tool caches (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis`, `node_modules`) use `:(exclude,glob)**/<name>/**` to match at any depth. In service repositories whose `uv` project lives under a subdirectory (such as `services/<name>/.venv`), `count_ignored_data_files` (`src/devops_cli/git/worktree_inventory.py:243`) counts every file in the nested virtual environment as ignored data, blocking `devops repos worktrees prune` and `worktrees add --reclaim`.

## What Changes
- Change the `.venv` exclude pathspec in `CONST_WORKTREE_REGENERABLE_PATHSPECS` (`src/devops_cli/config/constants.py`) to `:(exclude,glob)**/.venv/**` (matching `.venv` at any depth while leaving `dist`, `build`, and `htmlcov` root-only).
- Update `openspec/specs/repos-worktrees-prune/spec.md` so `.venv` is listed among the regenerable paths excluded at any depth.
- Add tests in `tests/git/test_repos_worktrees_reclaim_scope.py` covering nested `.venv` exclusion, data files beside nested `.venv`, nested `build` directories staying counted as data, and `prune` preview behavior.

## Capabilities
- Modified: `repos-worktrees-prune`

## Impact
- `src/devops_cli/config/constants.py`
- `openspec/specs/repos-worktrees-prune/spec.md`
- `tests/git/test_repos_worktrees_reclaim_scope.py`

Fits in one pull request.

## Feasibility
Confirmed on `origin/main`:
- `src/devops_cli/config/constants.py:794-814` defines `:(exclude).venv` without `**/`.
- `src/devops_cli/git/worktree_inventory.py:259-272` passes `*CONST_WORKTREE_REGENERABLE_PATHSPECS` straight to `git ls-files --others --ignored --exclude-standard -z -- .`.
- `openspec/specs/repos-worktrees-prune/spec.md:133-135` lists `.venv` among root-only exclusions instead of at-any-depth exclusions.

## Existing Tool Considered
Git pathspec glob matching (`git ls-files` with `:(exclude,glob)**/.venv/**`), already used in-repo for `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis`, and `node_modules`. No open external tool replaces `count_ignored_data_files`; the change is a single pathspec string update.
