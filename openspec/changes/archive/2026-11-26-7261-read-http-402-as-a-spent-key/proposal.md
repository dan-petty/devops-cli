# Proposal: #7261

## Why
On 2026-11-25 from 13:12Z to 20:43Z the key of the hosted provider had too few credits (#7261). The provider answered HTTP 402 (`This request requires more credits, or fewer max_tokens`), and the LLM gateway passed the status on. `spend_limit_error` (`ai/client/models.py`) reads only the text `Key limit exceeded`, and each caller asks it only for HTTP 401 and 403 (#6821). So `model_call_error` gave the 402 the plain `AIClientError`, and the failure class was `provider`. A job fails one item for an `AIClientError` and goes on to the next item. It stops its round only for `AICredentialsError`. So no round failed, the failure ledger of the Service suspended no row, and `RoadmapProviderKeySpendLimit` did not fire. In those 8 hours the result lines hold 439 attempts with `class=provider` and 4 successes.

## What Changes
- `spend_limit_error` gives `AIKeySpendLimitError` for each HTTP 402, with no test of the body text. The rule for the text of a 401 or 403 does not change.
- One set, `KEY_STOP_STATUSES` (401, 402, 403), names the statuses that stop a whole run. `model_call_error` and the status branches of `LLMClient` (the OpenAI-compatible status error, the status error of the shared transport and the Claude status error) read it and ask the rule first.
- `model_call_error` also gives `AIKeySpendLimitError` for `ModelQuotaExceededError` of pydantic-ai, which that library raises when a provider reports that its quota, its credits or its billing is exhausted. An error with no HTTP status, as from an error event inside a stream, gets the status 402 in its text.
- This changes the error class and the failure class of a reply that a consumer observes, so the change has a spec delta.

## Capabilities
- `ai-client-error-reason`: MODIFIED requirements for the spend-limit rule and for the sites that use it.

## Impact
- A model call that gets HTTP 402 gives the error text `The provider key reached its spend limit (HTTP 402). A person raises the spend limit of the key at the provider, or changes the key.` in the Job log, the Service log and the stop of an item.
- The failure class is `spend_limit`, not `provider`. Each job stops its round at the first such call, and no item gets a failure. The failure ledger suspends the row after `service.max_failed_rounds` rounds and probes each hour. `RoadmapProviderKeySpendLimit` fires as for the 403 of #6821.
- An implement item that the error stops stays Blocked until a comment `implement: retry`, because the action of `spend_limit` is `wait`. Before, the class `provider` let the Service start the Job again, and each new Job failed the same way.
- An HTTP 429 from the cooldown of the gateway keeps the class `provider`: it names no cause.
- The change fits one pull request.

## Feasibility
- Code: `model_call_error` asks `spend_limit_error` only when the status is in `_REFUSED_KEY_STATUSES` (401, 403) (`roadmap/agent_run.py`). `spend_limit_error` returns None when the error text does not hold `Key limit exceeded` (`ai/client/models.py`). `refine`, `alternatives`, stage and implement each re-raise `AICredentialsError` and fail only the item for another `AIClientError`.
- Live log (Loki, namespace `llm`, 2026-11-25): the gateway holds `OpenrouterException - {"error":{"message":"This request requires more credits, or fewer max_tokens. ...","code":402}}` from 13:12Z to 20:43Z. The Service log of that time holds `HTTP 402 Payment Required` in 203 lines and `HTTP 429 Too Many Requests` in 199 lines.
- Result lines of that time: 439 attempts with `class=provider` (refine 315 on 119 items, stage 87, alternatives 34, implement 3).
- pydantic-ai 2.75.0 (`_model_errors.py`) gives `ModelQuotaExceededError` for each 402 and for the quota codes of the providers.

## Existing Tool Considered
- pydantic-ai (in use) already classes the reply: `ModelQuotaExceededError` covers HTTP 402 and the quota errors of each provider. `model_call_error` reads that class. `LLMClient` does not use pydantic-ai, so its status branches read the same status through `spend_limit_error`.
- LiteLLM (in use) passes the 402 on with its status. Its `BudgetExceededError` is for the budget of a LiteLLM key, not of the provider key.
- Cost to build: one status in the rule, one set of statuses and one class test, about 30 k tokens and 1 hour. `_REFUSED_KEY_STATUSES` of `agent_run.py` is deleted, because `KEY_STOP_STATUSES` replaces it.
