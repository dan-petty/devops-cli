## MODIFIED Requirements

### Requirement: A spent provider key is a spend-limit error
`spend_limit_error` in `ai/client/models.py` SHALL be the one rule for a 401, 402 or 403 reply. It SHALL give `AIKeySpendLimitError`, a subclass of `AICredentialsError`, for a 402 with any body, and for a 401 or 403 whose error text (the `message` or `error` of the body, or the body as a string or a JSON text) holds `Key limit exceeded` with no regard to case. The error text SHALL name the spend limit, the status and the person step, and SHALL hold no text of the body.

#### Scenario: The text of the error
- **WHEN** the rule reads a 403 body whose `message` is the gateway's `litellm.APIError: APIError: OpenrouterException - {"error":{"message":"Key limit exceeded (total limit). ... $5.00 of $5.00 used; does not reset.","code":403}}`
- **THEN** it gives `AIKeySpendLimitError` with the text `The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the key at the provider, or changes the key.`, which holds no `$` amount, no key and no URL

#### Scenario: The text in another field
- **WHEN** a 403 body holds `Key limit exceeded` only in a field that is not `message` or `error`
- **THEN** the rule gives no spend-limit error

#### Scenario: A reply that asks for payment
- **WHEN** the rule reads a 402 whose body is the gateway's `This request requires more credits, or fewer max_tokens` message, another text, or no body
- **THEN** it gives `AIKeySpendLimitError` with the text `The provider key reached its spend limit (HTTP 402). A person raises the spend limit of the key at the provider, or changes the key.`, which holds no amount and no URL of the body

### Requirement: Each refused-key site uses the rule
`model_call_error` and the status branches of `LLMClient` SHALL call `spend_limit_error` for each status of `KEY_STOP_STATUSES` (401, 402, 403), and `fetch_model_info` for a 401 or 403, before they build their credentials error. They SHALL give that credentials error for a 401 or 403 with any other body. `model_call_error` SHALL also give `AIKeySpendLimitError` for a `ModelQuotaExceededError` of pydantic-ai, with the status of the error, or with 402 when it has none.

#### Scenario: A model call of an agent run on a spent key
- **WHEN** an agent run fails with `ModelHTTPError` 403 whose body holds the gateway's key-limit message
- **THEN** `model_call_error` gives `AIKeySpendLimitError`

#### Scenario: A refused key keeps the credentials error
- **WHEN** an agent run fails with `ModelHTTPError` 403 or 401 whose body says `Authentication Error`
- **THEN** `model_call_error` gives an `AICredentialsError` that is not an `AIKeySpendLimitError`, with the text `The model refused the key (HTTP 403).` or `(HTTP 401).`

#### Scenario: A gateway call of LLMClient on a spent key
- **WHEN** a chat or a stream of `LLMClient` through the gateway gets HTTP 403 with the gateway's key-limit body
- **THEN** it raises `AIKeySpendLimitError` after one request, and a 403 with another body still raises the error that names the key sources

#### Scenario: A Claude call on a spent key
- **WHEN** a Claude call through the shared client gets HTTP 403 whose error message holds `Key limit exceeded`
- **THEN** it raises `AIKeySpendLimitError`

#### Scenario: The model list of the gateway on a spent key
- **WHEN** `fetch_model_info` gets HTTP 403 whose body holds `Key limit exceeded`
- **THEN** it raises `AIKeySpendLimitError`

#### Scenario: A model call of an agent run that asks for payment
- **WHEN** an agent run fails with `ModelHTTPError` 402, or with a `ModelQuotaExceededError` that has no HTTP status
- **THEN** `model_call_error` gives `AIKeySpendLimitError` that names HTTP 402, and `failure_class_of` gives the class `spend_limit` for it

#### Scenario: A quota error with another status
- **WHEN** an agent run fails with a `ModelQuotaExceededError` whose HTTP status is 429
- **THEN** `model_call_error` gives `AIKeySpendLimitError` that names HTTP 429

#### Scenario: The cooldown of the gateway is no spent key
- **WHEN** an agent run fails with `ModelHTTPError` 429 whose body says `No deployments available for selected model`
- **THEN** `model_call_error` gives an `AIClientError` that is not an `AICredentialsError`, and `failure_class_of` gives the class `provider`

#### Scenario: A call of LLMClient that asks for payment
- **WHEN** a chat or a stream of `LLMClient` through the gateway, or a Claude call, gets HTTP 402
- **THEN** it raises `AIKeySpendLimitError` after one request
