# Proposal: #4338

## Why

A stage item that fails with `AIClientError` shows no reason. `_failure_of` in `src/devops_cli/roadmap/stage/stage.py` sets an empty reason for it, and `_plan_each` logs nothing. The report reads `#3599 (AIClientError)`. A live run on 2026-11-10 ended after 2 minutes 48 seconds with that report, and the cause (a gateway error, a timeout, a cut at 125 seconds) stayed unknown. Closes #4338.

## What Changes

- `_failure_of` gives the reason of an `AIClientError`: the error code with the HTTP status or the timeout (`AIClientError.reason`), then the message of the error. `body_error_text` hides each quoted part of the message, because a provider can echo text of the model.
- `_failure_of` logs one warning line for it, with the item number, the class, the error code, the HTTP status and the timeout flag. The line holds no text of the message: CodeQL flags a log of that text as clear-text logging, and the Service already logs the reason inside its failure report.
- The reason of a `StructuredOutputValidationError` is unchanged and still holds no reply text.
- The change carries a spec delta because the failure text of an item is observable.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A failed model call names its reason

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`
- Consumers: the failure line of the report, the record of a failed item and the log of the Service now hold the reason.

## Feasibility

- Premise checked in the code at `origin/main` (699026ef): `_failure_of` has the branch `elif isinstance(exc, AIClientError): reason = ""`, and `model_call_error` in `src/devops_cli/roadmap/agent_run.py` builds the error with the text `model call failed (<class>)`, the HTTP status and the timeout flag. So the reason is known at the point where it is dropped.
- The new tests fail on the base: the reason is `''` and no line `model call failed` exists. `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py` passes after the change.
- `uv run devops roadmap eval stage --replay` is not affected: it replays the gates and makes no model call.

## Existing Tool Considered

`AIClientError.reason` and `body_error_text` already exist and give the safe text. No library is needed. Cost: about 15 000 tokens to build, 2 000 to keep and 45 minutes.
