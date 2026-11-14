# Design: #5721

## Decisions

### 1. Enable developer sandbox
- Set `enableDevSandbox: true` in `jsonData`.
- This exposes the developer sandbox page in Grafana administration.

### 2. Enable MCP server
- Set `mcp.disabled: false` in `jsonData`.
- This registers the HTTP endpoint at `/api/plugins/grafana-llm-app/resources/mcp/grafana`.
- All standard toolsets default to enabled.

## Rejected Alternatives
- Leave MCP disabled: Rejected because agents require direct MCP access to telemetry and dashboards.
