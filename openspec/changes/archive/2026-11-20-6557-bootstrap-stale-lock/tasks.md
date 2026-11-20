# Tasks

## 1. Behavior

- [x] 1.1 A bootstrap without `locked` runs `uv sync --frozen` and `npm install --no-save`, and syncs offline from a seed that fits
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.2 The implement Job of a staged item with stale locks writes no tracked file before its first step and does not stop, also when each plain `uv run` locks again
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py`
- [x] 1.3 The model fix of fix-checks syncs with `--frozen`, and on a branch with stale locks it reaches its first model request
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 1.4 Each `pre-commit` command of the Job runs as `uv run --frozen`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_hooks.py`
