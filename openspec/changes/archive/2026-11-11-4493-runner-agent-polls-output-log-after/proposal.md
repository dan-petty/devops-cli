# Proposal: #4493

## Why

The agent of an implement step polls the log of the harness shell after a long command, and the polls spend the step token budget. Closes #4493.

`Coder` of pydantic-ai-harness 0.59.0 registers the persistent tool `shell` with `default_timeout=MAX_FOREGROUND_WAIT` (270 s, `coder/_capability.py:136-142`), and a call cannot ask for more. The tool also has a background mode, and no notice arrives when its command ends. `_tune` in `implement_step.py` changed only the allowlist, the operators and the environment of the shell, so it kept the 270 s return and the background mode. A scoped `uv run devops ci test <dir>` often runs longer than 270 s. The call then returns a PID and a log path, and the agent reads `output.log` again and again: Job 686f (#3429) made 67 `tail` calls on one log, and the step stopped at `step_token_budget`. The prompt rule "A shell call returns when its command ends. Do not poll" was false.

Two more defects of the same prompt and shell:

- The prompt promised "one more turn" for an error of `ruff check` or `mypy`. The step gives up to `roadmap.implement.repair_rounds` (default 3) extra turns, and each failed check or hook takes one.
- The harness refuses an operator as plain text, so a `;`, a new line or a heredoc in the code of `uv run python -c` is refused. The hint said only "Do not chain commands", and the agent sent the same code again (24 refusals in 8 of 8 Jobs in the window of the issue).

## What Changes

- The shell of a step is the tool `run_command` of the same `Shell` capability of the harness, in place of the persistent tool `shell`. `run_command` waits until its command ends and returns the labelled output, and the line `[exit code: <n>]` when the code is not 0. `_tune` registers only that tool and sets its wait to `roadmap.implement.command_timeout_seconds` (default 1800). The harness kills a command that runs longer (the process group) and the call returns `[Command timed out after <n>s]`. No tool has a background mode, so the agent has no log to poll.
- `ShellRefusal` sets the wait of each `run_command` call to the same setting, whatever wait the model gives. The description of the tool says "default: 30", a short wait kills a good test run, a long wait keeps the Job log silent past `deadline_stall_seconds`, and a wait of 0 makes the workspace raise `ValueError`, which ends the run.
- The allowlist, the denied operators, the pipe rule, the argument refusals and the refusal count apply to `run_command` as they did to `shell`: the harness checks both tools with the same `_check_command`, and `ShellRefusal` reads the `command` argument of any tool.
- The tool log reads the exit status of a `run_command` call for the trace: the code of the last line `[exit code: <n>]`, else 0, and no status for a call that timed out.
- The tool name changes in `IMPLEMENT_LOCAL_TOOL_NAMES` and in the tool registry `roadmap/tools.py`. The lines of the Job log read `Tool call: run_command, ...`.
- The prompt states the wait of `run_command` with its setting and default, keeps the ban on `sleep`, `time.sleep` and a repeated `tail`, says that a `timeout_seconds` of the model has no effect, and gives the count of extra turns with `roadmap.implement.repair_rounds`.
- The hint of an operator refusal names a `;`, a new line and a heredoc in the code of `python -c`, and tells the agent to write that code to a file under `.data/agent/scratch/` and run `uv run python <file>`.
- The prompt states before the first call that the shell refuses a heredoc and code of `python -c` that holds a `;` or a new line, and names the script file. The base instructions of `Coder` (`coder/_instructions.py`) tell the model to check behavior with a heredoc, and the step keeps them.
- The digest of the budget extension (#4394) counts a refused command by its outcome, not by its tool name, so its count does not change.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The implement prompt forbids polling; A shell call in a trace holds its exit status; A run that reaches a limit ends stopped; A call with a command writes the command to the Job log before it runs; The shell of a step waits for its command up to the command limit (added); The operator refusal names the code of python -c (added); The implement prompt gives the count of extra turns (added); The implement prompt names the refusal of a heredoc (added); The operator refusal names the code of python -c (added); The implement prompt gives the count of extra turns (added)

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/settings.py` (description only)
- Prompt: `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Tests: `tests/roadmap/implement/` (the tool name in the scripts of a real step, the wait, the exit status, the prompt and the hint)
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ENV_VARS.md` (generated), the knowledge base page `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`
- Operations: no setting is added, removed or renamed, so the live ConfigMap needs no change. A Loki query on `Tool call: shell` finds no line after the release; the query for polls reads `Tool call: run_command`.

## Feasibility

- Harness source (`pydantic_ai_harness` 0.59.0): `Coder` builds `Shell(default_timeout=MAX_FOREGROUND_WAIT, tools=['shell'])` (`coder/_capability.py:136-142`). `Shell.tools` takes any of `run_command`, `start_command`, `check_command`, `stop_command` and `shell` (`shell/_toolset.py`, `SHELL_TOOL_NAMES`), and the 270 s cap applies only when `shell` is registered. `ShellToolset.run_command` calls the same `_check_command` as `shell`, then `ctx.workspace.run(..., timeout=timeout)`.
- Library source (`pydantic_ai` 2.59.0, `workspaces/local.py`): `LocalWorkspaceBackend.run` starts the command in a new session and kills the whole process group at the timeout.
- A real run of `Shell(tools=['run_command'], default_timeout=2)` on a `LocalWorkspace` with a scripted model: `sleep 1` returned after 1.1 s, `sleep 5` returned `[Command timed out after 2s]` after 2.1 s, a failing `git rev-parse` ended with `[exit code: 128]`, `cd /` then `pwd` printed the workspace directory (no state from one call to the next, as with `shell`, which also starts each command in the working directory), `git status; git log` was refused for `;`, and `timeout_seconds=0` ended the run with `ValueError: timeout must be a positive finite number or None`.
- Settings: `deadline_stall_seconds` (default 4200) must be above `command_timeout_seconds` (default 1800), so a call that waits the whole limit does not end the Job by its stall. `step_time_limit_seconds` is checked before each model request and already names `command_timeout_seconds` as the limit of a running command.
- The issue proposed to move the long test row to the exit check of the job. That gives the agent no result of its own test run in the turn, and the harness already ships a tool that blocks, so this change uses that tool.

## Existing Tool Considered

The harness tool `run_command` covers the need: it blocks, it kills a command at its wait, and it takes the same allowlist. The change builds no shell code. It adds about 10 lines that set the wait of a call and read the exit status line. Cost: about 60k tokens to build, under 1 hour, and near zero to keep, as the code follows the result form of the pinned harness.
