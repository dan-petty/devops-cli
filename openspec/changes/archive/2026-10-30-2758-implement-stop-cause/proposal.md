# Proposal

## Why

Issue #2758. The first end-to-end run of the implement job on #2656 stopped at group 1 with the reason `UnexpectedModelBehavior` and the last message "Let me run the test directly in the project directory:". The reason holds only the class name of the pydantic-ai error. The message of the error says what happened, and the Job log has no line for a tool call. After a stop the checkout is discarded, so a person has no evidence of the cause.

## What Changes

- The reason of a step that stops on `UsageLimitExceeded` or `UnexpectedModelBehavior` holds the class name and the message of the error. The step masks the message with `mask_secrets` and cuts it to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters. The stop comment keeps its own cut to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS`.
- The reason also counts the tool calls that were refused and the tool calls that were retried for another cause. The count is in the reason only when it is not zero.
- The agent of a step gets one pydantic-ai `Hooks` capability. It writes one line to the standard error stream for each tool call: the tool name, the first word of a shell command, and the outcome `ok`, `refused`, `retry` or `failed`. A line holds no argument, no file content and no output. The Job log is that stream, so the line is the evidence a person has after a stop.
- A consumer observes the reason and the Job log, so the change carries a spec delta. It modifies one requirement of `roadmap-implement-step` and adds two.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the requirement "A run that reaches a limit ends stopped" now gives the reason as the class and the message of the error. Two requirements are added: the count of refused and retried tool calls in the reason, and the log line of each tool call.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, a new `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_roadmap_implement_step.py`, a new `tests/test_roadmap_implement_tool_log.py`, `tests/support/implement_step.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The cause on #2656 is not proven by the Job log, and this change does not claim it. A faked run shows the case that the issue suspects. The model is a pydantic-ai `FunctionModel` that calls `shell` with `pytest tests/test_sample.py` in every reply, and the agent is the real `build_agent` agent with the real harness shell and the allowlist `git`, `uv`, `ruff`, `mypy`. The shell answers each call with a `ModelRetry` whose text is "Command 'pytest' is not in the allowed list." and whose cause is a `PermissionError` (`pydantic_ai_harness/shell/_policy.py`, `recoverable`). The model got five retry prompts. The sixth call ended the run with `UnexpectedModelBehavior`, with the message "Tool 'shell' exceeded max retries count of 5. Consider raising the retry limit, or see the docs on tool retries: https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/#tool-retries". The `__cause__` chain of that error is the `ModelRetry` and then the `PermissionError` (`pydantic_ai/tool_manager.py`, `_check_max_retries`). Today the step reports only `UnexpectedModelBehavior`, which is the reason on #2656.
- This case gives the same class and the same last message pattern as #2656. It does not prove that #2656 had it: other tool retries, such as arguments that fail validation, end in the same error. The count of refused and of other retries tells the cases apart on the next stop.
- A hook sees both kinds of retry. Read in `pydantic_ai/tool_manager.py` (2.59.0, the version in `uv.lock`): `wrap_tool_execute` wraps the call, and a `ModelRetry` of the tool reaches it as a `ToolRetryError` whose cause is the `ModelRetry`. The call that exceeds the retry limit reaches it as `UnexpectedModelBehavior`. `on_tool_execute_error` is not called for a retry, so it cannot be used. A failed validation of the arguments calls `on_tool_validate_error` before the retry is counted.
- The refusal is told from another retry without reading text: the cause chain of the error holds a `PermissionError` only when the shell refused a command by its policy.
- The issue asks for a line through the "existing logger conventions". A probe shows that a `logging` call at the level INFO is dropped in a `devops` process: the root logger has the level WARNING and no handler (`logging.getLogger().level` is 30 and `handlers` is empty after `import devops_cli.main`). The Job log would hold no line. The channel that reaches the Job log is the console stream, which `main.py` already uses for its elapsed time with `print_muted(..., to_stderr=True)`. The change uses that channel.
- The issue cites the "project's spend capability" as a user of `after_model_request`. The repository holds no such capability. The change uses `pydantic_ai.capabilities.Hooks` directly. The premise of the issue holds, and only this reference is wrong.

## Existing Tool Considered

pydantic-ai `Hooks` (`wrap_tool_execute` and `on_tool_validate_error`) gives the point where each tool call and each retry is seen, and `capture_run_messages` already gives the last text of the model. `mask_secrets` masks the message. `print_muted` writes the line. The change builds only two small decisions that no tool makes: the cause-chain test that tells a refusal from another retry, and the format of the line. Cost of what it builds, estimated: about 150 lines of code and tests, about 80k tokens of agent work and two hours of elapsed time. The upkeep is small: the code follows the public hook signatures of pydantic-ai.

The change deletes no code.
