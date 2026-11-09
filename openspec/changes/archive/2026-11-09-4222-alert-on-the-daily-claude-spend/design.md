# Design

## Decisions

- Use `devops_cli_ai_spend_usd_total` and no other series. The project owns it, a test pins its name, and its `model` label is the model that the client asked for.
- Use `increase(...[24h])` summed over all series. `increase` adds the value before a counter reset, so a pod restart in the window does not hide the spend. A sum over `job` and `instance` counts a workstation and the Service together.
- Select `claude-sonnet-5-5` with an exact `model` matcher in `ClaudeSpendDailyHigh`, and no matcher in `HostedSpendDailyHigh`. A local model adds 0, so the second sum is the spend of the hosted models.
- Use `for: 0m` and severity `warning`. The window of 24 hours smooths the series, and a stage burst must show at once.
- A series that starts inside the window loses its first sample in `increase`. The series of the Service live for many days, and the first request of a new workstation process is small, so the rules use the plain form and do not copy the longer form of `Crawl4AIFetchesFailing`.
- The README rows go in the alert table of the section "Alerting", and the descriptions point to it.

## Rejected alternatives

- `litellm_spend_metric_total`: it needs no #3665, but its live series is not verified to carry a Claude cost, and its labels differ. Using it with the counter would count the spend twice.
- The `max_budget` of LiteLLM per key: it stops a key at a limit and sends no alert. The owner wants a signal before the baseline (#3566).
- A threshold per model: a model list in the rule needs an edit for each new hosted model. `HostedSpendDailyHigh` covers every model with one sum.
