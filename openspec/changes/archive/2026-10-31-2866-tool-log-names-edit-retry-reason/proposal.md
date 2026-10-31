# Proposal

## Why

Issue #2866. The implement Job `devops-cli-runner-20261031-125802-ebfe` for #2735 stopped at group 1 with `UnexpectedModelBehavior: Tool 'edit_file' exceeded max retries count of 5`. The Job log and the stop comment show the word `retry` for each failed call and nothing else. `edit_file` refuses an edit for several causes, and the retry message that it returns is the only evidence of the cause. The step does not keep that message, so a person cannot tell a missing `old_text` from a stale hash. The same blind stop happened on #2656.

## What Changes

- The tool log line of a retried call carries the reason that the tool returned, and the path of the call when the reason does not name it. Example: `Tool call: edit_file, retry (old_text not found in src/x.py. No changes were written.).` The reason is masked, escaped to one line and cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` characters.
- The reason is the message of the `ModelRetry` that the tool raised. The code reads it from the `ToolRetryError` that pydantic-ai makes, or from the cause chain of the error that ends the run. It does not match on the text of the model.
- A retry that is a refusal by policy has no reason in the line: a `PermissionError` is in its cause chain. The text of such a refusal repeats the command or names a path outside the root, and the spec already keeps it out of the log. A retry of failed argument validation has no reason either: its content is a list of errors that holds the input of the model.
- `ToolCallLog` keeps the last `CONST_ROADMAP_IMPLEMENT_STOP_REASONS` reasons of each tool. When a tool exceeds its retries, the reason of the stopped run ends with one more line that names the tool and its last reasons, in the same bounded form.
- A consumer observes the Job log and the stop comment, so the change carries a spec delta. It modifies one requirement of `roadmap-implement-step` and adds two. This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the line of a retried tool call and the reason of a stopped run.

## Impact

- `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`.
- `tests/roadmap/test_roadmap_implement_tool_log.py`, `tests/roadmap/test_roadmap_implement_step.py`.

## Feasibility

- **The reason exists and is reachable.** In `pydantic_ai_harness/filesystem/_toolset.py`, `_edit_file` raises `ValueError` for `old_text not found in <path>. No changes were written.`, for a match count above one, and for a stale hash (`Conflict: file ... has changed`). The decorator `_recoverable` turns these into `ModelRetry(str(error))`. `_replacements` raises `ModelRetry` itself for a missing pair.
- **The hook sees it.** In `pydantic_ai/tool_manager.py`, `_raw_execute` catches `ModelRetry`, calls `_check_max_retries`, and raises `ToolRetryError(RetryPromptPart)` whose `content` is the message. `ToolCallLog._execute` is a `wrap_tool_execute` hook, so it already receives that error. The call that exceeds the limit raises `UnexpectedModelBehavior ... from error`, and `error` is the `ModelRetry`. So the last reason is in `__cause__` of the error that ends the run. No new hook and no patch of the harness is needed.
- **What the reason can hold.** All `ModelRetry` texts of the filesystem toolset were read. They hold a path or a pattern that the model wrote, a count, a hash of 12 hex characters, the strerror of the OS and fixed words. None holds file content or the `old_text` or `new_text` of the model. So the change shows no excerpt of `old_text`: a reason names the cause, and the excerpt would add file content to a public comment. The model text is still masked and cut, as a path can hold anything.
- **Validation retries.** For a failed validation, `RetryPromptPart.content` is a list of error details with an `input` field, which holds what the model sent. The change logs no reason for it, so no argument value reaches the log.
- **Not read from a live Job.** The Job log of the run in the issue is not needed: the issue quotes its lines, and the tests below run the real `Coder` toolset on a checkout with a scripted `FunctionModel`.

## Existing Tool Considered

pydantic-ai already carries the reason: `ToolRetryError.tool_retry.content` and `ModelRetry.message`. `mask_secrets` (through `bounded_text`) masks it, and `str.encode("unicode_escape")` escapes it, as `logged_command` does. The change builds only the choice of what the line shows, about 40 lines with tests. Cost, estimated: 50k tokens of agent work and one hour of elapsed time. The upkeep is small. The change deletes no code.
