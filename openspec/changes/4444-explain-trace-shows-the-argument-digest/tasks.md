# Tasks

## 1. Behavior

Reads: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `tests/roadmap/test_roadmap_explain.py`. Changes: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`.

- [x] 1.1 Add the tests: the line of a tool call shows `[argument <digest>]` after the program, two calls with the same digest show the same digest, and a tool event with no digest shows no argument part. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py`
- [x] 1.2 Add `explain_trace_tool_digest` to `RoadmapMessages`, put `{digest}` after `{program}` in `explain_trace_tool`, and fill it from the `digest` field in `_event_line`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py`

## 2. Documents

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 Say in `docs/roadmap/implement.md` that a tool call in the trace holds the digest of its argument, so a reader sees a repeated call
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The line of a tool event in `explain --trace` shows the digest of its argument when the event holds one, and no argument part when it holds none.
