# Proposal: #4545

## Why

The LiteLLM gateway series carry `client_ip` and `user_agent`. `client_ip` takes a new value with
each caller pod address, and the move of the roadmap jobs into short pods adds about 1,100
addresses and about 84,000 series a day. No panel, alert rule or test reads the two labels.
Closes #4545.

## What Changes

- The `http` endpoint of `k8s/llm/gateway/servicemonitor.yaml` drops `client_ip` and
  `user_agent` with one `labeldrop` rule each.
- `tests/gate/k8s_checks/llm_gateway.py` gains three checks: the endpoint holds the two rules and
  keeps its port, path and interval; no dashboard query names the labels; no alert expression
  names them.

## Capabilities

`gateway-caller-telemetry`: three requirements for the drop and its checks.

## Impact

The gateway ServiceMonitor and the `k8s` row. The spend totals keep the same values. No image,
command or gateway config change.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): no dashboard query or alert
expression names the two labels, and the ServiceMonitor holds one `http` endpoint. The `k8s` row
passes.

## Existing Tool Considered

The Prometheus Operator `metricRelabelings` drops the labels at scrape time and costs only the
manifest lines. LiteLLM has no setting for one label, and an endpoint `relabelings` cannot remove
a metric label. No new tool.
