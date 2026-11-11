# Tasks

## 1. The shell of a step waits for its command

Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_timeouts.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step_trace.py`. Changes: the same files, `src/devops_cli/roadmap/tools.py` and the tests of `tests/roadmap/implement/` that script a call of the shell in a real step.

- [x] 1.1 Add the tests: the agent offers `run_command` and no `shell`, the tuned shell has the wait of the setting, each call reaches the workspace with the wait of the setting whatever wait the model gives, and the trace holds the exit status that `run_command` reports. Change the tool name in the scripts of a real step. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_timeouts.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/implement/test_roadmap_implement_step_trace.py`
- [x] 1.2 Register only `run_command` with the wait of `roadmap.implement.command_timeout_seconds` in `_tune`, set the wait of each call in `ShellRefusal`, read the exit status of `run_command` in the tool log, and rename the tool in `IMPLEMENT_LOCAL_TOOL_NAMES` and the tool registry
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_tools.py tests/roadmap/test_roadmap_mcp.py`
- [x] 1.3 Name the tool `run_command` in the test of the line that a call writes before it runs, so that the test and its scenario name the tool of the step
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py`

## 2. The prompt and the refusal hint

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`. Changes: the same files.

- [x] 2.1 Add the tests: the prompt states the wait of `run_command` with the setting and its default and forbids a poll, the prompt gives the count of extra turns with `roadmap.implement.repair_rounds`, and the operator hint names the code of `python -c`. They fail on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`
- [x] 2.2 Correct the rule of the shell call and the rule of the extra turns in the prompt, and add the `python -c` causes to the operator hint
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`
- [x] 2.3 Add the test that the prompt names the refusal of a heredoc and of `python -c` code with a `;` or a new line, then add that rule to the prompt before the first call
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py`

## 3. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `src/devops_cli/config/settings.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`. Changes: the same files and `docs/ENV_VARS.md`.

- [x] 3.1 Say in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md` that the shell of a step is `run_command` and waits up to the command limit, add the shell of the agent to the description of `command_timeout_seconds`, and regenerate the reference
  - Verification: `$ uv run devops ci docs`
- [x] 3.2 Say in the knowledge base page of the harness that the step registers `run_command` with the command limit in place of `shell`, and that the base instructions of `Coder` name a heredoc and a poll
  - Verification: `$ uv run devops ci test tests/review/test_kb_manuals_metadata.py`

## Criteria

- Group 1: A step offers no shell tool that returns before its command ends, and each command of the agent waits up to `roadmap.implement.command_timeout_seconds`.
- Group 2: The prompt and the refusal hint state what the step does.
- Group 3: The documents name the tool and its wait.
