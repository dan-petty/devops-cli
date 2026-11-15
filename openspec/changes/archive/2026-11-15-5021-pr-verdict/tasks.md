# Tasks

## 1. Behavior

- [x] 1.1 Write tests for `verdict(state)` table and state outcomes
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_watch.py`
- [x] 1.2 Write tests for empty checks (#4927) and failed read retry (#4838)
  - Verification: `$ uv run pytest tests/github/test_pr_monitor_empty_checks.py`
- [x] 1.3 Write tests for `steps/ready.py` and `mark_ready`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_ready.py`
- [x] 1.4 Write tests for CLI commands `roadmap step watch` and `roadmap step ready`
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_watch.py tests/commands/test_roadmap_step_ready.py`
- [x] 1.5 Implement `src/devops_cli/roadmap/steps/watch.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_watch.py`
- [x] 1.6 Implement `src/devops_cli/roadmap/steps/ready.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_ready.py`
- [x] 1.7 Implement CLI commands in `src/devops_cli/commands/roadmap_step_watch.py` and `roadmap_step_ready.py`
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_watch.py tests/commands/test_roadmap_step_ready.py`
- [x] 1.8 Unify callers across `implement_pull.py`, `stage_ready.py`, `pr_conflicts.py`, `pr_monitor.py`, `pr.py`
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/stage/test_roadmap_stage_ready.py tests/commands/test_pr_cmd.py`
- [x] 1.9 Add structural architectural invariant ensuring only `steps/ready.py` wraps `gh pr ready`
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py -k pr_ready`

## 2. Verification

- [x] 2.1 Verify fail-to-pass gate on base `origin/main`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Verify full local CI
  - Verification: `$ uv run devops ci`

## 3. Documents

- [x] 3.1 Update CLI reference documentation
  - Verification: `$ uv run devops docs generate && uv run devops docs check`
