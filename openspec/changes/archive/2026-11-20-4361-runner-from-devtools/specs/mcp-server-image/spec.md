## MODIFIED Requirements

### Requirement: Runtime user and directories
The `mcp-server` target SHALL run as user `1000:1000` and SHALL keep the data directory under `HOME`.

#### Scenario: Runtime user is non-root
- **WHEN** the smoke test runs `docker run --rm --entrypoint id "$IMAGE" -u`
- **THEN** the command prints `1000`

## REMOVED Requirements

### Requirement: MCP server image target
**Reason**: The MCP server image no longer builds on the `runner` stage. It builds on the layers of the Service image, on `python:3.14-slim-trixie` (#4361).
**Migration**: The requirement "The MCP server image builds on the Service image layers" holds the rule.

### Requirement: Pinned cluster tools
**Reason**: kubectl and helm come from the devtools image, which the `Dockerfile` pins by digest. `tools.lock` and `devops install-tools` no longer install them in the image (#4361).
**Migration**: The requirement "The MCP server image copies its cluster tools from the devtools image" holds the rule.

## ADDED Requirements

### Requirement: The MCP server image builds on the Service image layers
The `Dockerfile` SHALL add an `mcp-server` target that builds on `mcp-server-deps`, which builds on `service-deps` and so on `python:3.14-slim-trixie`, as the Service image does. It SHALL NOT build on the `runner` stage, and it SHALL hold no uv and no dev dependency.

#### Scenario: The target holds no build tool
- **WHEN** a person builds `--target mcp-server` and runs `docker run --rm --entrypoint sh <image> -c 'command -v uv'`
- **THEN** the build exits 0 and the command exits non-zero

### Requirement: The MCP server image copies its cluster tools from the devtools image
The `mcp-server` target SHALL copy `kubectl` and `helm` from the devtools image that the `Dockerfile` pins by digest, and SHALL hold gh, git and OpenSpec as the Service image does. The `Dockerfile` SHALL name no version of these tools.

#### Scenario: The cluster tools run
- **WHEN** the smoke test of the MCP Server Image job runs `docker run --rm --entrypoint kubectl "$IMAGE" version --client` and `docker run --rm --entrypoint helm "$IMAGE" version`
- **THEN** each command exits 0 and prints the version of the devtools image
