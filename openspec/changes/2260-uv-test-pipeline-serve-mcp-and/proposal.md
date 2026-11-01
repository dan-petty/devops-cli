# Proposal

## Why

Issue #2260 (part of #886) found 14 commands that do not obey the dry-run rule (#412). A dry run must make no external request and must return the requests the real run would make. These 14 commands either print a generic line, fail with No such option, or print an echo of arguments. None shows the requests.

## What Changes

- Add --dry-run with a PlannedRequest list to 12 request-plan commands (uv lock, uv python-install, uv run, uv sync, test load, test profile-memory, test run, test sandbox, mcp serve, serve, pipeline, ci fail-to-pass).
- Add --dry-run local preview to mcp export-schemas: print the change, write nothing.
- Give mcp tools the no-external-request class so devops --dry-run runs it normally.
- Remove echo-only previews (render_dry_run_result or @dry_run_command) from commands that gain a new dry run.
- Remove all 14 paths from tests/fixtures/dry_run_gaps.json.
- Write tests that verify no external request is made and the plan matches the real run's calls.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: request-plan-commands-list-planned-requests, local-preview-commands-print-change, mark-only-commands-run-normally, plan-built-from-same-builder, echo-only-previews-removed

## Impact

- Code: `src/devops_cli/commands/uv_cmd.py`, `src/devops_cli/commands/test_cmd.py`, `src/devops_cli/commands/mcp_cmd.py`, `src/devops_cli/commands/serve_cmd.py`, `src/devops_cli/commands/pipeline_cmd.py`, `src/devops_cli/commands/ci_cmd.py`
- Tests: `tests/test_dry_run_uv.py`, `tests/test_dry_run_test_cmd.py`, `tests/test_dry_run_mcp.py`, `tests/test_dry_run_serve.py`, `tests/test_dry_run_pipeline_ci.py`, `tests/fixtures/dry_run_gaps.json`

## Feasibility

- The issue cites devops_cli.dry_run.requests.PlannedRequest and render_request_plan (#741) as existing. The CHANGELOG shows 15+ prior deliveries of the same pattern (config, devcontainer, telemetry, vault, cloudflare, docker, scan, review, tf, argo, k8s, pr, gh, ai).
- tests/fixtures/dry_run_gaps.json (shown in context) lists all 14 command paths, confirming they are tracked.
- tests/conftest.py (shown in context) provides the network guard, process guard, and dry-run state reset that the new tests will use.
- The issue evidence names specific source locations: commands.test_cmd:run_test_cmd:162, http.broker:HttpClientBroker.arequest:141, docker.engine:DockerEngineService.client:416. The implementation must verify each row against the code before changing it.
- First checks the implementation runs: (1) uv run devops ci fail-to-pass --dry-run to confirm the current echo-only output; (2) uv run devops uv lock --dry-run to confirm the missing option; (3) uv run devops mcp tools --dry-run to confirm the generic line; (4) uv run pytest tests/test_roadmap_dry_runs.py to confirm the ratchet test currently passes with the 14 gaps present.

## Existing Tool Considered

The repository already provides devops_cli.dry_run.requests.PlannedRequest, render_request_plan, the dry-run class decorator, and the ratchet test (sub-issue 00). The test guards in tests/conftest.py and the plan-equality pattern in tests/test_roadmap_dry_runs.py cover the verification need. No new dependency is necessary.
