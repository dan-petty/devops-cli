# Tasks

## 1. The caller gives the limits of a run (behavior)

- [x] 1.1 Write a failing test: the default `usage_limits` of `run_step`, `run_fix_step` and `ToolboxClient` equal the guards `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`, `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS`, `CONST_ROADMAP_STAGE_MAX_REQUESTS` and `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py`
- [x] 1.2 Add `usage_limits` to `run_step` and `run_fix_step` in `src/devops_cli/roadmap/implement/implement_step.py`, pass it to each run of the agent, and add `usage_limits` to `ToolboxClient` in `src/devops_cli/roadmap/stage/stage_toolbox.py`. The MCP test that calls `_attempt` in `tests/roadmap/test_roadmap_mcp.py` passes it too.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_mcp.py`

## 2. The tests of the limits and of the watch run small (other)

- [x] 2.1 Give the tests that reach a limit small limits: `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step_repair.py` and `tests/roadmap/stage/test_roadmap_stage_toolbox.py`. Each of these tests reaches its limit in 12 model requests or fewer.
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/implement/test_roadmap_implement_step_repair.py tests/roadmap/stage/test_roadmap_stage_toolbox.py --no-cov --durations=15`
- [x] 2.2 Set `roadmap.implement.monitor_timeout_seconds` to `WATCH_SECONDS`, three poll intervals, in the implement world of `tests/support/roadmap_implement.py`. A watch that waits out the monitor polls the pull request 4 times. The watch tests of `tests/core/test_roadmap_implement_checks.py` read `WATCH_SECONDS`.
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_phase_marks.py tests/roadmap/implement/test_roadmap_implement_typed_result.py tests/core/test_roadmap_implement_checks.py --no-cov --durations=15`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
