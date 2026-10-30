# Proposal

## Why

Issue #2562 reports that the two warnings of a refine round for one item name no repository and no cause. The Service runs refine for 7 repositories, and issue numbers repeat across them, so an operator cannot find the issue. A call that waited too long at the gateway reads the same as a reply that the model got wrong.

## What Changes

- The warning "Refine skipped #N: its model call failed" names the repository, the class of the error and its reason. The reason is the error code of the error, then the HTTP status of the gateway's reply or `timeout`.
- The warning "Refine's investigation of #N stopped with no proposal" names the repository and the reason. The reason is the class of the pydantic-ai error and the first line of its `message`, masked and cut.
- `AIClientError` gets the fields `status` and `timed_out`. The gateway, Claude and Ollama paths, the stream reads and `model_call_error` set them where the code already knows the status or the timeout. They hold no text of the model.
- The implement step reads the `message` of a stopped run through the same helper, not `str()`, which closes the leak of the `body` (#2778). The two limits become one pair, `CONST_ROADMAP_RUN_ERROR_CHARS` and `CONST_ROADMAP_RUN_ERROR_READ_CHARS`.
- `InvestigationStopped` gets the field `message`. Its `reason` stays the class name, so the alternatives job keeps the text of its comment and record.
- The error that ends the round (`RoadmapRefineError`), the job record and the comments on issues do not change.
- The change alters a log message of the Service, so it carries a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

- `ai-client-error-reason`: an `AIClientError` states the HTTP status or the timeout of the provider call that failed, and its `reason` holds no text of the model.

### Modified Capabilities

- `roadmap-refine`: the warnings for a failed model call and for a stopped investigation name the repository and a reason with no text of the model.

## Impact

- `src/devops_cli/ai/client/models.py`, `base.py`, `openai.py`, `claude.py`, `unified.py`, `ollama.py`, `streaming.py`: the error carries its status and timeout.
- `src/devops_cli/roadmap/agent_run.py`, `refine_investigation.py`, `refine.py`, `implement_step.py`: the text of a stopped run and the two warnings.
- `src/devops_cli/lang/en/messages.py`: the two warnings and the shared `class: message` text.
- `src/devops_cli/config/constants.py`: the one pair of limits for the message of a stopped run (the pair of the implement step, renamed).

## Feasibility

The premise holds in part. The evidence, read from the checkout and from the installed packages (pydantic-ai 2.59.0):

- `_failed_item` in `refine.py` logs `type(exc).__name__` and the violation count, with no repository. `investigate()` in `refine_investigation.py` returns `InvestigationStopped(type(stopped).__name__)`, and `_investigate` logs that class. Both match the issue.
- `_refine_error` is now `model_call_error` in `roadmap/agent_run.py`. It sorts a `ModelAPIError` into `AICredentialsError` (HTTP 401 or 403) or a plain `AIClientError` whose text holds only the class of the error. It does not keep the status or the timeout. The issue says it "already sorts them": it sorts the key refusal only. The change keeps the status and the timeout in two new fields.
- The provider mixins know the status and the timeout when they build the error: `_status_error` (`openai.py`), `_format_status_error` and `_format_network_error` (`base.py`), and the Claude status branch (`claude.py`). The fields cost one argument at each of those places.
- `AgentRunError.message` is a plain attribute. `UnexpectedModelBehavior.__str__` adds `, body:` and the body, so `str(stopped)` leaks model text and only `message` is safe. The helper of #2758 (`_stop_reason` in `implement_step.py`) builds its text from `str(stopped)`, so it did not fit. The change fixes it at the source: `_stop_reason` now reads `message` and shares the mask-and-cut function with refine (#2778).
- `message` is not always a fixed text. `models/openai.py` raises `UnexpectedModelBehavior(f"Invalid response from {system} chat completions endpoint: {e}")` with a pydantic `ValidationError`, whose later lines quote `input_value`, the reply. `_tool_execution.py` raises `Function tool calls must have unique `tool_call_id` values; duplicate `tool_call_id`s: {ids}`, and `tool_manager.py` raises `Tool {name!r} exceeded max retries count of N`: the id and the name come from the model's reply (a tool call to an unknown tool uses a name the model chose). The change therefore keeps the first line, hides each quoted part, stops at the first `:`, `;` or `=`, and drops the characters that cannot print. A test runs the repeated tool call id through a real investigation.
- First checks: `uv run devops ci test tests/test_roadmap_refine_investigation.py tests/test_roadmap_refine.py tests/test_roadmap_agent_run.py tests/test_ai_client_error_reason.py`.

## Existing Tool Considered

The standard library covers the text of a status: `http.client.responses` maps 408 to "Request Timeout". pydantic-ai gives `message`, `ModelHTTPError.status_code` and `ModelTimeoutError`. `mask_secrets` of the project masks the message. No outside tool covers a log line of this kind, and the change adds no parser and no dependency. The written cost is about 60 lines of code and 120 lines of tests: roughly 40,000 tokens to write and review, no upkeep, and about one hour of work.

The change deletes the second pair of limits and the `implement_stop_reason` text, which `run_stop_reason` replaces.
