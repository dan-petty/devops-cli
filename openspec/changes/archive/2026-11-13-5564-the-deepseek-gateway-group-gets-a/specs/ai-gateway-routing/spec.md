## ADDED Requirements

### Requirement: The dated DeepSeek group falls back to the undated model with the same provider filter
The gateway SHALL send a failed call of the hosted group `deepseek-v4.1-flash-1017` to the hosted group `deepseek-v4.1-flash`, which calls `openrouter/deepseek/deepseek-v4.1-flash` with no `floor` route and with the same fp8 and `data_collection: deny` filters.

#### Scenario: A timeout of the dated group falls back
- **WHEN** a call of `deepseek-v4.1-flash-1017` fails, for example with an OpenRouter timeout
- **THEN** the gateway sends the call to `deepseek-v4.1-flash`

#### Scenario: The fallback keeps the privacy filter
- **WHEN** the gateway config is read
- **THEN** both DeepSeek groups ask OpenRouter for fp8 weights and `data_collection: deny`
