# Proposal

## Why

The implement step of #2572 stopped with `UnexpectedModelBehavior: Tool 'shell' exceeded max retries count of 5`. #3271 first asked to raise or configure the retry limit. The evaluation of #3271 shows that the stated cause is wrong. In the window 2026-11-03T15:05Z to 2026-11-04T15:05Z, 11 stops have the class `refused_tool`. They hold 201 refused commands, at most 37 in one run, and 45,964,971 input tokens. A refusal of the shell by policy is no failure of the tool, yet it counts as a tool retry. A higher limit only moves the stop.

## What Changes

- A refusal of the shell by policy, and a refusal of an argument, come back as a normal tool result that names the replacement. They add no tool retry. A real failure of a tool still counts, and `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` stays 5 for real failures.
- A new constant `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` of 30 limits the refusals in one step. The 31st refusal ends the run with the text "Too many commands refused by policy in one step: the limit is 30." The failure class of the stop is `refused_tool`, an existing class of `failure.py`, so this change adds no class.
- A new capability `ShellRefusal` wraps the toolset of the agent. It replaces the two hooks `shell_refusal_hooks` and `argument_refusal_hooks`. The tool log keeps the count of refused commands and the line `refused` for each refused call.
- The setting `roadmap.implement.tool_retries` and a default of 50 are not added.
- `docs/ROADMAP_WORKFLOW.md` states that a refusal adds no tool retry and that the step has a limit of refusals.
- The change modifies four requirements of `roadmap-implement-step`: the shell policy, the limit that ends a run, the counts of a stopped run, and the line of each tool call.
- The change fits one pull request. The read pipe through a table of right-hand programs and the table of `logged_program` go to #3520.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A shell refusal counts no tool retry, and the refusals of a step have a limit

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`, `tests/roadmap/test_roadmap_implement_tool_log.py`, `tests/roadmap/test_roadmap_limit_classes.py`

## Feasibility

- The installed `pydantic_ai` is version 2.59.0. In `pydantic_ai/tool_manager.py`, `for_run_step` (lines 331 to 342) keeps the retry count of a tool for the next run step only when the tool is not in `succeeded_tools`, and adds one for each tool in `failed_tools`. A successful call of a tool therefore resets its count, and the count is of failures in a row. The stated cause of #3271 (a count across the full execution) is false.
- The same file shows why a hook cannot return the refusal as a result. `_raw_execute` (line 1188) catches the `ModelRetry` of the tool, calls `_check_max_retries`, and adds the tool to `failed_tools` before any `wrap_tool_execute` hook sees the error. A hook that turns the error into a result is too late: the count is up, and the check raises at the sixth call. A trial of this form in `implement_shell_refusal.py` showed it: the run still stopped at the sixth request. The design point 1 of #3271 ("`_execute` can return text in place of `raise ModelRetry`") does not hold as written.
- The public method `AbstractCapability.get_wrapper_toolset` wraps the toolset. A `WrapperToolset.call_tool` runs inside `_raw_execute`, so a refusal that it returns is a normal result and counts as a success.
- The shell of `pydantic-ai-harness` 0.59.0 raises a policy refusal as `ModelRetry` from a `PermissionError` (`shell/_policy.py`, function `recoverable`). The wrapper reads that cause, so the harness stays the one authority on what the shell allows.
- The window of 2026-11-03 to 2026-11-04 gives the limit. The largest run holds 37 refused commands, and 201 refused commands fall in 11 stops. A limit of 30 lets a run be refused often and still ends a loop. `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` of 500 and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` of 1,500 are the only other stops of such a loop.
- The first checks are `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_refusal.py`, then the other test files in "Impact", then `uv run devops openspec check`.

## Existing Tool Considered

`pydantic-ai` already has the seam: `AbstractCapability.get_wrapper_toolset` and `WrapperToolset`. This change uses them and builds no parser. The only new code is about 40 lines of the wrapper and 12 lines of the limit in the tool log. The cost is about 8,000 tokens to build, about 1,000 tokens to keep and fix, and about 2 hours. The change deletes the two hooks `shell_refusal_hooks` and `argument_refusal_hooks`, the private class `_ArgumentRefused` and the helper `_has_cause` of `implement_shell_refusal.py`.

## Dependencies

None. Issue #3476 adds failure classes in parallel. This change uses the existing class `refused_tool` and adds none. Issue #3041 names this issue as a dependency.
