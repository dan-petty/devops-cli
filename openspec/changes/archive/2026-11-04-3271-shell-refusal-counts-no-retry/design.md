# Design

## Decisions

- **Wrap the toolset with `get_wrapper_toolset` and return a refusal from `call_tool`.**: The retry count is made in `_raw_execute` before any hook runs, so only code inside the call of the toolset can return the refusal as a success. The hook point is public API of pydantic-ai, and the harness stays the authority on the shell policy because the wrapper reads its `ModelRetry`.
- **Catch a `ModelRetry` whose `__cause__` is a `PermissionError` and whose call has a `command` word.**: This is the form in which the harness raises a refusal (`recoverable` in `shell/_policy.py`). A `ModelRetry` for another cause, such as a NUL byte in the command, still counts as a failure. A file tool has no `command`, so its refusal of a path still counts.
- **Check the refused argument in the same wrapper, before the call.**: The table `SHELL_PROGRAMS` is read in one place. The hook that raised the argument refusal only worked because a second hook turned it into a `ModelRetry`. Both hooks, the cause class `_ArgumentRefused` and the helper `_has_cause` go.
- **The wrapper tells the tool log through `ToolCallLog.refuse(tool_call_id)`, and the log counts the call.**: The log hook sees a result for a refused call, so it reads the marker by the id of the call. The id is safe for parallel calls in one reply. The log keeps its counts, its line `refused`, its trace event and the reason of a stop.
- **End the run in the tool log when the refusals pass `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS`.**: The log holds the total of refusals for the whole step, extra turns included, and it already sits where a run ends on `UnexpectedModelBehavior`. The error text names the limit. The reason of the stop then holds "Refused commands: ..." and the failure class is `refused_tool`, which `failure.py` already maps to the action `wait`. No class is added.
- **Set the limit to 30.**: The window of 2026-11-03 to 2026-11-04 shows 11 stopped runs with 201 refused commands and at most 37 in one run. A run needs room for the habits of a model, such as `cd`, `python` and `rg`, but a loop must end well before the 500 requests of the run.
- **Keep `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` at 5.**: A refusal adds no retry now, so the count holds failures in a row only, and the harness file tools allow five.
- **Add no setting `roadmap.implement.tool_retries`.**: The evaluation of #3271 drops it.

## Rejected alternatives

- **Raise `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` or make it a setting with a default of 50.**: A successful call resets the count (`tool_manager.py`, `for_run_step`), so a higher limit only moves the stop for a model that loops on a refusal.
- **Return the refusal from the existing `wrap_tool_execute` hook.**: The hook runs after `_raw_execute` has counted the failure and checked the limit, so the run still stops at the sixth refusal. A trial showed it.
- **Check the command in a hook before the call, with our own allowlist code.**: It repeats the policy of the harness (allowed programs, denied operators, interactive commands), and the two copies drift.
- **Subclass `Shell` and override `_make_toolset`.**: It uses a private method of the harness.
- **Remove `|` from `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`.**: The harness reads the first word only, so `| sh` would run. A table of right-hand programs is a separate change.
- **Write a free first word to the log for the 91 refused commands whose program is `other`.**: The first word can hold a secret (`implement_tool_log.py`). A change to that rule goes to the owner.
