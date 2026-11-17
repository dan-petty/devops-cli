## MODIFIED Requirements

### Requirement: The server pod reads the token from its Secret
Deployment `mcp-server` SHALL set the variable `DEVOPS_CLI_MCP_TOKEN` with a `secretKeyRef` to the key `DEVOPS_CLI_MCP_TOKEN` of Secret `mcp-server`. A `secretKeyRef` of a manifest under `k8s/` to a Secret of the table SHALL name a key of that row.

#### Scenario: A test reads the manifest
- **WHEN** a person runs `kubectl -n devops get deployment mcp-server -o yaml` on the cluster
- **THEN** its container env holds the variable with that `secretKeyRef`
