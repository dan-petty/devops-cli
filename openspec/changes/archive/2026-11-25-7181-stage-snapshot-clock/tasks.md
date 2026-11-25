# Tasks

## 1. Behavior

- [x] 1.1 Reproduce the wall-clock failure on `origin/main` with `pytest`
  - Verification: `$ uv run pytest -n 0 tests/roadmap/stage/test_roadmap_stage_github_snapshot.py::test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues -q`
- [x] 1.2 Freeze `NOW` around `run_stage_agent` with `time_machine.travel(NOW, tick=False)` and verify all snapshot tests pass
  - Verification: `$ uv run pytest -n 0 tests/roadmap/stage/test_roadmap_stage_github_snapshot.py -q`

## 2. Verification

- [x] 2.1 Archive the OpenSpec change and pass local CI gates
  - Verification: `$ uv run devops ci --check --no-cache --skip test,outdated`
