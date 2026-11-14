# Proposal: #5711

## Why
Grafana dashboards lack generative AI capabilities such as AI-generated panel descriptions, title suggestions, and query explanations because the `dashgpt` feature toggle is not enabled in Grafana's configuration. Closes #5711.

## What Changes
Enable `dashgpt` under `feature_toggles.enable` in `grafana.ini` within `k8s/monitoring/grafana-values.yaml`. Update `k8s/README.md` and add integration tests in `tests/commands/k8s/test_k8s_monitoring_integration.py`.

## Capabilities
- `grafana-plugins`

## Impact
Grafana enables dashboard-level generative AI features alongside the LLM app plugin. Operators can generate panel titles, summaries, and query explanations directly from dashboards.

## Feasibility
Grafana supports the `dashgpt` feature toggle under `[feature_toggles]` in `grafana.ini`. The Grafana Helm chart passes `grafana.ini` settings directly to Grafana. The change fits one pull request.

## Existing Tool Considered
Grafana native `dashgpt` feature toggle.
