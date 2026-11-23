## ADDED Requirements

### Requirement: A spent provider key is a spend-limit error
`spend_limit_error` in `ai/client/models.py` SHALL be the one rule for the body of a 401 or 403 reply. When the error text of the body (its `message` or `error`, or the body itself as a string or a JSON text) holds `Key limit exceeded` with no regard to case, it SHALL give `AIKeySpendLimitError`, a subclass of `AICredentialsError`. Its text SHALL name the spend limit, the status and the person step, and SHALL hold no text of the body.

#### Scenario: The text of the error
- **WHEN** the rule reads a 403 body whose `message` is the gateway's `litellm.APIError: APIError: OpenrouterException - {"error":{"message":"Key limit exceeded (total limit). ... $5.00 of $5.00 used; does not reset.","code":403}}`
- **THEN** it gives `AIKeySpendLimitError` with the text `The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the key at the provider, or changes the key.`, which holds no `$` amount, no key and no URL

#### Scenario: The text in another field
- **WHEN** a 403 body holds `Key limit exceeded` only in a field that is not `message` or `error`
- **THEN** the rule gives no spend-limit error

### Requirement: Each refused-key site uses the rule
`model_call_error`, the 401/403 branches of `LLMClient` and `fetch_model_info` SHALL call `spend_limit_error` before they build their credentials error, and SHALL give that credentials error for any other body.

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
