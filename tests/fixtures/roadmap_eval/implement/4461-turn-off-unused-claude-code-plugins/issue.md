### Problem or Motivation

The project file `.claude/settings.json` turns on six Claude Code plugins in `enabledPlugins`. Three of them, `cloudflare`, `mcp-server-dev` and `playwright`, are not used in this repository. Each Claude Code request still loads their skill listing (about 1,520 tokens) and the deferred MCP tool names of `playwright` (about 320 tokens).

The context audit of 2026-11-11 measured about 53,000 Claude Code requests in one week. These three plugins added about 150M tokens in that week (about 96% of them cache reads). The same week had 0 calls to a skill or a tool of these three plugins. The owner approved to turn them off on 2026-11-11.

The scaffold template `src/devops_cli/templates/claude_settings.json.j2` holds a copy of the same file. `devops devcontainer init` writes it, and a test makes sure that the copy and the committed file are equal.

### Proposed Solution & Architectural Design

- In `.claude/settings.json`, set `cloudflare@claude-plugins-official`, `mcp-server-dev@claude-plugins-official` and `playwright@claude-plugins-official` to `false` in `enabledPlugins`.
- Make the same change in `src/devops_cli/templates/claude_settings.json.j2`, so that `devops devcontainer init` writes the same file.
- Keep `mattpocock-skills`, `pydantic-ai` and `grafana-mcp` on. The `grafana-mcp` tools had 1,165 calls in the same week.
- Do not change `.claude/settings.local.json`, the permissions or the hooks.

A person must turn off the claude.ai Docs connector in the claude.ai settings. That connector is not in the repository.

### Target Subsystem

Development environment: Claude Code project settings and the `devops devcontainer init` scaffold.

### Existing Tool Considered

Claude Code `enabledPlugins` in the project settings file. A value of `false` in the project scope turns off a plugin. No code is necessary.

### Standards Compliance

- [x] I confirm this proposal aligns with AGENTS.md engineering principles.
- [x] I am willing to submit a pull request implementing this feature with accompanying tests.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=c653bde8c7e6e014a17cb31e079c66f25fc365fb -->
## Proposed design

### Problem statement
`.claude/settings.json` turns on six Claude Code plugins. Three of them are unused in this repository. Each request still loads their skill listing and the deferred MCP tool names of `playwright`. A week of about 53,000 requests spent about 150M tokens on them, with no call to their skills or tools. The scaffold template holds a copy of the same file, and a test keeps the two equal.

### Acceptance criteria

### Requirement: Unused plugins are off in the project settings
`.claude/settings.json` SHALL set `cloudflare@claude-plugins-official`, `mcp-server-dev@claude-plugins-official` and `playwright@claude-plugins-official` to `false` in `enabledPlugins`.

#### Scenario: Read the committed project settings
- **WHEN** A test loads `.claude/settings.json` and reads `enabledPlugins`.
- **THEN** The three named plugin entries hold the value `false`.

### Requirement: The used plugins stay on
`.claude/settings.json` SHALL keep `mattpocock-skills@claude-plugins-official`, `pydantic-ai@claude-plugins-official` and `grafana-mcp@claude-plugins-official` set to `true`.

#### Scenario: Read the kept plugin entries
- **WHEN** A test loads `.claude/settings.json` and reads `enabledPlugins`.
- **THEN** The three kept plugin entries hold the value `true`.

### Requirement: The scaffold template carries the same plugin values
`src/devops_cli/templates/claude_settings.json.j2` MUST set the same three plugin entries to `false` and keep the same three entries `true`.

#### Scenario: Compare the rendered template with the committed file
- **WHEN** The test that compares the rendered template with `.claude/settings.json` runs.
- **THEN** The test passes with no difference.

### Requirement: The rest of the settings are unchanged
The change MUST NOT alter the `env` and `permissions` blocks of the two files, or `.claude/settings.local.json`.

#### Scenario: Compare the untouched blocks
- **WHEN** A test compares the `env` and `permissions` blocks of the changed files with the base commit.
- **THEN** Both blocks equal the base commit, and the changed files hold no `.claude/settings.local.json`.

### Existing Tool Considered
No alternatives check has run. The Claude Code `enabledPlugins` project setting covers the need: a value of `false` in the project scope turns a plugin off. The setting lacks nothing for this change, and no code is necessary.

### Key questions
- **Which test keeps the scaffold template and the committed settings file equal?**: The test lives in `tests/commands/test_devcontainer.py`. It compares the rendered template with `.claude/settings.json`, so the same edit in both files keeps it passing. [sources: tests/commands/test_devcontainer.py, src/devops_cli/templates/claude_settings.json.j2, .claude/settings.json]
- **Does the change set each unused plugin entry to `false` or remove the entry?**: Set each of the three entries to `false`. Keep the key, so a person turns a plugin on again with one edit. (best practice) [sources: .claude/settings.json]
  - Chosen: Set the value to `false`. The project scope turns the plugin off and keeps the plugin id for a later turn-on. The body proposes this value.
  - Rejected: Remove the entries. Removal loses the plugin id and hides which plugins the project considered.
- **Who turns off the claude.ai Docs connector?**: The owner turns it off in the claude.ai account settings. The repository holds no file for it, so no pull request does it and this change does not wait on it. (a person decides)

### Open questions
- Who turns off the claude.ai Docs connector? (a person decides)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "New", "Value": "Medium", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "1e115e2ed7f74f226524cdd1814bded23295562773317c21570ea85ba3e51fc8", "refine.commented_at": "2026-11-11T03:20:30+00:00", "refine.comments_seen": "2", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "person", "refine.returned_body_hash": null, "refine.section_hash": "a39aebd6f7a38bceca068ac7fcbf282810c076ce188b963c580d1724378e51a1", "refine.wait_refs": "claude.ai"} -->
