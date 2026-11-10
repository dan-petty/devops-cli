# Tasks

## 1. Judge the path of a citation in the trace gate

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/agent_run.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, assert that a claim in the form `path:line:text`, `path:def name`, `./path` or the end of a path passes when the run read the file, that a claim of an unread path in any of these forms is refused with the path alone, and that the word `read` inside a quoted line makes no claim
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py` fails on the base
- [x] 1.2 In `_uncalled_path` of `src/devops_cli/roadmap/stage/stage_change.py`, judge the path of the citation, accept a read path that ends with the claimed path, and search the sentence for a verb of reading outside its code spans
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py` passes

## 2. Keep the golden replay

Reads: `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Changes: none.

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
