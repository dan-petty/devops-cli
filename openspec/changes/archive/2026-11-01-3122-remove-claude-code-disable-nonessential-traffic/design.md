# Design

## Context

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` was previously added to `.devcontainer/devcontainer.json`, `.devcontainer/image/devcontainer.json`, and `src/devops_cli/templates/devcontainer.json.j2` under the assumption that it served only as a telemetry opt-out variable. However, in Claude Code, setting this variable to `1` disables all non-essential traffic, which includes remote web sessions and update checks. Rule 9 of `SECURITY.md` specifies that non-essential traffic and telemetry should be turned off only when the user loses no function.

## Decisions

### 1. Remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` from container environments

Remove the variable from `.devcontainer/devcontainer.json`, `.devcontainer/image/devcontainer.json`, and `src/devops_cli/templates/devcontainer.json.j2`. This restores remote session capabilities for Claude Code in the devcontainer while keeping other telemetry opt-out variables (`DO_NOT_TRACK`, `HF_HUB_DISABLE_TELEMETRY`, `DOTNET_CLI_TELEMETRY_OPTOUT`, `GOTELEMETRY`, `PIP_DISABLE_PIP_VERSION_CHECK`) intact.

### 2. Update telemetry tests to assert absence

Update `tests/core/test_third_party_telemetry.py` to:
- Remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` from the expected environment tuples.
- Explicitly assert `assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" not in env` across workspace, image, and template tests to prevent accidental reintroduction.

### 3. Update security policy documentation

Update `SECURITY.md` item 9 to remove `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` from the list of example telemetry opt-out variables.

## Risks / Trade-offs

- **Claude Code nonessential traffic**: Without this variable, Claude Code may check for updates and emit default analytics unless configured otherwise at the tool or user level. This is an accepted trade-off to allow remote sessions and interactive features to function.
