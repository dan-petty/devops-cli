# Proposal: #4461

## Why

The project file `.claude/settings.json` turns on six Claude Code plugins. Three of them, `cloudflare`, `mcp-server-dev` and `playwright`, are not used in this repository, but each Claude Code request loads their skill listing (about 1,520 tokens) and the MCP tool names of `playwright` (about 320 tokens). In the week to 2026-11-11 there were about 53,000 Claude Code requests, so these three plugins added about 150M tokens (about 96% cache reads), and that week had 0 calls to them. The owner approved to turn them off on 2026-11-11. Closes #4461.

## What Changes

- Set `cloudflare@claude-plugins-official`, `mcp-server-dev@claude-plugins-official` and `playwright@claude-plugins-official` to `false` in `enabledPlugins` of `.claude/settings.json`.
- Make the same change in `src/devops_cli/templates/claude_settings.json.j2`, the copy that `devops devcontainer init` writes. `test_init_scaffolds_claude_settings_matching_the_repository_settings` holds the two files equal.
- Keep `mattpocock-skills`, `pydantic-ai` and `grafana-mcp` on. The `grafana-mcp` tools had 1,165 calls in the same week.
- Do not change `.claude/settings.local.json`, the permissions or the hooks.
- No spec delta: the change edits data in two files. The `devcontainer-agent-config` spec names the permissions and the environment of the scaffolded file, not its plugin set, so no requirement changes. No command, option or message changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Claude Code sessions in this repository and in a repository that `devops devcontainer init` makes no longer load the skills and MCP tools of the three plugins.
- A person who needs one of the three plugins turns it on in `.claude/settings.local.json`, which has priority over the project file.
- The claude.ai Docs connector is a claude.ai account setting, not a file of the repository. A person turns it off in the claude.ai settings.

## Feasibility

- The Claude Code settings reference (https://code.claude.com/docs/en/settings-reference, read on 2026-11-11) gives `enabledPlugins` the scope "Any file" and the type "object mapping `plugin-name@marketplace-name` to a Boolean", with an example that sets one plugin to `false`. It also says: "To opt out of a project-enabled plugin on your machine, set it to `false` in `.claude/settings.local.json` instead."
- The settings page (https://code.claude.com/docs/en/settings) gives the order "managed settings, command line, project local, shared project, user". So a `false` in `.claude/settings.json` turns a plugin off unless a local file, the command line or a managed source turns it on.
- `python3 -c 'import json; print(json.load(open("/home/vscode/.claude/settings.json")).get("enabledPlugins"))'` printed `None`, and the same read of `.claude/settings.local.json` printed `None`. So only the project file turns on the three plugins.
- `git grep -n -E 'claude-plugins-official|enabledPlugins' origin/main` found only `.claude/settings.json` and `src/devops_cli/templates/claude_settings.json.j2`. No document, test or other generator lists the plugins.
- With the new `.claude/settings.json` and the old template, `test_init_scaffolds_claude_settings_matching_the_repository_settings` failed. So the template must change with the file.

## Existing Tool Considered

Claude Code `enabledPlugins` in the project settings file turns off a plugin. The change uses it and builds nothing. It deletes no internal code.
