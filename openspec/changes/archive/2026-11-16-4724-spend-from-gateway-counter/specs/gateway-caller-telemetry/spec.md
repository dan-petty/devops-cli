## ADDED Requirements

### Requirement: The spend panels take gateway spend from the gateway
Cloud Spend in Range, the spend target of each projection, Spend: USD per hour and Spend by model: USD per hour SHALL read the gateway's spend counter `litellm_spend_metric_total` for a call through the gateway, and `devops_cli_ai_spend_usd_total{provider!="gateway"}` for a call that did not go through the gateway. No spend panel SHALL select devops-cli's `provider="gateway"` spend. Each stat SHALL fall back to 0 for each counter.

#### Scenario: Spend in range adds the gateway and the direct calls
- **WHEN** promtool evaluates Cloud Spend in Range over 24 h of fixture series: the gateway counter at $1 an hour, devops-cli's gateway spend at $0.75 an hour and its direct spend at $0.25 an hour
- **THEN** the panel gives $30, and devops-cli's gateway spend adds nothing

#### Scenario: The panel queries
- **WHEN** a test reads the spend targets of the six spend panels
- **THEN** each reads both counters, each devops-cli spend selector is `devops_cli_ai_spend_usd_total{provider!="gateway"}`, and each stat falls back to 0

### Requirement: A spend projection reads the last 7 days
The spend target of Projected 30-Day, 90-Day and 1-Year Run Rate SHALL read the spend rate of the last 7 days (`[7d]`), and SHALL NOT read `$__range`.

#### Scenario: The projection does not follow the range
- **WHEN** promtool evaluates the spend target of Projected 30-Day Run Rate with a range of 6 h and of 7 d
- **THEN** both give $900, the spend of 30 days at the rate of the last 7 days

### Requirement: The hourly spend panels draw bars that follow the step
Spend: USD per hour and Spend by model: USD per hour SHALL draw bars of `increase(...[$__interval])` with a Min interval of `1h`, and SHALL follow the chart rules of the dashboards, so they SHALL NOT use `or vector(0)`.

#### Scenario: The hourly bars add up to the spend of the range
- **WHEN** promtool adds the 24 hourly bars of Spend: USD per hour and of Spend by model: USD per hour over the fixture series
- **THEN** the bars of Spend: USD per hour add up to $30, and the bars by model give $24 for the hosted model, $6 for the direct model and no bar for the local model that spent $0

#### Scenario: The panel settings
- **WHEN** a test reads the two panels
- **THEN** each has the Min interval `1h`, the draw style `bars` and the unit `currencyUSD`, and the chart rules find no problem

## MODIFIED Requirements

### Requirement: The dashboard shows the gateway's attempts, callers and coverage
The AI spend dashboard SHALL hold Gateway Attempts by Status (the gateway's chat and embedding requests by `status_code`), Gateway Requests and Tokens by Caller (its replied requests and its tokens by `end_user`), and devops-cli Coverage of Gateway Spend (devops-cli's `provider="gateway"` spend over the gateway's spend counter `litellm_spend_metric_total`, as a stat in percent that shows red under 0.95 and over 1.05).

#### Scenario: The gateway row
- **WHEN** the three panels are read
- **THEN** the attempts group by `status_code` and match no status, the caller panel's two queries group by `end_user`, and the coverage stat divides `devops_cli_ai_spend_usd_total{provider="gateway"}` by `litellm_spend_metric_total`, in `percentunit`, with the threshold steps red, 0.95 text and 1.05 red

#### Scenario: The coverage of the fixture series
- **WHEN** promtool evaluates the coverage stat over 24 h of fixture series in which devops-cli counts $0.75 of each $1 that the gateway counts
- **THEN** the stat gives 0.75
