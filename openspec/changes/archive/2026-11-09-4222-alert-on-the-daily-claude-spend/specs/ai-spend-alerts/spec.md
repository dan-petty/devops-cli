## Purpose
The alert rules that tell an operator when the hosted AI spend of one day is high: for the model `claude-sonnet-5-5` and for all hosted models together. Without them a failed stage burst that spends about 20 USD per hour shows only when a person reads the cost page.

## ADDED Requirements

### Requirement: The spend alerts have their own rule group
The rule group `ai-spend` in `k8s/monitoring/prometheus-values.yaml` SHALL hold the warning alerts `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh`. promtool SHALL accept them. The alert table of `k8s/README.md` SHALL have a row for each alert, and the row SHALL give the first step: read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job.

#### Scenario: The group and the README
- **WHEN** a test reads the group and the alert table of `k8s/README.md`
- **THEN** both alerts have severity `warning`, read only `devops_cli_ai_spend_usd_total`, and have a row in the table that names the label `end_user`

### Requirement: A high Claude spend warns
`ClaudeSpendDailyHigh` SHALL fire when the sum of the 24 hour increase of `devops_cli_ai_spend_usd_total{model="claude-sonnet-5-5"}` is above 15 USD. It SHALL add the increases of every series, and it SHALL keep the spend of a series that resets to 0 in the window.

#### Scenario: The spend rises 1 USD per hour
- **WHEN** `promtool test rules` evaluates a series with `model="claude-sonnet-5-5"` that rises by 1 USD per hour for 24 hours
- **THEN** `ClaudeSpendDailyHigh` fires

#### Scenario: A pod restart in the window
- **WHEN** `promtool test rules` evaluates a Claude series that rises by 10 USD, resets to 0, and rises by 13 USD
- **THEN** `ClaudeSpendDailyHigh` fires and `HostedSpendDailyHigh` stays quiet

#### Scenario: A workstation and the Service
- **WHEN** `promtool test rules` evaluates two Claude series of the jobs `devops-cli` and `roadmap-service` of 11 USD each
- **THEN** `ClaudeSpendDailyHigh` fires

#### Scenario: A normal day
- **WHEN** `promtool test rules` evaluates a Claude series of 5.59 USD in 24 hours, and a local series of 0 USD
- **THEN** neither alert fires

### Requirement: A high hosted spend warns
`HostedSpendDailyHigh` SHALL fire when the sum of the 24 hour increase of `devops_cli_ai_spend_usd_total` of every model is above 25 USD. A model other than `claude-sonnet-5-5` SHALL count for this alert and SHALL NOT count for `ClaudeSpendDailyHigh`.

#### Scenario: Another hosted model spends 30 USD
- **WHEN** `promtool test rules` evaluates a series of another hosted model that rises by 30 USD in 24 hours
- **THEN** `HostedSpendDailyHigh` fires and `ClaudeSpendDailyHigh` stays quiet
