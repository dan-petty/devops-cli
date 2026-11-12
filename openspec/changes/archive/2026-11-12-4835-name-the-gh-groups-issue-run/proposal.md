# Proposal

## Why

Issue #4835: agents type gh's nouns, and `devops gh` used plural names. `devops gh issue ...` failed 630 times from 2026-09-23 to 2026-11-11 in the Claude Code, Kilo and Antigravity records. That is 36% of the 1,737 usage errors found (tracker #4833). `devops gh run` failed 48 times. After a failure, most agents sent `devops gh api` to the same resource. The plural came from the repository text, not from gh. The hidden `rate_limit` command was a compatibility alias, which the alpha rule of AGENTS.md does not permit.

## What Changes

- Rename four groups of `devops gh` to gh's nouns: `issues` to `issue`, `runs` to `run`, `labels` to `label` and `secrets` to `secret`. Add no alias. Typer prints `Did you mean 'issue'?` for an old plural.
- Keep `project`, `pr`, `api` and `status`, which have gh's name. Keep `milestones`, `views`, `pages`, `metrics`, `branch-protection` and `rate-limit`, which have no gh peer.
- Remove the hidden `rate_limit` command. Typer suggests `rate-limit` for it.
- Rename every surface that names an old group in the same pull request:
  - the MCP tool names (`gh_issues_view` to `gh_issue_view`) in `CONST_MCP_EXPOSURE_TABLE`, `ai/mcp/roles.py`, `ai/mcp/path_confinement.py` and the tool-listing snapshot;
  - the MCP resource `resource://gh/issues/status` to `resource://gh/issue/status`;
  - the roadmap tool registry `roadmap/tools.py`;
  - the help keys of `lang/en/help.py`, the text of `lang/en/messages.py`, `roadmap/stores/store.py` and `roadmap/workflow_labels.py`;
  - the knowledge base, README.md, CONTRIBUTING.md, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `docs/roadmap/intake.md`, `docs/adr/0001-github-is-the-roadmap-source.md` and `.github/labels.yml`;
  - the tests, and the generated `docs/CLI_REFERENCE.md`, `docs/commands/gh.md` and `docs/MCP_TOOLS.md`.
- Correct the comment in `ai/mcp/dispatcher.py`: gh names the command `gh secret set`.
- Add one naming rule to CONTRIBUTING.md: a `devops gh` or `devops pr` command that does the work of a gh command takes gh's name and flag names.
- Add a test with a table of gh nouns that fails when a `devops gh` command for a gh noun has another name, and a test that an old name is a usage error that names the new one.
- The command names are observable, so the change adds the capability `gh-command-names` and modifies the requirements that name the old groups. The capability ids `gh-issues-close` and `gh-issues-view`, the requirement names and the scenario names stay. The `## Purpose` lines of `gh-issues-close` and `gh-issues-view` name the new group; a Purpose is not a requirement, so the change edits it in place.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `gh-command-names`: how `devops gh` names a command that does the work of a gh command, and what an old name does.

### Modified Capabilities

- `command-dry-run-class`: `gh-issues-milestones-labels-runs-request-plans` and `gh-api-status-branch-protection-secrets-request-plans` name the new groups.
- `gh-issues-close`: both requirements name `devops gh issue close`.
- `gh-issues-view`: the requirement names `devops gh issue view`.
- `mcp-role-server`: the scenario of the mutating tool names `gh_issue_create`.
- `roadmap-inbox`: the clearing step names `devops gh label sync`.
- `roadmap-stage`: the allow-list scenario names `('gh', 'label', 'list')`.

## Impact

- Command lines: `devops gh issue|run|label|secret ...` replace the plural forms. The plural forms and `devops gh rate_limit` exit 2.
- MCP clients: the gh tools of the four groups get new names, and the issue resource gets a new URI. The role tables and the roadmap tool registry hold the new names, so the job roles keep the same tools.
- The Service: no ConfigMap, manifest or workflow names an old group (`git grep` over `k8s`, `tf` and `.github/workflows` prints nothing), so the Service needs no preparation.
- Agent memory files outside git that name the plural get the new names after the merge.

## Feasibility

All commands ran on 2026-11-12 in a worktree at origin/main `92087179`, with Typer 0.27.2 and Click 8.5.0.

- gh names each group with a singular noun: `gh issue`, `gh run`, `gh label`, `gh secret`, `gh project`, `gh pr`, `gh api` and `gh status` (gh manual, cli.github.com/manual, gh 2.x). Bare gh was not run (AGENTS.md rule 7).
- Typer suggests a close name for an unknown command: `uv run devops gh issue view 1` printed `No such command 'issue'. Did you mean 'issues'?`, and `uv run devops gh rate_limitx` printed `Did you mean 'rate_limit', 'rate-limit'?`. Typer's `suggest_commands` setting is on by default (`typer/main.py`).
- The new tests failed on the base: 9 failed and 4 passed (`pr`, `project`, `api`, `status` already have gh's name).
- `git grep -wE 'devops gh (issues|runs|labels|secrets)' -- ':!CHANGELOG.md' ':!openspec/changes/archive' ':!docs/agent/archive' | wc -l` printed 151 on the base.
- No active change names an old group: `git grep` of the four plurals and their tool names over `openspec/changes`, without the archive, printed nothing.

## Existing Tool Considered

gh's own command names are the reference. Typer's command suggestion (difflib) tells a caller the new name, so the change builds no alias and no suggestion code. The change deletes the hidden `rate_limit` command registration.

## Acceptance

Criteria of the issue, and the group of `tasks.md` that delivers each:

- `devops gh issue view 1 --help`, `gh run list --help`, `gh label list --help` and `gh secret list --help` exit 0: group 1.
- `devops gh issues view 1` exits 2 and prints `Did you mean 'issue'?`, the same for `runs`, `labels` and `secrets`, and `devops gh rate_limit` suggests `rate-limit`: group 1.
- The `git grep` of the plural forms prints 0 lines: groups 2 and 3.
- The MCP tool-listing snapshot holds `gh_issue_view` and no tool that starts with `gh_issues_`, `gh_runs_`, `gh_labels_` or `gh_secrets_`: group 2.
- The gh-noun test fails when one group gets its old name back: group 1.
- The docs argv check and the required CI checks pass: group 3 and the pull request checks.
