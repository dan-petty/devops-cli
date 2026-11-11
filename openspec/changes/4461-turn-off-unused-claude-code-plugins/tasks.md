# Tasks

## 1. Turn off the unused plugins

Kind: data. Changes: `.claude/settings.json`, `src/devops_cli/templates/claude_settings.json.j2`.

- [x] 1.1 Set `cloudflare@claude-plugins-official`, `mcp-server-dev@claude-plugins-official` and `playwright@claude-plugins-official` to `false` in `enabledPlugins` of `.claude/settings.json` and of `src/devops_cli/templates/claude_settings.json.j2`. Keep the other three plugins, the environment and the permissions unchanged
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py` passes

## Criteria

- Pending a person: start a new Claude Code session in the repository and make sure that `/plugin` shows `cloudflare`, `mcp-server-dev` and `playwright` as off and the skill list has no `cloudflare:` or `mcp-server-dev:` skill.
- Pending a person: turn off the claude.ai Docs connector in the claude.ai settings. The connector is not a file of the repository.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
