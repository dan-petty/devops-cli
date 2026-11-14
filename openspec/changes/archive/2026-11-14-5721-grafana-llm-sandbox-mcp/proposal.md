# Proposal: #5721

## Why
Operators cannot test model completions interactively, and autonomous agents cannot query Grafana telemetry through standard MCP tools.
The `grafana-llm-app` plugin provides a developer sandbox and a Model Context Protocol server, but the provisioning configuration leaves them unconfigured. Closes #5721.

## What Changes
Enable `enableDevSandbox: true` and `mcp.disabled: false` in `k8s/monitoring/grafana-values.yaml`.
Update the integration tests and documentation.

## Capabilities
- `grafana-plugins`

## Impact
Operators can access `/a/grafana-llm-app/dev-sandbox` for prompt experimentation.
External agents can access Grafana telemetry through `/api/plugins/grafana-llm-app/resources/mcp/grafana`.

## Feasibility
The `grafana-llm-app` plugin supports `enableDevSandbox` and `mcp` in `jsonData`.
The change modifies only Kubernetes values, tests, and documentation.

## Existing Tool Considered
Native `grafana-llm-app` sandbox and MCP server capabilities.
