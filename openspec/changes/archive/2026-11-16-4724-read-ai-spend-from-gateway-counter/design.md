# Design

## Decisions

- **Sum gateway counter and direct cloud spend in Panel 2 and 7**: Read gateway total spend from `litellm_spend_metric_total` and non-gateway spend from `devops_cli_ai_spend_usd_total{provider!="gateway"}` with `or vector(0)` on each term.
- **Pin run rates to fixed 7d baseline**: Run rates (Panels 16, 17, 18) use `[7d]` window so range selection changes in Grafana do not fluctuate projected estimates.
- **Group slot wait by outcome**: Panel 20 uses `devops_cli_ai_gateway_slot_wait_seconds` with `outcome` grouping at 0.95 quantile and count.
- **Drop vector matching zero fallback in Panel 8**: Grouped backend server hourly bars use raw `sum by (server, backend, provider) (increase(...))` without vector multiplication.
- **Leave local savings queries unchanged**: Local savings query restructuring was split into issue #5784 because it requires live Prometheus recordings.

## Rejected alternatives

- **Read all spend from devops-cli**: Rejected because it misses third-party caller traffic to the LiteLLM gateway.
- **Dynamic range for run rates**: Rejected because selecting 6h projected huge variance while 7d offers stable estimation.
