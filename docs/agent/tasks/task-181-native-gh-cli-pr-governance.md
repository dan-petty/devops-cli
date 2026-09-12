# Task 181: Implement Native DevOps CLI Functionality for GH Operations and PR Governance

**Issue**: [#181](https://github.com/dan-petty/devops-cli/issues/181)
**PR**: TBD (Draft PR targeting `release/v0.2.17`)
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`

---

## 1. Description & Architectural Objectives

Implement native `devops-cli` commands replacing raw `gh` invocations across pull request management, workflow run inspection, and API rate limit diagnostics to establish consistent workflow control, prevent silent mutation failures, and enforce strict PR governance.

### Key Objectives
1. **Pull Request Management Subcommands**:
   - `devops pr ready <number>`: Programmatically mark a draft pull request as ready for review. Check status via REST, invoke GraphQL mutation, intercept and format rate-limit errors, and assert ground truth (`draft == false`) before success.
   - `devops pr diff <number>`: View unified PR diff with pager and syntax styling.
   - `devops pr close <number>`: Close a PR with optional comment and branch deletion.
2. **Workflow Run Inspection**:
   - `devops gh runs list`: List recent workflow runs for the repository.
   - `devops gh runs view <run_id> [--log-failed]`: View run details and stream/display failed step logs directly.
3. **API Rate Limit Diagnostics**:
   - `devops gh rate-limit`: Query and display REST, GraphQL, Search, and other rate limits with remaining quotas and countdown timers to reset.
4. **FastMCP Server Integration**:
   - Register corresponding FastMCP tools (`pr_ready`, `pr_diff`, `pr_close`, `gh_rate_limit`, `gh_runs_list`, `gh_run_view`).
5. **Agent Governance Hardening**:
   - Update `AGENTS.md` and `CLAUDE.md` to mandate native `devops` commands, explicitly document GitHub draft conversion restrictions, and reinforce PR check monitoring and Human-in-the-Loop policies.
6. **Comprehensive Testing & CI Validation**:
   - Add unit tests for all new commands and options, verifying error states, rate-limit handling, and output formats.
   - Validate that cyclomatic complexity $\le 10$ and nesting depth $\le 5$ project-wide.
   - Pass all 10 `devops ci` quality gates.

---

## 2. Implementation Checklist

- [x] Ground issue [#181](https://github.com/dan-petty/devops-cli/issues/181) in GitHub tracking
- [x] Author dedicated task tracking file `docs/agent/tasks/task-181-native-gh-cli-pr-governance.md`
- [x] Add unit tests for `devops pr ready`, `devops pr diff`, `devops pr close` in `tests/test_pr_cmd.py`
- [x] Add unit tests for `devops gh rate-limit`, `devops gh runs` in `tests/test_gh_cmd.py`
- [x] Implement `ready`, `diff`, and `close` subcommands in `src/devops_cli/commands/pr.py`
- [x] Implement `rate-limit` and `runs` subcommands in `src/devops_cli/commands/gh.py`
- [x] Register FastMCP tools in `src/devops_cli/ai/mcp/server.py`
- [x] Update language catalogs (`help.py`, `messages.py`, `errors.py`)
- [x] Update `AGENTS.md` and `CLAUDE.md` documentation
- [x] Synchronize documentation via `devops docs generate --sync-readme`
- [x] Verify local quality gates with `uv run pytest` and `devops ci`
- [ ] Push topic branch and open Draft PR targeting `release/v0.2.17`
- [ ] Monitor CI checks and address review feedback
