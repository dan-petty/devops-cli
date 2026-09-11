# Task 144: Align Dev Container Usage Guide with Modern Best Practices

**Issue**: [#144](https://github.com/dan-petty/devops-cli/issues/144)
**PR**: [#145](https://github.com/dan-petty/devops-cli/pull/145)
**Status**: Done
**Milestone**: `v0.2.16`
**Priority**: `priority/p2-medium`
**Scope**: `scope/infra`

---

## 1. Description & Architectural Objectives

Audit and modernize `docs/DEVCONTAINER_USAGE.md` to ensure all instructions, recommendations, configuration examples, and command references strictly adhere to modern engineering best practices:

1. **Tag Pinning & Release Governance**:
   - Update all tag and CLI reference examples from outdated versions (`v0.2.13`, `v0.2.9`) to the active stable release (`v0.2.16`).
   - Explicitly document architecture support (`linux/amd64`, `linux/arm64`) and digest pinning for high-security environments.

2. **Cross-Platform Host Integration**:
   - Fix SSH mount path syntax to support Windows, macOS, and Linux seamlessly: `"source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"`.
   - Recommend named Docker volumes for high-churn directories (`/tmp`, `.venv`, `.data`, `.uv`, `.ruff_cache`, `/home/vscode`) to decouple heavy I/O from host bind mounts (avoiding WSL2 and macOS VirtioFS filesystem latency).

3. **Virtual Environment & Tooling Alignment**:
   - Correct the VS Code and Antigravity Python interpreter setting from system Python (`/usr/local/bin/python`) to the project `.venv` path (`${containerWorkspaceFolder}/.venv/bin/python`).
   - Configure mandatory environment variables (`DEVOPS_CLI_CONFIG`, `UV_MALWARE_CHECK`, `UV_CACHE_DIR`).
   - Provide complete, modern customization blocks for both VS Code and Antigravity IDE (including Ruff formatting on save, Pylance, EOL, rulers, and tab settings).

4. **Port Forwarding & Microservices**:
   - Document standard port forwarding definitions and labels for the complete DevOps & AI local stack: ArgoCD (`8080`), Grafana (`8030`), Prometheus (`8090`), Jaeger Query UI (`16686`), Qdrant Vector DB (`6333`), Valkey (`6379`), and Ollama (`11434`).

5. **AI Review & FastMCP Configuration**:
   - Update FastMCP server integration snippet to include `--with fastmcp`, `--transport stdio`, and workspace PATH resolution matching `src/devops_cli/templates/mcp.json.j2`.
   - Update CLI examples for configuring AI providers (`devops ai config`) and running branch reviews (`devops review branch`).
