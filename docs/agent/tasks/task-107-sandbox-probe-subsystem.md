# Task 107: Protocol-Agnostic Endpoint Readiness & Health Probing Subsystem

**Issue**: [#107](https://github.com/dan-petty/devops-cli/issues/107)
**PR**: [#163](https://github.com/dan-petty/devops-cli/pull/163)
**Status**: Done
**Milestone**: `v0.2.17`
**Priority**: `priority/p0-critical`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Implement a protocol-agnostic probing engine evaluating application health, reachability, and readiness across multiple network protocols before initiating integration workflows, test runs, or fuzz testing against sandboxed workloads.

### Key Architectural Capabilities
1. **Multi-Protocol Probing Matrix (`devops sandbox probe`)**:
   - **TCP Socket Reachability**: Non-blocking TCP connection verification asserting port listener readiness with microsecond timing.
   - **HTTP/REST Health Probes**: Structured requests (`/healthz`, `/health`, `/ready`, `/live`, custom paths) asserting HTTP status codes, latency SLAs, and regex response matching.
   - **OpenAPI Schema Discovery & Validation**: Automatic discovery and parsing of `/openapi.json` executing safe schema-validated GET probes.
   - **gRPC Health Probes**: Health check execution via standard `grpc.health.v1.Health/Check` and reflection fallback without requiring pre-compiled `.proto` stubs.
2. **Pydantic v2 Models**:
   - Strongly typed `ProbeProtocol` (`tcp`, `http`, `openapi`, `grpc`), `ProbeStatus` (`pass`, `fail`, `timeout`, `skipped`), `EndpointProbeResult`, and `SandboxProbeReport`.
3. **Rich Visual Reporting & Automation**:
   - High-density Rich terminal tables with colored status badges, probe latencies, and executive summary panels.
   - Machine-readable `--json` export for pipeline consumption.
4. **Architectural Invariants**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ (< 6 indentation levels).
   - Fast-fail timeouts and bounded string truncations on errors ($\le 256$ chars).

---

## 2. Planned Changes

1. **Core Domain Submodule (`src/devops_cli/sandbox/`)**:
   - `models.py`: Add `ProbeProtocol`, `ProbeStatus`, `EndpointProbeResult`, and `SandboxProbeReport`.
   - `probe.py`: Implement protocol probing engine (`probe_tcp_reachability`, `probe_http_endpoint`, `probe_openapi_schema`, `probe_grpc_health`, `run_sandbox_probes`).
   - `engine.py`: Integrate probe runner with `WorkloadSandboxEngine.probe()`.
2. **CLI Commands (`src/devops_cli/commands/sandbox.py`)**:
   - Implement `devops sandbox probe [identifier]` with options `--protocol`, `--path`, `--timeout`, `--expected-status`, `--regex`, `--json`, and `--dry-run`.
3. **Language Localization (`src/devops_cli/lang/en/`)**:
   - `help.py`: Add help docstrings for `sandbox.probe` and options.
   - `messages.py`: Add user messages and status strings.
4. **Submodule Tests (`tests/test_sandbox_probe.py`)**:
   - Comprehensive unit and integration test suite with mock sockets, HTTP servers, OpenAPI schemas, and gRPC endpoints.
   - Assert $\ge 90\%$ test coverage and invariant gates.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#107) and set label to `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-107-sandbox-probe-subsystem.md`.
- [x] Create dedicated topic branch `feat/107-sandbox-probe-subsystem`.
- [x] Author unit tests in `tests/test_sandbox_probe.py`.
- [x] Implement probe models in `src/devops_cli/sandbox/models.py`.
- [x] Implement probing engine in `src/devops_cli/sandbox/probe.py`.
- [x] Implement CLI command in `src/devops_cli/commands/sandbox.py`.
- [x] Update language help and message strings in `src/devops_cli/lang/en/`.
- [x] Run test suite and full CI quality gate (`devops ci`).
- [x] Synchronize documentation (`devops docs generate --sync-readme`).
- [x] Author Pull Request targeting `release/v0.2.17` and verify CI checks pass.
