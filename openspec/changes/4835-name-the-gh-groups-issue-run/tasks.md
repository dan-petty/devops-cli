# Tasks

## 1. The gh groups take gh's nouns
kind: behavior

- [x] 1.1 Write failing tests: `devops gh <noun> --help` exits 0 for each gh noun of the table, and `devops gh <old> list` exits 2 and names the new name for `issues`, `runs`, `labels`, `secrets` and `rate_limit`
  - Verification: `$ uv run devops ci test tests/commands/test_gh_cmd.py`
- [x] 1.2 Rename the groups `issues`, `runs`, `labels` and `secrets` of `src/devops_cli/commands/gh.py` to `issue`, `run`, `label` and `secret`, with their sub-app variables and the help keys of `GHCommandHelp`, and delete the hidden `rate_limit` command
  - Verification: `$ uv run devops ci test tests/commands/test_gh_cmd.py tests/commands/test_gh_issues_close.py tests/commands/test_github_milestones.py tests/commands/test_cli_format_adoption.py`
- [x] 1.3 Rename the command paths of `CONST_MCP_EXPOSURE_TABLE`, the MCP tool names in `ai/mcp/roles.py`, `ai/mcp/path_confinement.py` and `roadmap/tools.py`, the resource `resource://gh/issue/status`, and the tool-listing snapshot
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py tests/ai/mcp/test_mcp_tool_registry.py tests/ai/mcp/test_mcp_roles.py tests/ai/mcp/test_mcp_prompts_and_resources.py tests/roadmap/stage/test_stage_run_allowlist.py`
- [x] 1.4 Rename the old groups in the messages, the roadmap store, the other tests and their fixtures, and correct the `gh secret set` comment of `ai/mcp/dispatcher.py`
  - Verification: `$ uv run devops ci test tests/github/test_gh_issues_milestones_labels_runs_dry_run.py tests/github/test_gh_api_status_branch_protection_secrets_dry_run.py tests/github/test_github_secrets.py tests/github/test_gh_issues_milestones.py tests/github/test_github_issues.py tests/invariants/test_workflow_contracts.py tests/invariants/test_dry_run_class_ratchet.py`

## 2. Documents
kind: documents

- [x] 2.1 Rename the old groups in the knowledge base, README.md, CONTRIBUTING.md, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `docs/roadmap/intake.md`, `docs/adr/0001-github-is-the-roadmap-source.md` and `.github/labels.yml`, add the gh naming rule to CONTRIBUTING.md, and regenerate the references with `devops docs generate --sync-readme`
  - Verification: `$ ! git grep -nwE 'devops gh (issues|runs|labels|secrets)' -- ':!CHANGELOG.md' ':!openspec' ':!docs/agent/archive'`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, rename the plural groups in the agent memory files outside git.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
