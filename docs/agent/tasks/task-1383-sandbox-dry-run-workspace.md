# Task: Docker sandbox and test sandbox dry runs check the workspace as the real run does (#1383)

**Issue**: [#1383](https://github.com/dan-petty/devops-cli/issues/1383)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/bug, priority/p2-medium, scope/cli, scope/security

## Description

Issue #1115 made the sandbox workspace check request-free by reading the engine endpoint from `DOCKER_HOST` or the default unix socket without calling the egress lookup (`DockerEngineService.configured_host()`), and wired `devops sandbox deploy --dry-run` to run workspace validation. However, `devops docker sandbox --dry-run` and `devops test sandbox --dry-run` returned early via `sandbox_runner.build_dry_run_details()` before `sandbox_runner.run()` executed, skipping `_validate_workspace_dir()`. As a result, dry runs could report success for invalid workspaces that a real run refuses (such as forbidden root directories, user runtime directories, engine socket directories, or sensitive paths).

The fix updates `WorkloadSandboxRunner.build_dry_run_details()` in `src/devops_cli/docker/sandbox.py` to resolve and validate the workspace via `self._validate_workspace_dir()`, ensuring both `devops docker sandbox --dry-run` and `devops test sandbox --dry-run` validate the workspace and refuse invalid configurations with `DockerSandboxError`.

## Acceptance Criteria

- [x] `devops docker sandbox --dry-run` and `devops test sandbox --dry-run` run `validate_sandbox_workspace` and refuse every workspace the real run refuses, each with its own error type (`DockerSandboxError`).
- [x] The dry runs still make no request: a test with `DOCKER_HOST=tcp://example.com:2375` and private networks disallowed records no host lookup and no client call (`test_docker_and_test_sandbox_dry_runs_make_no_request` in `tests/test_sandbox_lifecycle.py`).
- [x] Tests reuse `_REFUSED_WORKSPACES` (`tests/test_sandbox_lifecycle.py`) for both dry runs; each call phase stays under 1 s and `uv run devops ci` passes.
- [x] `changelog.d/1383.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
