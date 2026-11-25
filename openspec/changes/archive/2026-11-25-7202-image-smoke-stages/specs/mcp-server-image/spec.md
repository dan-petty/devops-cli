## MODIFIED Requirements

### Requirement: Runtime user and directories
The `mcp-server` target SHALL run as user `1000:1000` and SHALL keep the data directory under `HOME`.

#### Scenario: Runtime user is non-root
- **WHEN** the stage `mcp-server-smoke` of `smoke.Dockerfile` runs `id -u` on the image
- **THEN** the command prints `1000`, and the build of the stage fails when it prints another value

### Requirement: The MCP server image copies its cluster tools from the devtools image
The `mcp-server` target SHALL copy `kubectl` and `helm` from the devtools image that the `Dockerfile` pins by digest, and SHALL hold gh, git and OpenSpec as the Service image does. The `Dockerfile` SHALL name no version of these tools.

#### Scenario: The cluster tools run
- **WHEN** the stage `mcp-server-smoke` of `smoke.Dockerfile` runs `kubectl version --client` and `helm version` on the image
- **THEN** each command exits 0 and prints the version of the devtools image
