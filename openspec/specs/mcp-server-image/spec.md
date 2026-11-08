# mcp-server-image Specification

## Purpose
The container image target for the MCP server that serves role-scoped tool sets to cluster jobs.

## Requirements

### Requirement: MCP server image target
The `Dockerfile` SHALL add an `mcp-server` target that inherits the `runner` stage.

#### Scenario: Target inherits runner
- **WHEN** A test parses the stages of the `Dockerfile`.
- **THEN** The stage `mcp-server` exists and its `FROM` line names `runner`.

### Requirement: Pinned cluster tools
The `mcp-server` target SHALL install `kubectl` and `helm` at the versions that `tools.lock` pins.

#### Scenario: Tool pins match
- **WHEN** The image build runs the tool version check.
- **THEN** Each installed version equals its pin, and a mismatch fails the build and names the tool.

### Requirement: Runtime user and directories
The `mcp-server` target SHALL run as user `1000:1000` and SHALL keep the data and uv cache directories under `HOME`.

#### Scenario: Runtime user is non-root
- **WHEN** A test reads the `USER` and `ENV` lines of the `mcp-server` stage.
- **THEN** `USER` is `1000:1000` and `DEVOPS_CLI_DATA_DIR` and `UV_CACHE_DIR` start with `HOME`.

### Requirement: MCP server image gate
The `mcp-server` image SHALL pass the HIGH and CRITICAL vulnerability scan and SHALL stay at or below 3,000,000,000 bytes.

#### Scenario: Image gate passes
- **WHEN** CI builds the `mcp-server` image.
- **THEN** `trivy image` exits 0 and `docker image inspect` reports at most 3,000,000,000 bytes.

### Requirement: Default Docker build stays on service
The `service` stage SHALL stay the last stage of the `Dockerfile`.

#### Scenario: Service stage is last
- **WHEN** A test lists the stages of the `Dockerfile`.
- **THEN** The last stage is `service` and `mcp-server` comes before it.
