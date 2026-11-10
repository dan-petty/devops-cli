# Tasks

## 1. Judge the subject of reads

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`, assert that a sentence with code as the subject of `reads` or `reading` passes with a trace of no call, and that a claim of the run with no call for the path is refused
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, skip a `reads` or `reading` that has a code span, `it` or `which` as its subject in `_uncalled_path`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_subject.py tests/roadmap/stage/test_roadmap_stage_trace_spans.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
