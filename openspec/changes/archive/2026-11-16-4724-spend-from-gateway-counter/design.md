# Design

## Decisions

- **Gateway counter for gateway calls.** A gateway call is spend of `litellm_spend_metric_total`, for every caller. devops-cli's `devops_cli_ai_spend_usd_total` adds only `provider!="gateway"`, the calls that did not go through the gateway. This is the rule that AI Requests in Range and Tokens Processed in Range already use (#1668).
- **A union, not a sum of two sums, in a time series.** Spend: USD per hour is `sum(increase(gateway[$__interval]) or increase(direct[$__interval]))`. The two sides never have the same label set, because only devops-cli's series have `provider`. So `or` keeps each series of both sides, and the panel needs no `or vector(0)`, which the chart rules of #4707 permit only in a stat.
- **Hourly bars.** Each spend bar is `increase(...[$__interval])` with a Min interval of 1h and `barAlignment` -1, as Traffic: calls per hour of `devops-cli.json` does. The bars of a range add up to the spend of the range. The rolling lines go: a bar of 1 h is the mean of its hour, and a rolling window that is longer than the step counts a sample in more than one point.
- **Stacked bars by model.** The bars of Spend by model: USD per hour stack, so one hour adds up to the bar of Spend: USD per hour. `> 0` removes a model with no spend in an hour, so a local model gives no bar and no legend entry.
- **A 7-day projection baseline.** The spend target is `rate(...[7d]) * 86400 * N`, which is `increase(...[7d]) / 7 * N`. The rate form keeps the operator ` / ` out of the query, so the chart rules read it as a count and not as a share. The legend names the baseline. The savings target keeps `$__range` until #5914 and #5784 change it, and the panel description tells the two baselines.
- **Spend coverage with a band.** The coverage stat shows red under 0.95, as #4724 asks, and also over 1.05, because a share over 1 is also a defect of the measure. The stat has no `max`, so a share over 100 % shows its value.

## Rejected alternatives

- **Keep devops-cli's spend counter for all calls.** On 2026-11-16 it holds 54 % of the gateway spend for 6 h ($0.67 of $1.23) and 77.5 % for 7 d. A Job pod sends about 6 samples for each series in 6 h, so `rate(...[5m])` gives no value for it.
- **Add both counters for each call.** It counts a gateway call twice: in the fixture, Cloud Spend in Range would give $48 in place of $30.
- **Keep the lines with `rate(...[$__rate_interval])`.** It follows the step, but at a range of 6 h `$__rate_interval` is 4 min (four times the `timeInterval` of 60 s), and a series with a few samples an hour has no two samples in that window. Bars of 1 h hold about 4 samples of a series that the Service sends each 15 min.
- **Filter the gateway counter by `user_agent`.** The gateway ServiceMonitor drops `user_agent` (#4545). On 2026-11-13 other callers spent $0.0012 in 7 d (#4724), so the filter changes almost nothing.
- **Write the projection as `increase(...[7d]) / 7 * N`.** It gives the same value, but the chart rules read a query with ` / ` as a share, and the savings target of the same panel is a count.
