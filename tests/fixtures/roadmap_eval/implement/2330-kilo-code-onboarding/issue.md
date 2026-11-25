## Problem Description

The repository supports Claude Code, GitHub Copilot and Antigravity, but Kilo Code only has its extension in the devcontainer and a `.kilo/` entry in `.gitignore`.

Kilo Code reads `AGENTS.md` natively (https://kilo.ai/docs), so it needs no pointer stub. It does not read `.mcp.json` or `.vscode/mcp.json`. It reads project MCP servers from `kilo.jsonc` at the repository root (or `.kilo/kilo.jsonc`, which `.gitignore` excludes). So the `devops-cli` MCP server is not available to Kilo Code, and `devops devcontainer init` and `update` do not scaffold it.

## Expected vs Actual Behavior

Expected: a committed `kilo.jsonc` exposes the `devops-cli` MCP server (`type: local`, stdio) to Kilo Code. `devops devcontainer init` and `devops devcontainer update` scaffold it for managed repositories. The documents list Kilo Code as a supported agent.

Actual: Kilo Code has the rules of `AGENTS.md` but no MCP server.

## Environment Diagnostics

- Premise: Kilo Code docs for `AGENTS.md` and for the `mcp` key of `kilo.jsonc`.
- No `KILO.md` stub is added: Kilo reads `AGENTS.md`.
