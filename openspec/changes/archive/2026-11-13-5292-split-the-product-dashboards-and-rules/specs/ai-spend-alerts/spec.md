## MODIFIED Requirements

### Requirement: The spend alerts have their own rule group
The rule group `ai-spend` in `k8s/devops/monitoring/prometheus-rules-values.yaml` SHALL hold the warning alerts `ClaudeSpendDailyHigh` and `HostedSpendDailyHigh`. promtool SHALL accept them. The alert table of `k8s/README.md` SHALL have a row for each alert, and the row SHALL give the first step: read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job.

#### Scenario: The group and the README
- **WHEN** a test reads the group and the alert table of `k8s/README.md`
- **THEN** both alerts have severity `warning`, read only `devops_cli_ai_spend_usd_total`, and have a row in the table that names the label `end_user`
