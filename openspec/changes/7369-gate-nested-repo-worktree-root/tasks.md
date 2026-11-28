# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for nested clone worktree gate root, stale worktree exit-128 fallback, non-git directory exit 1, and gate-root-keyed cache and coverage index paths
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops ci test tests/commands/test_ci.py tests/ci/test_ci_cache.py`
- [x] 1.2 Implement `find_gate_root` in `src/devops_cli/core/repo.py`, `not_in_work_tree` in `src/devops_cli/lang/en/messages.py`, update `_get_project_root` / `all_checks` in `src/devops_cli/commands/ci.py`, and key `resolve_ci_cache_path` by `find_gate_root` in `src/devops_cli/ci/cache.py`
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops ci test tests/commands/test_ci.py tests/ci/test_ci_cache.py tests/commands/test_repos.py`

## 2. Documents and Quality Gate

- [x] 2.1 Validate OpenSpec artifacts and docs and run local static checks
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops openspec check && UV_COMPILE_BYTECODE=0 uv run devops ci docs && UV_COMPILE_BYTECODE=0 uv run devops ci --check --only lint,format,domain,test-tree,constructs,startup-imports,swallowed-failures`
