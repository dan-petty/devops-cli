## ADDED Requirements

### Requirement: A chat call gives the cached prompt tokens of its reply
A chat call of `LLMClient`, streamed or not, SHALL give `track_request_spend` the prompt tokens that its reply names as cached in `usage.prompt_tokens_details.cached_tokens`. A failed attempt whose error body names that usage SHALL give them too. A call whose reply names no usage SHALL give 0 cached tokens.

#### Scenario: A chat call on the DeepSeek group with cached prompt tokens
- **WHEN** a chat call or a stream on the DeepSeek group gets a reply that names 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the ledger record costs 0.033477 USD

#### Scenario: A failed attempt whose error body names cached prompt tokens
- **WHEN** an attempt fails with an error body that names the same usage
- **THEN** its error record costs 0.033477 USD
