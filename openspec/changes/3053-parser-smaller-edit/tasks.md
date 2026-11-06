# Tasks

## 1. Ask for a smaller edit after a parser failure

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_parser.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_step_parser.py` and `tests/roadmap/test_roadmap_implement_step.py`, add and change the tests: the resend after a parser failure holds the smaller-edit message once; a second parser failure of the step, also after a good reply, stops it with class `parser` and no third send; the `wip:` commit of a ticked task stays
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_parser.py tests/roadmap/test_roadmap_implement_step.py`
- [x] 1.2 Add `_ask_smaller_edit`, the count `ToolCallLog.parser_failures`, the message `implement_parser_smaller_edit`, and the use of them in `_run_agent`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_parser.py tests/roadmap/test_roadmap_implement_step.py`

## 2. Tell the reader

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 In `docs/roadmap/implement.md`, describe the smaller-edit message and the stop on the second parser failure of a step
  - Verification: `uv run devops docs check`

## Workflow follow-up

- Strategy of each round and the name of `roadmap.implement.ladder` in the stop of a one-tier ladder: #3569.
- The guard against a repeated failed tool call: #3570.
- The reset of a moved HEAD: #3575.
- A group that changes no file returns for a smaller replacement: #3576.
- The repair of a failed verification command: #3577.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
