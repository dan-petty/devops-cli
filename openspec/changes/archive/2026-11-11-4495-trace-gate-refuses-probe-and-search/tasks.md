# Tasks

## 1. Read the subject and the object of a read word

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, assert with table-driven cases that a read whose subject is the plan, a group, a test case, the probe or code, a `read-only` word, and a read whose object is in another clause make no claim, and that a claim of the run, a passive, a noun read and a pronoun object stay refused
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, find the subject and the object of each read word in `_uncalled_path`, and do not match `read` before a hyphen
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py tests/roadmap/stage/test_roadmap_stage_trace_spans.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/stage/stage_change.py`, end the object of a read at a verb of its result, judge the last path before the read when its object has no path, and assert the plan sentence of #3252 with a trace of each of its paths in `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py` fails before the change and passes after it

## 2. Count a search match line as seen

Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/ai/client/test_roadmap_agent_run.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`.

- [x] 2.1 Assert that `TraceFacts.of` holds the `path:line` of each `search_code` and `callers` match line and of no other answer, that a citation of a match line passes while a bare path, another line and a range stay refused, and that the kept plan file holds the cited match lines
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py tests/roadmap/stage/test_roadmap_stage_trace_spans.py tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py` fails on the base
- [x] 2.2 Add `ToolCallRecord.matches`, `TraceFacts.lines` and `PlanFacts.lines`, join them in `_trace_facts`, and accept a cited match line in `_was_seen`
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py tests/roadmap/stage/test_roadmap_stage_trace_spans.py tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py` passes

## 3. Keep the golden replay

- [x] 3.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## 4. Documents

- [x] 4.1 In `docs/roadmap/stage.md`, state how the trace gate reads a read claim and what the kept plan facts hold
  - Verification: `$ uv run devops ci docs`
