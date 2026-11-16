## MODIFIED Requirements

### Requirement: The savings queries price the labelled local tokens at the reference price
Each savings query of the AI spend dashboard SHALL multiply the tokens of the token series that carry `local="true"` by the constant `reference_price_usd_per_token` on operation and token type, and SHALL read no series other than `devops_cli_ai_tokens_total`. No savings query SHALL select a series without the `local` label, no savings query SHALL map an absent `operation` label to chat, and the record SHALL hold no key of the deleted price rule.

#### Scenario: The savings queries
- **WHEN** The savings queries of the dashboard are read
- **THEN** Each one selects `local="true"` for the chat branch and for the embeddings branch, multiplies the tokens by the constant on operation and token type, reads only `devops_cli_ai_tokens_total`, and names no `local=""` selector and no `provider="gateway", server!="cache"` fallback

#### Scenario: The record of the current label set
- **WHEN** The recorded answer of the query of the panel Local Cloud Savings in Range is read
- **THEN** Every recorded series carries `local="true"` and `operation`, the record holds no key of the deleted price rule, its `expr` is the query of the panel, its `result` is the priced total of its series at the dashboard reference price, and `uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

#### Scenario: A range that ends before the price rule, with series from before the labels
- **WHEN** the recorded answer of Prometheus to the query of "Local Cloud Savings in Range" from 2026-10-01 to 2026-10-22 is read, over token series that have no `local` and no `operation` label
- **THEN** the query is the query of the panel, and the answer is the total of the recorded series at the dashboard prices, $423.03

#### Scenario: A range with series with and without the labels
- **WHEN** the recorded answer of Prometheus to the same query for a range with series with both labels, without `local`, and without `local` and `operation` is read
- **THEN** the answer is the total of the recorded series at the dashboard prices

## RENAMED Requirements

- FROM: `### Requirement: The savings queries price every range and every token series`
- TO: `### Requirement: The savings queries price the labelled local tokens at the reference price`
