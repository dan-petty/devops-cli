# Tasks

## 1. Make tool call ordering deterministic in step trace test

Kind: other. Reads: `tests/roadmap/implement/test_roadmap_implement_step_trace.py`, `tests/support/model_script.py`, `src/devops_cli/roadmap/implement/implement_trace.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_step_trace.py`.

- [x] 1.1 Split `tool_calls(same, same, other)` at `tests/roadmap/implement/test_roadmap_implement_step_trace.py:193` into `tool_calls(same), tool_calls(same), tool_calls(other)` so the three calls run in order without concurrency races
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_trace.py --repeat 3` passes
- [x] 1.2 Validate the change folder and static checks (`lint`, `format`, `typecheck`, `test-tree`)
  - Verification: `$ uv run devops ci --check --no-cache --only lint,format,typecheck,test-tree` passes
