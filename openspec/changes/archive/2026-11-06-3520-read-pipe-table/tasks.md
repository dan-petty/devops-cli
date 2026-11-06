# Tasks

## 1. Admit a read pipe and the checkout prefix

Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_read_pipe.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`, `tests/roadmap/test_roadmap_implement_shell_refusal.py`.

- [x] 1.1 Add `tests/roadmap/test_roadmap_implement_read_pipe.py`: the table holds `head`, `tail`, `grep` and `wc` and only read programs, `|` stays a denied operator, a read pipe runs, a pipe to `sh` or `|&` is refused with the program and the table, a stage that redirects to a file is refused, a `;` after a read pipe is refused, a `|` in a quoted or escaped pattern is part of a word, and only the exact prefix `cd <checkout> &&` is dropped
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_read_pipe.py` fails on the base
- [x] 1.2 Add `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` to `src/devops_cli/config/constants.py` and the pipe messages to `src/devops_cli/lang/en/messages.py`. Add `wc`, `HARNESS_DENIED_OPERATORS`, `pipe_refusal` and `without_checkout_prefix` to `src/devops_cli/roadmap/implement_shell_policy.py`. Make `ShellRefusal` in `src/devops_cli/roadmap/implement_shell_refusal.py` read the pipe and drop the prefix, and give the shell of `src/devops_cli/roadmap/implement_step.py` the denied operators without `|`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_read_pipe.py tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_implement_shell_refusal.py` passes

## 2. Name the refused program in the log

Reads: `src/devops_cli/roadmap/implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_tool_log.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 2.1 Add cases to `tests/roadmap/test_roadmap_implement_tool_log.py`: `head`, `tail`, `grep` and `wc` are logged by name, an unknown first word is logged as `other:` and a 12-character digest that is not the plain hash and not the word, one word has one digest, and a call that starts with `cd <checkout> &&` names the program after the prefix. Update the cases that expected the plain `other` in the program of a line
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py` fails on the base
- [x] 2.2 Make `logged_program` in `src/devops_cli/roadmap/implement_tool_log.py` write `other:` and the keyed digest of an unknown word, and make `ToolCallLog` read the command after the checkout prefix
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py tests/roadmap/test_roadmap_implement_step.py` passes

## 3. State the rules in the prompt and the workflow document

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the prompt of the step, say that a pipe may end in `head`, `tail`, `grep` or `wc`. In `docs/ROADMAP_WORKFLOW.md`, state the pipe rule, the checkout prefix and the row of `wc`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_implement_shell_refusal.py` passes
- [x] 3.2 Regenerate the documentation
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- `python -c` and `uv run python -c` need no change: `uv run python -c` runs, and a bare `python -c` gets a refusal that names `uv run python`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
