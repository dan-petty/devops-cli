# Proposal

## Why

Issue #3122: In the devcontainer environment, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is set to `"1"`. Anthropic's Claude Code uses this variable to disable nonessential network traffic, including remote web sessions and update checks. This setting prevents remote sessions and other remote connectivity in the devcontainer environment.

## What Changes

- Remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` from `containerEnv` in `.devcontainer/devcontainer.json`.
- Remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` from `containerEnv` in `.devcontainer/image/devcontainer.json`.
- Remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` from `containerEnv` in `src/devops_cli/templates/devcontainer.json.j2`.
- Update the telemetry opt-out examples in `SECURITY.md` to omit this variable.
- Update `tests/core/test_third_party_telemetry.py` to assert that `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is not set in devcontainer configurations or the template.
- The change sets `skip_specs: true` in `.openspec.yaml`. It alters no behavior a consumer observes: no `devops` command, option, message, manifest or service changes.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Devcontainer configuration: `.devcontainer/devcontainer.json`, `.devcontainer/image/devcontainer.json`, and `src/devops_cli/templates/devcontainer.json.j2`.
- Documentation: `SECURITY.md`.
- Tests: `tests/core/test_third_party_telemetry.py`.

## Feasibility

- Upstream Claude Code documentation specifies that `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` disables non-essential traffic such as telemetry, automatic update checks, and remote terminal connections.
- Command output: `uv run devops ci fail-to-pass --base origin/main` confirms that 3 tests in `tests/core/test_third_party_telemetry.py` fail on the base tree where the variable is set and pass when it is removed.
- Fast checks and static analysis pass cleanly via `uv run devops ci devcontainer`, `uv run devops ci lint`, and `uv run devops ci typecheck`.

## Existing Tool Considered

Dev Containers configuration specification (<https://containers.dev/implementors/json_reference/>) provides `containerEnv` for container-level environment variables. No custom code or wrapper is required. The change removes the variable from existing JSON configurations and templates. It builds nothing and deletes no internal code.
