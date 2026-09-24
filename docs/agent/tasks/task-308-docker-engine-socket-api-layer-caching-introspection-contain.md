# Task 308: Docker Engine Socket API, Layer Caching Introspection & Container Sandbox Optimization Research

**Issue**: [#308](https://github.com/dan-petty/devops-cli/issues/308)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Workstation container management and dynamic sandbox execution executed shallow `docker` CLI subprocesses (`docker run`, `docker inspect`, `docker stats`, `docker logs`, `docker network create`) behind every Docker SDK call as a fallback shim, causing process churn and fragile human-readable string scraping. This deliverable establishes a single `DockerEngineService` speaking the Engine API directly over the daemon Unix domain socket, projects every response into typed Pydantic models, introspects BuildKit multi-stage layer caching, and ruthlessly eliminates every CLI fallback path.

### Key Deliverables Completed:
- [x] **DockerEngineService Singleton Architecture (`src/devops_cli/docker/engine.py`)**:
  - Direct Engine API communication over the daemon Unix domain socket (`/var/run/docker.sock`), with `DOCKER_HOST` TCP endpoints routed through SSRF egress validation (`validate_service_url`) before the client is negotiated.
  - Cached, process-wide client connection so repeated container, image, network, and build-cache operations reuse one negotiated socket instead of re-handshaking per command.
  - Zero-overhead daemon liveness probing via Engine API socket ping (`ping`) with bounded TTL response caching (`DEFAULT_DOCKER_CACHE_TTL_SECONDS`).
  - Typed container introspection (`list_containers`, `inspect_container`) and lifecycle control (`create_container`, `stop_container`, `remove_container`, `exec_in_container`, `wait_container`, `container_logs`, `container_log_stream`) issuing direct Engine API calls without redundant inspect round-trips.
  - Real-time cgroup telemetry streaming (`container_stats`, `stream_container_stats`) yielding typed samples straight off the Engine API stats socket.
  - Internal (egress-denied) bridge network provisioning (`ensure_internal_network`) that detects and recreates drifted networks.
- [x] **BuildKit Multi-Stage Layer Cache Introspection**:
  - `GET /system/df` disk-usage projection into typed `BuildCacheRecord` / `BuildCacheReport` models reporting cache occupancy, reclaimable bytes, in-use and shared record counts, and a computed reuse ratio.
  - New `devops docker cache` subcommand with table, `--json`, `--prune`, and `--dry-run` output modes.
- [x] **Typed Pydantic Container State Models (`src/devops_cli/models/docker.py`)**:
  - `ContainerState` replaces unstructured `docker inspect` stdout scraping with a strongly typed projection of the Engine API inspect payload (status, health, exit code, network mode, labels, port bindings).
  - `BuildCacheRecord` and `BuildCacheReport` for BuildKit solver cache introspection.
- [x] **Legacy Fallback Shim Elimination (Zero Zombie Code)**:
  - Removed `WorkloadSandboxRunner._run_via_subprocess` and the duplicated `docker run` argument assembly in `src/devops_cli/docker/sandbox.py`.
  - Removed `_spawn_via_subprocess`, `_exec_via_subprocess`, `_fetch_logs_via_subprocess`, and the `docker stop` / `docker rm` subprocess termination fallback in `src/devops_cli/sandbox/engine.py`.
  - Removed the `docker stats --format '{{json .}}'` subprocess scraper in `src/devops_cli/sandbox/metrics.py`, along with the `_parse_size_bytes`, `_parse_docker_net_io`, and `_build_metrics_from_docker_dict` human-readable string parsers it required.
  - Consolidated four duplicated `_get_docker_client` / `_is_internal_network_sdk` / `_create_internal_network_sdk` helper copies into the single shared engine client.
- [x] **Centralized Constants & Defaults**:
  - Engine socket endpoints, `DOCKER_HOST` network schemes, `GET /system/df` object keys, BuildKit cache record types, and CPU severity thresholds centralized in `src/devops_cli/config/constants.py`.
  - Ping, cache TTL, stop timeout, stats sample, and sandbox PID limit defaults centralized in `src/devops_cli/config/defaults.py`.
- [x] **Typed Exception Hierarchy**:
  - `DockerEngineError` and `DockerDaemonUnavailableError` with dedicated error codes, replacing bare `Exception` propagation from the Docker SDK.
- [x] **Automated Tests & Quality Gates**:
  - 40 unit tests in `tests/test_docker_engine.py` using structural tuple equality assertions, plus a shared `docker_engine` fixture in `tests/conftest.py` that binds mock Engine API clients to an isolated service singleton and guarantees no socket leaks between tests.
  - Existing Docker, workload sandbox, sandbox lifecycle, sandbox logs, and sandbox metrics suites migrated from CLI-fallback assertions to Engine API behaviour.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ enforced project-wide.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
