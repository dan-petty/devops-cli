# Tasks

## 1. Behavior

Reads: `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/implement/test_roadmap_implement_trace.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_explain_command.py`. Changes: the same files, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`.

- [x] 1.1 Add the tests: the bound keeps the tokens and the seconds of the model events that it drops, and the repair rounds and the outcomes of the attempt events that it drops; a trace that fits writes no sum; a decoded trace keeps its sums once; a sum that is not a number stops the decode; the totals and the JSON totals of a long run equal the totals of the full run; the line beside the totals says that they include the dropped events. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_trace.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_explain_command.py`
- [x] 1.2 Add `TraceSums` and the field `dropped_sums` of `ImplementTrace`, keep the sums of the dropped events in `encode`, read them in `decode`, add them in `trace_totals`, and change the text `explain_totals_dropped`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_trace.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_explain_command.py`

## 2. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Say in `docs/ROADMAP_WORKFLOW.md` that the totals of `devops roadmap explain` include the events that the bound of the trace dropped
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The totals of a long run in `explain` and `explain --json` equal the totals of the full run when the bound drops its model events, and the encoded trace stays within the bound.
