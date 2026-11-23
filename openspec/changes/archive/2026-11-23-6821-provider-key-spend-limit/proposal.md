# Proposal: #6821

## Why
Since 2026-11-22 15:17 UTC the stage and refine jobs of the roadmap failed with `The model refused the key (HTTP 403).` (#6821). The key was not refused: the OpenRouter key behind the LLM gateway had used all of its total spend limit, and the gateway log gave `OpenrouterException - {"error":{"message":"Key limit exceeded (total limit). ...","code":403}}`. `model_call_error` (`roadmap/agent_run.py`) and the 401/403 branches of `LLMClient` map each 401 and 403 to a credentials error and do not read the body. So the Job report, the failure class and the alert send the person to the gateway key, and no signal names the spend limit.

## What Changes
- One rule in `ai/client/models.py`, `spend_limit_error`, reads the error text of a 401 or 403 reply. When the provider says that the key limit is exceeded (OpenRouter `Key limit exceeded`, which the LiteLLM gateway passes on in its message), it gives `AIKeySpendLimitError`. That error is a subclass of `AICredentialsError`, so each stop site that stops a run for a refused key stops for it too. Its text names the spend limit and the person step, and holds no key, URL or amount of the reply.
- `model_call_error`, the three 401/403 branches of `LLMClient` (the OpenAI-compatible status error, the status error of the shared transport, and the Claude status error) and the 401/403 branch of `fetch_model_info` use the rule. A 401 or 403 with another body gives the credentials error as before.
- The failure taxonomy gets the class `spend_limit`, with the default action `wait` and a wait of 1 hour. `CLASS_BY_EXCEPTION` maps `AIKeySpendLimitError` to it, and a text rule maps the error text in the log of a stage or implement Job to it. The class is a value of the `class` label of `devops_cli_service_stage_jobs_total`, `devops_cli_service_implement_failures_total` and `devops_cli_service_job_suspended`.
- A new critical alert `RoadmapProviderKeySpendLimit` of the group `roadmap-service` fires on those series of the class `spend_limit`. `RoadmapServiceJobsFailing` does not change.
- This changes a message, a failure class and an alert rule, which a consumer observes, so the change has spec deltas.

## Capabilities
- `ai-client-error-reason`: ADDED requirement for a spent provider key.
- `roadmap-failure-taxonomy`: MODIFIED class list, default actions, exception table and waits; ADDED requirement for the text rule of a spent provider key.
- `roadmap-service-alerts`: ADDED requirement for `RoadmapProviderKeySpendLimit`.

## Impact
- A model call that a spent provider key stops gives the error text `The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the key at the provider, or changes the key.` in the Job log, the Service log and the stop of an item.
- A stage Job that stops for it counts as `failed` with the class `spend_limit`, not `ci_infra`. A row of the Service that fails for it records `spend_limit`, not `provider`.
- The alert names the repository, the spend limit and the person step.
- The change fits one pull request.

## Feasibility
- Code: `model_call_error` returns `AICredentialsError("The model refused the key ...")` for each `ModelHTTPError` with status 401 or 403 (`roadmap/agent_run.py:66-67`). `OpenAICompatibleMixin._status_error`, `BaseLLMProviderMixin._provider_http_error` and the Claude status branch call `credentials_error` for each 401 or 403, and `fetch_model_info` does the same.
- Live log: `kubectl logs -n llm deploy/llm-gateway --since=30h` on 2026-11-23 holds `litellm.APIError: APIError: OpenrouterException - {"error":{"message":"Key limit exceeded (total limit). Manage it usin...`. The gateway passes that text on in the `message` of its error reply.
- Live metrics (`devops prometheus query`, 2026-11-23): in the last 24 hours, 49 stage Jobs of `dan-petty/devops-cli` counted as `failed` with `class="ci_infra"`, and the refine rows of four repositories held `class="provider"` in `devops_cli_service_job_retry_after_seconds`.
- pydantic-ai 2.71.0 (`_model_errors.http_status_category`) gives `ModelAuthenticationError` for each 401 and 403, and `ModelQuotaExceededError` only for a 402 or an OpenAI quota code. It does not read OpenRouter's 403 key limit.

## Existing Tool Considered
- pydantic-ai `ModelQuotaExceededError` covers a spent account where the provider says so with a 402 or a quota code. An OpenRouter key limit comes as a 403 and is a `ModelAuthenticationError`, so pydantic-ai does not cover the case. `LLMClient` does not use pydantic-ai, so the rule must also read its bodies.
- LiteLLM maps the OpenRouter reply to `litellm.APIError` with status 403 and keeps the text, which is what the rule reads. Its `BudgetExceededError` is for the budget of a LiteLLM key, not of the provider key.
- Cost to build: one function, one error class, one failure class, one text rule and one alert, about 40 k tokens and 1 hour. No internal code is deleted; `_REFUSED_KEY_STATUSES` of `agent_run.py` stays the status check of `model_call_error`.
