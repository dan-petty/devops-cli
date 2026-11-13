## MODIFIED Requirements

### Requirement: The AI spend dashboard holds the reference prices
The hidden constant `reference_price_usd_per_token` of `k8s/devops/dashboards/ai-spend.json` SHALL hold, for each operation and token type, genai-prices' price of the default reference model of the operation. The default chat reference model SHALL be `gpt-4o`. No Prometheus recording rule SHALL hold a reference price.

#### Scenario: The dashboard holds genai-prices' price of the default references
- **WHEN** the dashboard and the Prometheus values are read
- **THEN** `DEFAULT_AI_REFERENCE_MODEL` is `gpt-4o`, the hidden constant holds for chat and embeddings, and for prompt and completion tokens, the price that genai-prices' bundled snapshot gives the default reference model of the operation, and no recording rule records a price
