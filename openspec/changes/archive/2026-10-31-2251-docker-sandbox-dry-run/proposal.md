# Proposal

## Why
#2251 addresses the owner's dry-run rule (#412) for docker and sandbox commands. The dry-run rule states that a dry run makes no external requests and returns the planned requests that the real execution would perform. Today, 18 docker and sandbox commands either execute external requests (via Docker engine socket, HTTP transport, DNS resolution, or subprocesses) or print an echo-only parameter preview under dry run.

## What Changes
- Classify all 18 docker and sandbox commands with `@dry_run_class("request-plan")`:
  - 9 docker commands: `docker build`, `docker cache`, `docker images`, `docker prune`, `docker push`, `docker sandbox`, `docker sign`, `docker stats`, and `docker verify`.
  - 9 sandbox commands: `sandbox deploy`, `sandbox exec`, `sandbox logs`, `sandbox metrics`, `sandbox network-policy`, `sandbox probe`, `sandbox status`, `sandbox stop`, and `sandbox traces`.
- Provide request plan generators using `PlannedRequest` for each command in `devops_cli.docker.docker_plans` and `devops_cli.sandbox.sandbox_plans`.
- Under dry run (`--dry-run` or global `devops --dry-run`), each command performs zero external socket, daemon, HTTP, subprocess, or DNS requests, and renders its ordered request plan via `render_request_plan` (or structured serialization for `--format json`/`--format yaml`).
- Remove legacy echo-only previews (`render_dry_run_result`) and obsolete simulated outputs with no backward-compatibility shim.
- Remove all 18 docker and sandbox command entries from `tests/fixtures/dry_run_gaps.json`.
- Add test suites verifying dry-run classifications, request plans, and zero-external-reach guarantees across all 18 commands.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior and zero external requests for the 18 docker and sandbox commands.

## Impact
- Command interfaces: `docker` and `sandbox` CLI commands gain standardized dry-run request planning; echo-only previews are eliminated.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 18; new tests verify dry-run plans without network or process execution.
- Documentation: Command documentation reflects request planning under dry run.

## Feasibility
Confirmed against repository code and library sources:
- Docker commands communicate with the Docker daemon API via `DockerEngineService` (`docker.DockerClient` / unix socket) and cosign binaries.
- Sandbox commands communicate with Docker engine, HTTP endpoints via `httpx2`, local socket/DNS, and subprocesses.
- `PlannedRequest` and `render_request_plan` in `devops_cli.dry_run.requests` provide standard request planning used by other subsystems (`ai`, `argo`, `k8s`, `review`, `scan`, `tf`).
- `docker analyze-layers` was previously retired in #2712, leaving exactly 18 active commands across `docker` and `sandbox` matching `dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It deletes legacy echo-only previews using `render_dry_run_result`.
