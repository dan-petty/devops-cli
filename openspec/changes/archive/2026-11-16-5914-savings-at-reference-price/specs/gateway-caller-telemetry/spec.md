## MODIFIED Requirements

### Requirement: The dashboard reads only gateway series that the gateway serves
Each gateway series that `ai-spend.json` reads SHALL be in the LiteLLM capture with each label that a query matches or groups by, and SHALL be read through `rate(` or `increase(`. A label that the query sets with `label_replace` SHALL need no gateway series that carries it, and a gateway label name in a string of the query SHALL NOT count as a read of a series.

#### Scenario: A raw read of a gateway counter
- **WHEN** a query reads `litellm_total_tokens_metric_total` outside `rate(` and `increase(`
- **THEN** the check names that read

#### Scenario: A label that the query sets
- **WHEN** a query groups by `backend`, which a `label_replace` of the query sets from `litellm_model_name`, and another query groups by `backend` with no `label_replace`
- **THEN** the check names only the second query

### Requirement: The spend panels take gateway spend from the gateway
Cloud Spend in Range, the spend target of each projection, Spend: USD per hour and Spend by provider and model: USD per hour SHALL read the gateway's spend counter `litellm_spend_metric_total` for a call through the gateway, and `devops_cli_ai_spend_usd_total{provider!="gateway"}` for a call that did not go through the gateway. No spend panel SHALL select devops-cli's `provider="gateway"` spend. Each stat SHALL fall back to 0 for each counter.

#### Scenario: Spend in range adds the gateway and the direct calls
- **WHEN** promtool evaluates Cloud Spend in Range over 24 h of fixture series: the gateway counter at $1 an hour, devops-cli's gateway spend at $0.75 an hour and its direct spend at $0.25 an hour
- **THEN** the panel gives $30, and devops-cli's gateway spend adds nothing

#### Scenario: The panel queries
- **WHEN** a test reads the spend targets of the six spend panels
- **THEN** each reads both counters, each devops-cli spend selector is `devops_cli_ai_spend_usd_total{provider!="gateway"}`, and each stat falls back to 0

### Requirement: The hourly spend panels draw bars that follow the step
Spend: USD per hour and Spend by provider and model: USD per hour SHALL draw bars of `increase(...[$__interval])` with a Min interval of `1h`, and SHALL follow the chart rules of the dashboards, so they SHALL NOT use `or vector(0)`.

#### Scenario: The hourly bars add up to the spend of the range
- **WHEN** promtool adds the 24 hourly bars of Spend: USD per hour and of Spend by provider and model: USD per hour over the fixture series
- **THEN** the bars of Spend: USD per hour add up to $30, and the bars by provider and model give $24 for the hosted model, $6 for the direct model and no bar for the local model that spent $0

#### Scenario: The panel settings
- **WHEN** a test reads the two panels
- **THEN** each has the Min interval `1h`, the draw style `bars` and the unit `currencyUSD`, and the chart rules find no problem

## ADDED Requirements

### Requirement: The spend by provider panel names the provider first
The panel Spend by provider and model: USD per hour SHALL name the hosted provider first in its title and in each legend: `{{api_provider}}: {{model}}` for a call through the gateway and `{{provider}}: {{model}}` for a direct call.

#### Scenario: The legends
- **WHEN** a test reads the targets of the panel
- **THEN** the legends are `{{api_provider}}: {{model}}` and `{{provider}}: {{model}}`
