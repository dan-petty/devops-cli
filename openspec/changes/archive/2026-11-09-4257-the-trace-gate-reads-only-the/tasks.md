# Tasks

## 1. Read the calls of every plan run

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`.

- [x] 1.1 Add failing tests: a claim of the first run holds after the return; the facts hold every plan run; a review run supports no claim
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_runs.py`
- [x] 1.2 Add `RunTrace.row`, set it in `ToolboxClient` with `PLAN_ROW` and `REVIEW_ROW`, and build the facts of `_trace_facts` from the plan runs
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_runs.py`
- [x] 1.3 Mark the runs of the trace tests of the gates with `PLAN_ROW`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py`

## 2. Check the golden set and the specs

- [x] 2.1 Replay the golden set of the stage eval through the gates
  - Verification: `$ uv run devops roadmap eval stage --replay`
- [x] 2.2 Validate the specs
  - Verification: `$ uv run devops openspec check`
