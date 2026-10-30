# Proposal

## Why

Issue #2731. A model call that fails in a step of `devops roadmap implement` raises a client error out of `_run_agent`. `run_step` resets the checkout, and the stop comment of the item holds only "The step's model call failed (ModelAPIError)." It holds no diff of the discarded work. The case is worst in the extra turn for the ticks (#2721). There, every check has passed and only the ticks are missing, and a person cannot see the work. A stop with a reason (#2721, #2758) keeps the masked, size-limited diff. A failed model call must do the same.

## What Changes

- `_run_agent` no longer raises for a failed model call. For a `ModelAPIError` that is not a refused key, it ends the turn as stopped, like it does for `UsageLimitExceeded` and `UnexpectedModelBehavior`. The reason holds the class of the error, the HTTP status when the error has one, and the name of the model, then the counts of refused and retried tool calls when either is not zero. It holds neither the message nor the body of the reply (`_model_call_reason`). The turn returns the replies it got, the interrupted reply of the failed request included (the requests and the tokens), and the last text of the model.
- `_attempt` is not changed. It already builds a stopped outcome with the masked diff when the run holds a reason, for the first turn and for the extra turn. The extra turn adds its partial spend to the spend of the first turn through `_Run.then`.
- A `ModelHTTPError` with the status 401 or 403 still raises `AICredentialsError` after the checkout is reset. It stops the whole run, as before.
- `_implement_item` and `apply_implement` are not changed. They still stop an item that raises `AIClientError` for another cause, such as a failed `git` command, and they still stop the run on `AICredentialsError`.
- A consumer observes the stop reason and the diff in the stop comment, so the change carries a spec delta. It adds three requirements to `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the requirements "A failed model call ends the step stopped", "A failed model call gives a reason with no text of the provider" and "A refused key stops the whole run" are added.

## Impact

- `src/devops_cli/roadmap/implement_step.py`.
- `tests/test_roadmap_implement_step.py`, `tests/test_roadmap_implement_job.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The premise holds on `main`. In `src/devops_cli/roadmap/implement_step.py`, `_run_agent` catches `ModelAPIError`, builds the client error with `model_call_error` and raises it after the `finally` block. The call to `_discarded_diff` is in `_attempt`, after the turns, so the raise skips it. `run_step` resets the checkout in its `finally` block. `_implement_item` in `src/devops_cli/roadmap/implement_run.py` catches `AIClientError` and stops the item with the reason "AIClientError: The step's model call failed (ModelAPIError).", with no diff.
- A faked run shows it. The model is a pydantic-ai `FunctionModel` from `ModelScript`. It writes two files, and then its second request raises `ModelAPIError`, `ModelHTTPError` (status 503) or `ModelRequestTimeout`. `run_step` raises `AIClientError: The step's model call failed (...)`. The same model in the extra turn for the ticks (the first turn writes the work and forgets the ticks) gives the same error. The new tests fail on this error before the change.
- The partial result is already in `_run_agent`. `capture_run_messages` holds the messages of the failed run (pydantic-ai 2.59.0, the version in `uv.lock`), so `_last_text(messages)` and `_new_replies(messages, conversation)` give the last text and the replies that came before the failure. The `finally` block already records the spend of those replies. With the event stream handler that every turn uses, pydantic-ai also commits the failed request as a `ModelResponse` in the state `interrupted` (`_agent_graph.py`, `_commit_interrupted_response`), with any text and tokens that the provider billed before the error. A probe of a failed second request shows the messages `ModelRequest`, `ModelResponse` (text and two tool calls), `ModelRequest` (two tool returns) and an empty `ModelResponse`. So the failed request counts as a request, and its text is the last text of the model when it has some. No new capture is needed.
- The classes of error follow `pydantic_ai/exceptions.py`. `ModelAPIError` is the base of `ModelHTTPError` and of the categories `ModelRateLimitError`, `ModelQuotaExceededError`, `ModelUnavailableError`, `ModelServerError`, `ModelConnectionError`, `ModelTimeoutError`, `ModelContextWindowExceededError` and `ModelRequestTimeout`. `UsageLimitExceeded` and `UnexpectedModelBehavior` are `AgentRunError`, not `ModelAPIError`. `model_call_error` in `src/devops_cli/roadmap/agent_run.py` maps a `ModelHTTPError` with the status 401 or 403 to `AICredentialsError`, and every other `ModelAPIError` to `AIClientError`. Only the 401 and the 403 mean a rejected key.
- Today the classification at the item level is the same for every error that is not a refused key. `_implement_item` stops the item on `AIClientError`, and `apply_implement` stops the run only on `AICredentialsError` and `GitHubUnauthenticatedError`. The issue asks to keep it. After the change, `ModelAPIError` (including timeouts and rate limits) and `UsageLimitExceeded` are item-level, and a refused key stops the run.
- The message of a `ModelHTTPError` holds the body of the reply of the provider as the repr of a Python value. `mask_secrets` finds a secret by its form in a sentence, and it does not find the value of a key such as `x-api-key` or `api_key` in that repr (checked with a dict body). So the reason leaves the message and the body out, and gives the class, the status and the model name only. These are enough to tell a 503 from a 429. The comment of the item goes to GitHub, so nothing that the provider chose may enter it. A key that the gateway refuses never reaches the reason: it raises.
- The issue proposes to leave `_attempt` and `_implement_item` unchanged, and the code confirms it. One point in the issue needs care: it says that "_run_agent catches a ModelAPIError that maps to AICredentialsError" and raises. The code keeps that path, and it raises after the `finally` block, so the spend of the failed turn is still recorded.

## Existing Tool Considered

pydantic-ai gives all that the fix needs: the error classes, `capture_run_messages` for the replies and the last text of a failed run, and `UsageLimits`. The repository gives `_stop_reason`, `_last_text`, `_new_replies`, `_Run.then` and `_discarded_diff`. The change builds nothing new: it moves one `except` clause from the path that raises to the path that returns a stopped `_Run`. Cost, estimated: about 10 lines of code and 150 lines of tests, about 60k tokens of agent work and one hour of elapsed time. The upkeep is small, as the code uses the public pydantic-ai exceptions and one shared function for the reason.

The change deletes no code.
