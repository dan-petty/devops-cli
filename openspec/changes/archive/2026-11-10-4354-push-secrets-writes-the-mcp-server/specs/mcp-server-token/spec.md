## Purpose
How the bearer token of the MCP server reaches the cluster: one managed keyring credential, the Secret that the server pod reads, and the keys that the stage and implement clients read.

## ADDED Requirements

### Requirement: One keyring value feeds the server and the clients
The secret table SHALL hold the key `DEVOPS_CLI_MCP_TOKEN` of Secret `devops/mcp-server`, required, and the keys `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` of Secret `devops/devops-cli`, not required. All three keys SHALL read the keyring entry `mcp_token` of the credential `mcp.token`.

#### Scenario: A test reads the secret table
- **WHEN** a test reads the secret table
- **THEN** the three keys name the keyring entry `mcp_token`, and the two client keys adopt from `devops/mcp-server DEVOPS_CLI_MCP_TOKEN`

### Requirement: The push makes the token once
When the keyring and the live Secret hold no value, the push SHALL generate the value of `DEVOPS_CLI_MCP_TOKEN` with `token_urlsafe(32)`, which is longer than the 32 characters that the server requires. The two client keys SHALL be adopted from the Secret `devops/mcp-server`, and SHALL NOT be generated. A change of the value SHALL restart `deployment/mcp-server`.

#### Scenario: A push with an empty keyring
- **WHEN** the keyring holds no `mcp_token` and `devops k8s push-secrets --stack devops` runs
- **THEN** the keyring stores one new value, and the three keys hold that value

### Requirement: The server pod reads the token from its Secret
Deployment `mcp-server` SHALL set the variable `DEVOPS_CLI_MCP_TOKEN` with a `secretKeyRef` to the key `DEVOPS_CLI_MCP_TOKEN` of Secret `mcp-server`. A `secretKeyRef` of a manifest under `k8s/` to a Secret of the table SHALL name a key of that row.

#### Scenario: A test reads the manifest
- **WHEN** a test reads Deployment `mcp-server`
- **THEN** its container env holds the variable with that `secretKeyRef`

### Requirement: The README lists the rows
The secret table of `k8s/README.md` SHALL list the three keys.

#### Scenario: A test reads the README
- **WHEN** a test reads the secret table of `k8s/README.md`
- **THEN** the table holds one row for each key of the secret table
