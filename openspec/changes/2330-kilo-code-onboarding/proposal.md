# Proposal

## Why

Issue #2330: the repository supports Claude Code, GitHub Copilot and Antigravity, but Kilo Code has only its devcontainer extension. Kilo Code reads `AGENTS.md` by itself, but it does not read `.mcp.json` or `.vscode/mcp.json`, so the `devops-cli` MCP server is not available to it.

## What Changes

- Add the template `kilo_mcp.json.j2`. It renders `kilo.jsonc` with a `local` server: the command is one array and the variables are under `environment`.
- `devops devcontainer init` writes `kilo.jsonc` at the repository root, and the `post-start` and `update` sync writes it when it is missing.
- Commit `kilo.jsonc` for this repository, and copy it into the mutation tree (`also_copy` in `pyproject.toml`).
- Add Kilo Code to `docs/DEVCONTAINER_USAGE.md`.
- No `KILO.md` stub is added: Kilo Code reads `AGENTS.md`.
- A command writes a new file, which a consumer observes, so the change carries a spec delta.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `devcontainer-agent-config`: the MCP configuration file that each supported coding agent reads in a scaffolded repository.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/templates/kilo_mcp.json.j2`, `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/config/constants.py`.
- `kilo.jsonc`, `pyproject.toml`, `docs/DEVCONTAINER_USAGE.md`, `tests/test_devcontainer.py`.

## Feasibility

- The Kilo Code documents (https://kilo.ai/docs) state that Kilo reads `AGENTS.md` from the project root, and that project MCP servers sit under the `mcp` key of `kilo.jsonc` at the root or of `.kilo/kilo.jsonc`. A `local` server has `command` as an array and `environment` as a map.
- `.gitignore` already excludes `.kilo/`, so the committed file is the root `kilo.jsonc`.
- The `.devcontainer/devcontainer.json` of this repository already installs the extension `kilocode.Kilo-Code`.

## Existing Tool Considered

The Kilo Code configuration format and the existing template renderer (`render_json_template`, which parses what it renders). No new code framework is built, and no internal code is deleted.
