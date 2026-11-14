# Proposal

## Why

The requirement "The devcontainer scaffold writes Claude Code settings and Antigravity customizations" in `openspec/specs/devcontainer-agent-config/spec.md` names secret-file read/edit denies and the variable `PYDANTIC_AI_NO_BANNER`. The template `src/devops_cli/templates/claude_settings.json.j2` holds neither, and it sets `UV_MALWARE_CHECK`, which the requirement does not name. Owner direction keeps agent permissions permissive and adds no deny list, so the requirement is wrong (#4478).

## What Changes

- A MODIFIED delta states the command allowlist, the deny rules for `--no-verify` and bare `gh`, and the variables of the template.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-agent-config`: The scaffold requirement states what the template writes.

## Impact

- Spec: `openspec/specs/devcontainer-agent-config/spec.md`
- No code or test changes the template.

## Feasibility

- The template holds the values.
- `uv run devops openspec check` validates the delta.
- Verification command: `uv run devops openspec check`.

## Existing Tool Considered

OpenSpec is the tool for the change, and the spec is the only file.
