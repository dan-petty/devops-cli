# Tasks

## 1. Read the path of each citation form

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/tools.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, assert with table-driven cases that a `path:N`, `path:N-M` and tool-name citation of a read path passes, that each toolbox tool name before a read path passes, that a listed directory with a trailing `/` passes, that a quoted probe line makes no claim, and that an unread path stays refused in each form
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, add `path:N` and `path:N-M` to `_CITATION_PATH`, remove a toolbox tool name and a trailing `/` in `_claimed_path`, remove a trailing `/` of a read path in `_was_read`, and remove the quoted probe sentences in `_trace_problems`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py tests/roadmap/stage/test_roadmap_stage_trace_subject.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Re-anchor a stale `path:N:text` citation that matches one line at the staged commit: #4479.
- Name the file of the same name in the missing test path problem: #4498.
- The trace gate reads a claim from words that make no claim of the run: #4495.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
