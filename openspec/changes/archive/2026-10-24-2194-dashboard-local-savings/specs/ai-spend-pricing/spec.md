# Spec Delta

## REMOVED Requirements

### Requirement: One recording rule prices the local tokens of every process
**Reason**: A recording rule has samples only from its first evaluation, so the savings panels showed $0 for each range that ended before it (#2194).
**Migration**: The hidden dashboard constant `reference_price_usd_per_token` in `k8s/monitoring/dashboards/ai-spend.json` holds the prices. The requirements "The AI spend dashboard holds the reference prices" and "The savings queries price every range and every token series" hold the rule.

## ADDED Requirements

### Requirement: The AI spend dashboard holds the reference prices
The hidden constant `reference_price_usd_per_token` of `k8s/monitoring/dashboards/ai-spend.json` SHALL hold, for each operation and token type, genai-prices' price of the default reference model of the operation. The default chat reference model SHALL be `gpt-4o`. No Prometheus recording rule SHALL hold a reference price.

#### Scenario: The dashboard holds genai-prices' price of the default references
- **WHEN** the dashboard and the Prometheus values are read
- **THEN** `DEFAULT_AI_REFERENCE_MODEL` is `gpt-4o`, the hidden constant holds for chat and embeddings, and for prompt and completion tokens, the price that genai-prices' bundled snapshot gives the default reference model of the operation, and no recording rule records a price

### Requirement: The savings queries price every range and every token series
Each savings query of the AI spend dashboard SHALL multiply the local tokens by the constant `reference_price_usd_per_token` on operation and token type, and SHALL read no series other than `devops_cli_ai_tokens_total`. A token series without the `local` label SHALL be local when its provider is `gateway` and its server is not `cache`. A token series without the `operation` label SHALL be chat.

#### Scenario: The savings queries
- **WHEN** the savings queries of the dashboard are read
- **THEN** each one multiplies the local tokens of every kind of token series by the constant on operation and token type, and reads only `devops_cli_ai_tokens_total`

#### Scenario: A range that ends before the price rule, with series from before the labels
- **WHEN** the recorded answer of Prometheus to the query of "Local Cloud Savings in Range" from 2026-10-01 to 2026-10-22 is read, over token series that have no `local` and no `operation` label
- **THEN** the query is the query of the panel, and the answer is the total of the recorded series at the dashboard prices, $423.03

#### Scenario: A range with series with and without the labels
- **WHEN** the recorded answer of Prometheus to the same query for a range with series with both labels, without `local`, and without `local` and `operation` is read
- **THEN** the answer is the total of the recorded series at the dashboard prices
