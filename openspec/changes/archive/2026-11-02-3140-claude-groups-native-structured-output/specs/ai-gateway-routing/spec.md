## MODIFIED Requirements

### Requirement: A Claude group sets its prices and drops refused parameters
A Claude group SHALL set its input and output prices, because the cost map of the pinned image lacks the model. It SHALL drop `temperature`, `top_p` and `top_k`, which the provider API refuses. It SHALL set `supports_native_structured_output` and `supports_response_schema`, so that a structured reply uses the native format and not a forced tool call, which the API refuses for Sonnet 5.5.

#### Scenario: A Claude call with sampling parameters
- **WHEN** a caller sends `temperature` and `top_p` to `claude-sonnet-5-5`
- **THEN** the request to the provider holds neither

#### Scenario: A structured reply from a Claude group
- **WHEN** a caller sends a `response_format` with a JSON schema to `claude-sonnet-5-5`
- **THEN** the gateway answers with JSON that matches the schema, and sends no forced tool call
