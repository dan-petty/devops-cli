# Proposal: #4724

## Why

The AI spend dashboard previously read total spend only from devops-cli series. This missed external caller spend on the LiteLLM gateway and suffered from sparse OTLP series spikes. Panels also used obsolete metrics, fragile vector fallbacks, or dynamic ranges on run rates. Closes #4724.

## What Changes

- Panel 2: Reads total spend in range from `litellm_spend_metric_total` plus direct cloud spend from `devops_cli_ai_spend_usd_total{provider!="gateway"}`.
- Panel 7: Shows hourly spend as bars summing gateway spend and direct cloud spend.
- Panel 8: Drops the fragile `or sum(...) * 0` fallback on backend server spend bars.
- Panel 10 and 11: Updated to hourly bars with `: per hour` titles.
- Panels 16, 17, 18: Projected run-rate panels evaluate against a fixed 7-day baseline instead of `$__range`.
- Panel 20: Displays gateway slot wait duration at p95 grouped by outcome, replacing obsolete Ollama slot wait queries.
- Panel 24: Changes to a spend coverage stat panel dividing devops-cli gateway spend by gateway total spend.
- Adds promtool evaluation fixture tests in `tests/fixtures/dashboard_queries/ai-spend.yaml`.

## Capabilities

- `gateway-caller-telemetry`: Updated requirement for gateway coverage stat panel.
- `llm-slot-wait`: Updated requirement for gateway slot wait duration panel.

## Impact

The Grafana AI spend dashboard (`k8s/devops/dashboards/ai-spend.json`) and monitoring tests. Local savings panels remain unchanged for split issue #5784.

## Feasibility

Premise confirmed against real system and Prometheus dashboards on `origin/main`. LiteLLM exports `litellm_spend_metric_total` and devops-cli exports `devops_cli_ai_gateway_slot_wait_seconds`. All queries verified with promtool.

## Existing Tool Considered

Prometheus increase and rate operators with promtool unit tests evaluate queries natively without custom aggregation scripts.
