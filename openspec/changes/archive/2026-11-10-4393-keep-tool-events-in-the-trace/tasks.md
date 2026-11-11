# Tasks

## 1. The trace of a long run keeps every kind of event

Reads: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `tests/roadmap/implement/test_roadmap_implement_step_trace.py`, `tests/roadmap/implement/test_roadmap_implement_trace.py`. Changes: the same files, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`.

- [x] 1.1 Add the tests: the events of a run stand in the order of the run, the bound drops the oldest model events before any other event and counts every dropped event, a run of 101 requests and 150 tool calls keeps its newest tool events in the trace, a stored trace keeps its stored order, a shell call holds the exit status that the shell reports, and `explain --trace` shows it. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_trace.py tests/roadmap/implement/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_explain.py`
- [x] 1.2 Add the model event in the `after_model_request` hook of `ToolCallLog`, let `_trace_replies` add only the replies with no event, let `ImplementTrace.encode` drop the oldest model events first, add `shell_exit_status` and the `status` field of a tool event, and show the status in `explain --trace`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_trace.py tests/roadmap/implement/test_roadmap_implement_step_trace.py tests/roadmap/test_roadmap_explain.py`

## 2. Documents

Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`.

- [x] 2.1 Say in `docs/roadmap/implement.md` that the trace holds the events in the order of the run, with the exit status of a shell call, and that the bound drops the oldest model events first; say the same in `docs/ROADMAP_WORKFLOW.md`, and regenerate the reference
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: A long run keeps its tool, check, retry and attempt events in the trace before any model event, in the order of the run, within the same bound.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
