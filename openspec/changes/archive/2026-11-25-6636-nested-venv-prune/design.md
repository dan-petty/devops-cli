# Design

## Decisions
- Move `:(exclude).venv` in `CONST_WORKTREE_REGENERABLE_PATHSPECS` (`src/devops_cli/config/constants.py`) to the `:(exclude,glob)**/.venv/**` form alongside `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.hypothesis`, and `node_modules`.
- Keep `:(exclude)dist`, `:(exclude)build`, and `:(exclude)htmlcov` rooted at the worktree root so nested `build/` or `dist/` directories remain treated as ignored data unless explicitly permitted.
- Update the comment above `CONST_WORKTREE_REGENERABLE_PATHSPECS` (`constants.py`) and `openspec/specs/repos-worktrees-prune/spec.md` to match the updated rule.

## Rejected alternatives
- Glob `:(exclude,glob)**/build/**` or `**/dist/**` as well: rejected because nested `build/` directories outside the repository root can hold non-cache build outputs or scratch data (`test_scope_refusal_is_unknown_when_git_cannot_open_a_directory` also uses `.data/agent/scratch/dist/` as data).
- Walk directories in Python instead of `git ls-files` pathspecs: rejected because Git already applies `.gitignore` and pathspec globs atomically in one subprocess call.
