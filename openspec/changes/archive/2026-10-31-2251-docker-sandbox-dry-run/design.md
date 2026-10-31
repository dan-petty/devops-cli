# Design

## Context
See `proposal.md` for motivation.
Devops-cli enforces the owner's dry-run rule (#412) via `@dry_run_class`.
The `docker` and `sandbox` command groups interact with external resources:
- Docker daemon unix domain socket (`/var/run/docker.sock` or `DOCKER_HOST`) via `DockerEngineService`.
- Subprocesses such as `cosign` (`cosign sign`, `cosign verify`).
- HTTP endpoints via `httpx2.HTTPTransport` (metrics, traces, health probe endpoints).
- Local socket / DNS queries.

The 18 commands must not touch daemon sockets, network sockets, or launch subprocesses under dry run. Instead, they must generate an ordered list of `PlannedRequest` items and render them with `render_request_plan` or emit structured serialized output.

## Goals / Non-Goals

**Goals:**
- Implement plan generation functions in `devops_cli.docker.docker_plans` and `devops_cli.sandbox.sandbox_plans`.
- Decorate 9 docker and 9 sandbox commands with `@dry_run_class("request-plan")`.
- Ensure each command accepts `--dry-run` and respects global `devops --dry-run <cmd>`.
- In dry-run mode, make zero socket, HTTP, or subprocess calls.
- Format tabular request plans and structured outputs (JSON/YAML) consistently.
- Remove legacy `render_dry_run_result` calls and mock outputs with no shim.
- Remove all 18 commands from `tests/fixtures/dry_run_gaps.json`.

**Non-Goals:**
- Changing execution logic in non-dry-run mode.
- Adding backwards-compatibility shims for legacy echo-only `--dry-run` formats.

## Decisions

### 1. Dedicated plan modules (`docker_plans.py` and `sandbox_plans.py`)
- **Decision**: Keep plan builders in `src/devops_cli/docker/docker_plans.py` and `src/devops_cli/sandbox/sandbox_plans.py`.
- **Rationale**: Isolates request planning and argument generation, keeping command definitions lightweight and preventing cyclical imports. Follows patterns established in `src/devops_cli/ai/ai_plans.py`, `src/devops_cli/security/scan_plans.py`, and `src/devops_cli/tf/tf_plans.py`.
- **Alternatives considered**:
  - *Inline plan generation directly in CLI callback bodies*: Rejected because it increases command cyclomatic complexity beyond the project ceiling (10) and prevents unit testing plans in isolation.

### 2. Standardized engine and HTTP PlannedRequest representations
- **Decision**: Represent Docker Engine API calls with `method="DOCKER"` (e.g. `DOCKER GET /images/json`, `DOCKER POST /build`, `DOCKER POST /containers/{id}/stop`), cosign calls with `method="EXEC"` and `argv`, and HTTP endpoints with HTTP methods (`GET`, `POST`) and URL targets.
- **Rationale**: Accurately describes what would execute against the Docker daemon socket or network while adhering to `PlannedRequest(method=..., target=..., argv=...)`.
- **Alternatives considered**:
  - *Representing Docker calls as raw curl commands*: Rejected because Docker operations use the Python Docker SDK socket client, not curl CLI binaries.

## Risks / Trade-offs
- [Cyclomatic complexity in command functions] → Extract dry-run dispatch to concise helper functions (`_handle_docker_<cmd>_dry_run` and `_handle_sandbox_<cmd>_dry_run`) to strictly adhere to the complexity threshold (<=10).
- [Subprocess or socket leakage in tests] → Use session socket guards and monkeypatch runners to guarantee zero external calls are made during dry runs.
