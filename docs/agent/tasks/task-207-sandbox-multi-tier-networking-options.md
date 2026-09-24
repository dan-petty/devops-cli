# Task 207: Sandbox Multi-Tier Networking Configuration Options

**Issue**: [#207](https://github.com/dan-petty/devops-cli/issues/207)
**Status**: Done
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/security`, `scope/cli`

---

## 1. Description & Architectural Objectives

Implement multi-tier networking configuration options for workload sandboxes across Docker and Kubernetes execution environments:
1. **Isolated pod / container with no network access** (`isolated` / `none`):
   - Zero external and zero local network access (loopback only).
   - In Docker: maps to `--network=none`.
   - In Kubernetes: generates zero-ingress, zero-egress `NetworkPolicy`.
2. **Sandbox namespace access** (`sandbox_namespace`):
   - Restricted strictly to intra-sandbox communication within a dedicated internal network or Kubernetes sandbox namespace (`devops-sandbox-net` / `sandbox`), without public internet gateway or host network access.
   - In Docker: attaches to internal Docker network created with `--internal`.
   - In Kubernetes: generates intra-namespace `NetworkPolicy` + CoreDNS resolution.
3. **Public internet access by explicit whitelist** (`public_whitelist`):
   - Outbound access permitted strictly to explicitly whitelisted public domains and public IPs/CIDRs.
   - Private RFC 1918 IPs, link-local, and cloud metadata (`169.254.169.254`) are strictly blocked.
   - Generates egress `NetworkPolicy` ipBlocks and validates domain destinations.
4. **Access to explicitly whitelisted local URL/IP** (`local_whitelist`):
   - Access permitted strictly to explicitly whitelisted local/private endpoints (e.g. `http://localhost:11434`, `http://192.0.2.50:8000`, `host.docker.internal`).
   - Arbitrary local port scanning or unlisted internal hosts are blocked.
   - In Docker: maps to `--add-host` host-gateway mappings for authorized endpoints.

---

## 2. Planned Changes

1. **`src/devops_cli/config/constants.py` & `defaults.py`**:
   - Declare network mode constants and frozen set `CONST_SANDBOX_NETWORK_MODES`.
   - Declare default network mode and namespace.
2. **`src/devops_cli/sandbox/models.py`**:
   - Implement `SandboxNetworkMode` StrEnum and `SandboxNetworkConfig` Pydantic model with validation and `to_k8s_network_policy()` / `to_docker_args()`.
   - Update `SandboxDeployConfig` with `network_config`.
3. **`src/devops_cli/docker/sandbox.py`**:
   - Update `WorkloadSandboxConfig` with `network_config` and `WorkloadSandboxRunner` execution logic for all 4 modes.
4. **`src/devops_cli/sandbox/engine.py`**:
   - Wire `network_config` into `WorkloadSandboxEngine` create kwargs, subprocess execution, and lazy internal network creation.
5. **`src/devops_cli/commands/sandbox.py`, `commands/docker.py`, `commands/test_cmd.py`**:
   - Expose `--network-mode`, `--public-whitelist`, `--local-whitelist` CLI flags.
   - Add `devops sandbox network-policy` export command.
6. **`src/devops_cli/ai/mcp/server.py`**:
   - Expose networking options on `sandbox_deploy` and `docker_sandbox` FastMCP tools.
7. **`tests/test_sandbox_networking.py`**:
   - Author comprehensive unit tests covering all 4 modes, whitelist validations, NetworkPolicy YAML generation, and CLI commands.

---

## 3. Verification & Acceptance Criteria

- [ ] All 4 networking modes fully supported across `SandboxDeployConfig` and `WorkloadSandboxConfig`.
- [ ] NetworkPolicy generator creates valid, standard Kubernetes `networking.k8s.io/v1` specifications for all modes.
- [ ] Whitelist validation strictly prevents SSRF / cloud metadata leakage.
- [ ] CLI flags exposed on `devops sandbox deploy`, `devops docker sandbox`, and `devops test sandbox`.
- [ ] 100% test pass on `tests/test_sandbox_networking.py` and zero regressions in `devops ci`.
