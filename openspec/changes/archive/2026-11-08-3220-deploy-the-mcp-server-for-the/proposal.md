# Change: Add MCP Server Image Target and Gate (#3220)

## Why
The repository has no image target for the MCP server. A deployment cannot run the pinned scanners, `kubectl`, or `helm` because the `service` image lacks these tools. The live deployment also waits for cluster manifests. This change adds the `mcp-server` image target to `Dockerfile` and adds its gate to CI. It defers the live manifest set until the related deployment configuration lands.

This change fits in one pull request.

## What Changes
- Adds stage `mcp-server` to `Dockerfile` inheriting stage `runner`.
- Installs `kubectl` and `helm` into `/opt/devops-tools/bin` at the pinned versions from `tools.lock`.
- Sets runtime user `1000:1000` and configures `DEVOPS_CLI_DATA_DIR` and `UV_CACHE_DIR` under `HOME`.
- Adds a tool version check in the image build that confirms installed versions match their pins and fails if any mismatch occurs.
- Adds `mcp-server-image` job to `.github/workflows/ci.yml` that builds the target, runs smoke tests, bounds image size to at most 3,000,000,000 bytes, and scans for HIGH and CRITICAL vulnerabilities with Trivy.
- Adds invariant unit tests in `tests/invariants/test_mcp_server_image.py`.

## Capabilities

### New Capabilities
- `mcp-server-image`: Container image target for the MCP server with pinned cluster tools and non-root execution.

## Feasibility
Confirmed against the repository and system:
- `Dockerfile` stage `runner` provides the base scanner and Python environment.
- `tools.lock` pins `kubectl` at version 1.37.1 and `helm` at version 4.3.0 with SHA-256 digests.
- `devops install-tools --tool <name> --target-dir <dir>` installs and links the pinned binaries.
- `devops install-tools --check --tool <name> --target-dir <dir>` confirms the pins match.

## Existing Tool Considered
ToolHive (`https://github.com/stacklok/toolhive`, Apache-2.0) was evaluated on 2026-11-05. It partly covers MCP deployments through custom resources and proxy pods. It does not provide project-specific image targets, tool pinning, or plain kustomize workflows. Cost to build: approximately 150k tokens and 8 hours. The project image target preserves consistent toolchains and offline testability.
