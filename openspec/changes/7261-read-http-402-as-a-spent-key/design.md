# Design

## Decisions
- **The status decides, not the text.** HTTP 402 Payment Required has one meaning for each provider: the key or its account cannot pay for the request. So `spend_limit_error` reads no body text for a 402. The rule for a 401 or 403 keeps its text test, because those statuses also mean a refused key.
- **One builder for the error.** `spent_key_error` builds `AIKeySpendLimitError` from the status. `spend_limit_error` and `model_call_error` call it, so the text has one source and holds no text of a reply.
- **One set of statuses.** `KEY_STOP_STATUSES` in `ai/client/models.py` replaces the literal `(401, 403)` of three sites and `_REFUSED_KEY_STATUSES` of `agent_run.py`. `fetch_model_info` keeps its 401/403 branch: the model list of the gateway costs no credits, so it gets no 402.
- **The class of the library comes first.** `model_call_error` tests `ModelQuotaExceededError` before the status, so a quota error with another status (OpenAI `insufficient_quota` comes as a 429) is also a spent key and keeps its own status in the text.
- **No new park mechanism.** `AIKeySpendLimitError` is an `AICredentialsError`, so each job stops its round for it, and the failure ledger of the Service suspends the row and probes each hour (`RETRY_AFTER`). The alert `RoadmapProviderKeySpendLimit` reads the class `spend_limit`. The change adds no health probe, no key in Valkey and no setting.

## Rejected alternatives
- **Read the text `requires more credits`.** A second text rule follows one provider and breaks when that text changes. The status is stable, and pydantic-ai uses the same rule.
- **A gateway health probe before each round (#5967).** The gateway stayed ready on 2026-11-25, and a small request still passed, because the key could pay for it. A probe does not see this case.
- **Class the 429 of the gateway cooldown as a spent key.** The 429 names no cause, and a short provider failure gives the same reply.
