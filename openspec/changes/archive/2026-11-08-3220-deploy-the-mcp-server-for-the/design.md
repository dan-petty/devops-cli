# Design: MCP Server Image Target and Gate

## Context
Issue #3220 requires a container image for the MCP server that includes cluster tools (`kubectl` and `helm`) and scanners while running as non-root.

## Goals
- Add the `mcp-server` target to `Dockerfile` inheriting `runner`.
- Install `kubectl` and `helm` at versions pinned in `tools.lock`.
- Keep runtime user as `1000:1000` with data and cache directories under `HOME`.
- Verify installed tool versions during the build and fail if a mismatch occurs.
- Keep `service` stage as the last stage in `Dockerfile`.
- Add an image gate in `.github/workflows/ci.yml` verifying the byte limit (3,000,000,000 bytes) and vulnerability scan.

## Architecture Decisions

### Inherit from runner stage
The `runner` stage contains pinned Python tools, git, and static analysis utilities. Inheriting from `runner` avoids repeating the tool build steps and ensures common layers are shared.

### Install pinned kubectl and helm
`tools.lock` defines the exact version and checksum for `kubectl` and `helm`. Installing them via `devops install-tools` places executable symlinks in `/opt/devops-tools/bin`, matching the existing layout.

### Non-root execution
The container runs under user `1000:1000`. The environment variables `HOME=/home/devops`, `DEVOPS_CLI_DATA_DIR=/home/devops/.data`, and `UV_CACHE_DIR=/home/devops/.cache/uv` ensure runtime state stays in the user directory.

### Tool check during build
`devops install-tools --check` validates that the installed binaries match `tools.lock`. Any version drift fails the build with the name of the mismatched tool.
