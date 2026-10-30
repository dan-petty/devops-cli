# Proposal

## Why

Issue #2731. A model call that fails in a step of `devops roadmap implement` raises a client error out of `_run_agent`. `run_step` resets the checkout, and the stop comment of the item holds only "The step's model call failed (ModelAPIError)." It holds no diff of the discarded work. The case is worst in the extra turn for the ticks (#2721). There, every check has passed and only the ticks are missing, and a person cannot see the work. A stop with a reason (#2721, #2758) keeps the masked, size-limited diff. A failed model call must do the same.

## What Changes

- `_run_agent` no longer raises for a failed model call. For a `ModelAPIError` that is not a refused key, it ends the turn as stopped, like it does for `UsageLimitExceeded` and `UnexpectedModelBehavior`. The reason is built by the same function (`_stop_reason`): the class and the masked, cut message of the error, then the counts of refused and retried tool calls when either is not zero. The turn returns the replies it got (the requests and the tokens), and the last text of the model.
- `_attempt` is not changed. It already builds a stopped outcome with the masked diff when the run holds a reason, for the first turn and for the extra turn. The extra turn adds its partial spend to the spend of the first turn through `_Run.then`.
- A `ModelHTTPError` with the status 401 or 403 still raises `AICredentialsError` after the checkout is reset. It stops the whole run, as before.
- `_implement_item` and `apply_implement` are not changed. They still stop an item that raises `AIClientError` for another cause, such as a failed `git` command, and they still stop the run on `AICredentialsError`.
- A consumer observes the stop reason and the diff in the stop comment, so the change carries a spec delta. It modifies one requirement of `roadmap-implement-step` and adds one.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the requirement "A run that reaches a limit ends stopped" now covers a failed model call, with the three new scenarios. The requirement "A refused key stops the run" is added.

## Impact

- `src/devops_cli/roadmap/implement_step.py`.
- `tests/test_roadmap_implement_step.py`, `tests/test_roadmap_implement_job.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The premise holds on `main`. In `src/devops_cli/roadmap/implement_step.py`, `_run_agent` catches `ModelAPIError`, builds the client error with `model_call_error` and raises it after the `finally` block. The call to `_discarded_diff` is in `_attempt`, after the turns, so the raise skips it. `run_step` resets the checkout in its `finally` block. `_implement_item` in `src/devops_cli/roadmap/implement_run.py` catches `AIClientError` and stops the item with the reason "AIClientError: The step's model call failed (ModelAPIError).", with no diff.
- A faked run shows it. The model is a pydantic-ai `FunctionModel` from `ModelScript`. It writes two files, and then its second request raises `ModelAPIError`, `ModelHTTPError` (status 503) or `ModelRequestTimeout`. `run_step` raises `AIClientError: The step's model call failed (...)`. The same model in the extra turn for the ticks (the first turn writes the work and forgets the ticks) gives the same error. The new tests fail on this error before the change.
- The partial result is already in `_run_agent`. `capture_run_messages` holds the messages of the failed run (pydantic-ai 2.59.0, the version in `uv.lock`), so `_last_text(messages)` and `_new_replies(messages, conversation)` give the last text and the replies that came before the failure. The `finally` block already records the spend of those replies. The failed request has no `ModelResponse`, so it adds nothing to the count. No new capture is needed.
- The classes of error follow `pydantic_ai/exceptions.py`. `ModelAPIError` is the base of `ModelHTTPError` and of the categories `ModelRateLimitError`, `ModelQuotaExceededError`, `ModelUnavailableError`, `ModelServerError`, `ModelConnectionError`, `ModelTimeoutError`, `ModelContextWindowExceededError` and `ModelRequestTimeout`. `UsageLimitExceeded` and `UnexpectedModelBehavior` are `AgentRunError`, not `ModelAPIError`. `model_call_error` in `src/devops_cli/roadmap/agent_run.py` maps a `ModelHTTPError` with the status 401 or 403 to `AICredentialsError`, and every other `ModelAPIError` to `AIClientError`. Only the 401 and the 403 mean a rejected key.
- Today the classification at the item level is the same for every error that is not a refused key. `_implement_item` stops the item on `AIClientError`, and `apply_implement` stops the run only on `AICredentialsError` and `GitHubUnauthenticatedError`. The issue asks to keep it. After the change, `ModelAPIError` (including timeouts and rate limits) and `UsageLimitExceeded` are item-level, and a refused key stops the run.
- The message of a `ModelAPIError` can hold the body of the reply of the provider. The reason masks it with `mask_secrets` and cuts it to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters, as it does for `UnexpectedModelBehavior`, whose message can hold a body too. A key that the gateway refuses never reaches the reason: it raises.
- The issue proposes to leave `_attempt` and `_implement_item` unchanged, and the code confirms it. One point in the issue needs care: it says that "_run_agent catches a ModelAPIError that maps to AICredentialsError" and raises. The code keeps that path, and it raises after the `finally` block, so the spend of the failed turn is still recorded.

## Existing Tool Considered

pydantic-ai gives all that the fix needs: the error classes, `capture_run_messages` for the replies and the last text of a failed run, and `UsageLimits`. The repository gives `_stop_reason`, `_last_text`, `_new_replies`, `_Run.then` and `_discarded_diff`. The change builds nothing new: it moves one `except` clause from the path that raises to the path that returns a stopped `_Run`. Cost, estimated: about 10 lines of code and 150 lines of tests, about 60k tokens of agent work and one hour of elapsed time. The upkeep is small, as the code uses the public pydantic-ai exceptions and one shared function for the reason.

The change deletes no code.
