# Design

## Decisions

- **Set the three plugins to `false`, not remove their keys.**: A `false` value records the decision in the file, and it turns the plugin off also when a user scope turns it on.
- **Change the scaffold template with the committed file.**: `devops devcontainer init` writes the template, and an existing test holds the template equal to `.claude/settings.json`.
- **Keep `grafana-mcp`, `mattpocock-skills` and `pydantic-ai` on.**: `grafana-mcp` had 1,165 tool calls in the measured week, and the project skills of `mattpocock-skills` and `pydantic-ai` are in use.
- **Add no test.**: The change edits data. `docs/TESTING.md` gives data no test, and the existing equality test already fails when the two files differ.

## Rejected alternatives

- **Turn off the plugins in `.claude/settings.local.json`.**: That file is gitignored and holds the settings of one person, so other sessions and new workspaces would still load the plugins.
- **Remove the plugins from the user settings.**: `/home/vscode/.claude/settings.json` turns on none of the three, so the project file is the only source.
- **Add a deny list for the plugin tools.**: The owner keeps agent permissions permissive, and a deny list still loads the skill listing.
