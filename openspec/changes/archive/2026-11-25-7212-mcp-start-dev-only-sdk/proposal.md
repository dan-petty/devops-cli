# Proposal: #7212

## Why
`devops mcp serve` of the newest release does not start: `ModuleNotFoundError: No module named 'grafana_foundation_sdk'`. #7185 made `k8s/catalog.py` import `grafana/service_dashboard.py`, which imports a dev-only package at module level. The MCP server imports each command module to build its tools.

## What Changes
- New module `grafana/service_specs.py` holds `ServiceSpec`, `load_specs` and the spec file name, with no Grafana SDK.
- `grafana/service_dashboard.py` and `k8s/catalog.py` import them from it.
- A test imports each command module with the `DEP004` packages of `deptry` blocked.

## Capabilities
### Modified Capabilities
- `mcp-server-image`: the commands import with no dev-only package.

## Impact
No change of a command, a setting or the dashboard JSON.

## Feasibility
The new test fails on `main` with `devops_cli.commands.k8s: No module named 'grafana_foundation_sdk.builders'`, the error of the crashing pod.

## Existing Tool Considered
`deptry` already reads the imports. Its rule `DEP004` ignores the SDK by name, and it cannot say which command imports reach a module. A lazy import in `k8s/catalog.py` would leave the model and the builder in one module, so the next import would break it again. The split costs no new tool.
