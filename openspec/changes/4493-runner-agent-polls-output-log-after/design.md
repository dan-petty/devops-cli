# Design

## Decisions

- **The blocking tool of the harness.** `_tune` replaces the `Shell` leaf of `Coder` with `tools=["run_command"]` and `default_timeout=roadmap.implement.command_timeout_seconds`. The persistent tool `shell` and the four background tools are not registered, so the agent has no background mode and no log to read. The name lives in `IMPLEMENT_SHELL_TOOL` in `implement_shell_policy.py`, beside the other tables of the shell.
- **The step sets the wait.** `ShellRefusal` already rewrites the arguments of a shell call (the prefix `cd <checkout> &&`). It now also replaces `timeout_seconds` of a `run_command` call with the command limit. The step has one wait for each command, the setting, and no value of the model reaches the workspace. The prompt says that a `timeout_seconds` has no effect, as the description of the harness tool says "default: 30".
- **The exit status.** `run_command` returns text. The last line is `[exit code: <n>]` for a code other than 0, and `[Command timed out after <n>s]` for a killed command. `shell_exit_status` reads that line, and gives 0 when no such line is there. A command whose output ends with a line of the same form and exits with 0 is read with that code. The status is evidence in the trace, and no decision of the step reads it, so this limit is written in the docstring.
- **The prompt names settings.** The prompt names `roadmap.implement.command_timeout_seconds` and `roadmap.implement.repair_rounds` with their defaults. A test compares each default with `setting_default`, so a new default fails the test until the prompt changes. The prompt gets no new placeholder, because `fill_prompt` fills only the tables of the shell policy.

## Rejected alternatives

- **The job runs the long test row in its exit check (the design in the issue).** The agent then gets no result of its own test run in the turn, and must end its turn to learn whether the code passes. The harness tool `run_command` gives the result in the same call.
- **Keep `shell` and refuse its background mode.** A foreground call still returns after 270 s with a PID and a log, and a call cannot ask for more. A test row of more than 270 s gives the same poll.
- **Keep the wait of the model, capped at the setting.** A wait of 0 still ends the run with `ValueError`, and a short wait kills a good test run that the agent must start again.
- **Hide `timeout_seconds` from the tool schema with `prepare_tools`.** The validator of the tool still takes the argument, so the step still needs to replace it. It adds code for no gain.
