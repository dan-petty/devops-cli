## MODIFIED Requirements

### Requirement: Hosted groups call a provider with an optional key
The gateway config SHALL serve the groups `gemini-3.8-flash`, `claude-sonnet-5-5`, `claude-haiku-5-5` and `deepseek-v4.1-flash-1017`. Each SHALL name a `gemini`, `anthropic` or `openrouter` backend with no `api_base`, set its window, and read its key from a variable of the gateway Deployment that is an optional key of the Secret `llm-gateway-secrets`.

#### Scenario: A hosted group without its key
- **WHEN** the gateway starts with no `GEMINI_API_KEY`
- **THEN** it serves every group, and a call to `gemini-3.8-flash` fails with an error that names the missing key

#### Scenario: The OpenRouter group without its key
- **WHEN** the gateway starts with no `OPENROUTER_API_KEY`
- **THEN** it serves every group, and a call to `deepseek-v4.1-flash-1017` fails with an error that names the missing key
