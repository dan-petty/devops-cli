# Proposal

## Why

Issue #2773. The agent of an implement step keeps asking its shell for programs outside the allowlist. Each refusal counts against the retry limit of the shell tool, which is 5. The run then ends and the step discards its work. Two Jobs on 0.22.x show it. One Job stopped with "Tool 'shell' exceeded max retries count of 5", after six refused commands. Another Job had four refused commands among about 30 tool calls. The refusal text that the model reads says only "Command 'x' is not in the allowed list.", so the model does not learn what to run in its place. The Job log writes every refused program as "other", so nobody sees which program the model wants.

## What Changes

- The refusal of the shell tool tells the model what to use in its place. A program that the project knows, such as `python`, `pytest`, `cat` or `cd`, gets its replacement from one table. Any other refused program gets the list of allowed programs and the `uv run` form. A refused operator gets the rule of one command in each call. The set of allowed programs does not change.
- The prompt of the step gets the same table, next to the line that lists the allowed programs. A test pins the table and that line to `IMPLEMENT_SHELL_PROGRAMS` and to the table in the code.
- The log line of a refused command names its program when the first word is a program that the project knows: a program of the allowlist or a key of the table of replacements. Any other first word stays "other", also a short bare word, as the model can read a password from a file.
- The refusal text of the shell is cut to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` before the hint, as the text echoes the first word of the command with no limit.
- The refusal of `python` also says not to run `python -m pip`, and the prompt shows a directory command that the shell accepts.
- The reason of a stopped step counts the refused commands by program, for example "Refused commands: python 4, cd 2. Other retries: 1." The reason lists at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs. The programs beyond that join the count of "other".
- A consumer observes the log line, the reason and the refusal text, so the change carries a spec delta. It modifies three requirements of `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the requirements "The shell tool admits only the project's programs", "The reason of a stopped run counts the refused and the retried tool calls" and "Every tool call of a step writes one line to the Job log".

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, a new `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `tests/test_roadmap_implement_tool_log.py`, `tests/test_roadmap_implement_step.py`, a new `tests/test_roadmap_implement_shell_refusal.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- Where the refusal text is made, in the installed `pydantic-ai-harness` 0.59.0 (the version in `uv.lock`). `ShellToolset._check_command` in `pydantic_ai_harness/shell/_toolset.py` raises `PermissionError(f'Command {executable!r} is not in the allowed list.')`. The operator refusal and the interactive refusal are `PermissionError` too. The decorator `recoverable` in `pydantic_ai_harness/shell/_policy.py` turns the error into `ModelRetry(str(e))`.
- The text cannot be set. `Shell` and `ShellToolset` have no field or argument for it (`allowed_commands`, `denied_commands`, `denied_operators`, `default_timeout`, `max_output_chars`, `max_file_bytes`, `persist_cwd`, `allow_interactive`, `env`, `denied_env_patterns`, `tools`). The text is a string in the library code. So the change needs a wrapper.
- The wrapper is a pydantic-ai `Hooks` capability, not a subclass of a private method. In `pydantic_ai/tool_manager.py` (`_run_execute_hooks`), `wrap_tool_execute` sees a refusal as a `ToolRetryError` whose cause chain holds the `PermissionError`. A hook that raises `ModelRetry` with a new text is the documented path: the manager wraps it as a retry again. The manager records a failed tool in the set `failed_tools`, so the second wrap adds nothing to the retry count, and a test shows the model gets five refusals before the sixth call ends the run, as before. The hook keeps the original text and adds the hint after it, so the operator and interactive refusals keep their own text.
- The step shell has no credential in its environment. `shell_environment` in `implement_step.py` sets only `HOME` (a scratch directory), `XDG_CONFIG_HOME`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, `UV_CACHE_DIR` and `UV_PYTHON`. A local workspace passes on only `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` of the host, plus that `env` (`pydantic_ai/workspaces/local.py`, `_INHERITED_ENV`). The token of the Job stays in the process of the Job. The model can still read a secret from a file of the checkout and run it as a command, so the log shows a first word only when it is a known program.
- The premise of the issue holds. The two stops are in the comments on #2745 and #2656: six refused commands, then "Tool 'shell' exceeded max retries count of 5", and four refused commands. The Job logs write "program other" for each. The issue lists the programs as "likely"; the change does not claim them. The table covers the habits of the issue, and the log shows the real program after this change.

## Existing Tool Considered

`pydantic-ai-harness` `Shell` has the allowlist and the refusal, but no setting for the refusal text (see Feasibility). pydantic-ai `Hooks` (`wrap_tool_execute`) is the documented seam, and the project already uses it for the log of #2758. `collections.Counter` counts by program. The change builds only the table and the hook that adds the hint to a refusal. Cost of what it builds, estimated: about 120 lines of code and 250 lines of tests, about 100k tokens of agent work and two hours of elapsed time. The upkeep is small: the hook follows the public hook signature, and a test fails when the table and the prompt drift.

The change deletes no code. It replaces `_refused` and `_program` of `implement_tool_log.py` with public functions that the new module shares.
