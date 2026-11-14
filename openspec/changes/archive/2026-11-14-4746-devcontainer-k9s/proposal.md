# Proposal

## Why

`docs/DEVCONTAINER_USAGE.md` says that post-create installs `k9s`, `gh-dash` and `tuicr`. Since #4366 the image build installs every tool of `tools.lock` in `/usr/local/bin`, and post-create installs no locked tool (#4746).

## What Changes

- The terminal-tools bullet says that the image installs the three tools in `/usr/local/bin` and that post-create installs no locked tool.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Document: `docs/DEVCONTAINER_USAGE.md`

## Feasibility

- `.devcontainer/Dockerfile` installs the three tools in `/usr/local/bin`.
- `_run_post_create_lifecycle` installs no tool of `tools.lock`.
- Verification command: `uv run devops ci docs`.

## Existing Tool Considered

No tool covers a wrong sentence. The change edits one bullet.
