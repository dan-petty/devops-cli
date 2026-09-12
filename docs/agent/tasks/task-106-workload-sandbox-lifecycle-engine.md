# Task 106: Long-Running Workload Sandbox Lifecycle Engine

**Issue**: [#106](https://github.com/dan-petty/devops-cli/issues/106)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.16`
**Priority**: `priority/p0-critical`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Implement a foundational execution tier orchestrating isolated, long-running rootless Docker containers and ephemeral namespaces (`sandbox-<app>-<timestamp>`) for deploying, inspecting, and interacting with active builds and ephemeral services in total isolation.

### Key Architectural Capabilities
1. **Lifecycle Management (`devops sandbox deploy|status|stop|exec`)**:
   - `deploy`: Launch long-running containerized workload instances with detached daemon lifecycle.
   - `status`: Inspect running or terminated sandbox instances, uptime, port bindings, and resource usage.
   - `stop`: Gracefully terminate and clean up containers with guaranteed zero zombie processes.
   - `exec`: Run commands interactively or non-interactively inside active sandboxes.
2. **Dynamic Host Port Allocation (`10000-60000`)**:
   - Automated non-conflicting port allocation with socket binding check to ensure zero host port collision.
3. **Strict Resource & Security Containment**:
   - cgroup v2 resource limits: `pids_limit=256`, `cpu_limit`, `memory_limit`.
   - Hardened isolation: `read_only=True` root filesystems, `/tmp` tmpfs mounts, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`.
   - Host path containment: Strictly forbid mounting root paths (`/`, `/etc`), home directory, `.git`, `.ssh`, `.kube`, `.aws`, or Docker sockets.
4. **Persistent State Management**:
   - Managed state file under `.data/sandbox/instances.json` tracking instance ID, container ID, image, ports, status, and creation timestamps.
5. **FastMCP Integration**:
   - FastMCP tools (`sandbox_deploy`, `sandbox_status`, `sandbox_stop`, `sandbox_exec`) and system resource `resource://sandbox/status`.

---

## 2. Planned Changes

1. **Core Domain Submodule (`src/devops_cli/sandbox/`)**:
   - `models.py`: Typed Pydantic models for sandbox instance metadata, configs, state enums, port bindings, and exec results.
   - `ports.py`: Port allocator searching dynamic range (10000-60000) with socket collision detection.
   - `registry.py`: Persistent instance registry managing `.data/sandbox/instances.json` with thread/process-safe file locking.
   - `engine.py`: `WorkloadSandboxEngine` managing Docker container creation, daemon detachment, execution, and teardown.
2. **CLI Commands (`src/devops_cli/commands/sandbox.py`)**:
   - Implement `devops sandbox deploy`, `devops sandbox status`, `devops sandbox stop`, `devops sandbox exec`.
   - Register `sandbox` command group in `src/devops_cli/main.py`.
3. **FastMCP Tools (`src/devops_cli/ai/mcp/`)**:
   - Expose lazy MCP tools for sandbox lifecycle management.
4. **Submodule Tests (`tests/test_sandbox_lifecycle.py`)**:
   - Comprehensive unit tests verifying port allocation, container creation, execution, error boundaries, state persistence, and CLI commands with mock isolation.
   - Assert $\ge 90\%$ test coverage and architectural invariants (complexity $\le 10$, nesting depth $\le 5$).

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#106) and set label to `status/in-progress`.
- [x] Create dedicated topic branch `feat/workload-sandbox-lifecycle-engine`.
- [x] Author task tracking file `docs/agent/tasks/task-106-workload-sandbox-lifecycle-engine.md`.
- [x] Author implementation plan `implementation_plan.md` and present to user for approval.
- [x] Author unit tests in `tests/test_sandbox_lifecycle.py`.
- [x] Implement `sandbox` models, port allocator, registry, and engine.
- [x] Implement Typer CLI command group `devops sandbox`.
- [x] Implement FastMCP sandbox tools and dynamic resource.
- [x] Validate quality gates (29 tests passing, 97.35% coverage, lint, format, typecheck, docs, complexity <= 10).
- [ ] Open Pull Request targeting `release/v0.2.16`.
