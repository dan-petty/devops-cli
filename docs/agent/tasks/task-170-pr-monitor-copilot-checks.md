# Task 170: Automated PR Monitoring for CI Checks, Copilot Reviews & Review Threads

**Issue**: [#170](https://github.com/dan-petty/devops-cli/issues/170)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p0-critical`
**Scope**: `scope/github`

---

## 1. Description & Architectural Objectives

Implement an automated PR monitoring engine and CLI command (`devops pr monitor` / `devops pr wait`) that continuously tracks remote CI checks, GitHub Copilot review sessions, and unresolved review discussion threads. Update AI agent instructions to mandate running `devops pr monitor` before marking any PR task complete or ready for merge, eliminating premature handoffs and unaddressed Copilot review feedback.

### Key Objectives
1. **Automated PR Monitoring Subsystem (`src/devops_cli/github/pr_monitor.py`)**:
   - Collect and parse structured check runs from GitHub (`statusCheckRollup`).
   - Detect active Copilot review sessions (`copilot_work_started` vs `reviewed` events, review settling windows).
   - Query and inspect all unresolved review discussion threads via GraphQL (`list_pr_review_threads`).
   - Enforce bounded timeouts, configurable polling intervals, and settling grace periods.
2. **First-Class CLI Command (`devops pr monitor` / `devops pr wait`)**:
   - Auto-detect branch PR if number not specified.
   - Render live progress and summary tables for checks and review threads.
   - Strict exit code protocol:
     - `0`: Ready for merge (all checks passed, Copilot review complete, 0 unresolved threads).
     - `1`: CI checks failed.
     - `2`: Unresolved review threads exist.
     - `3`: Timeout exceeded.
3. **FastMCP Server Tool (`pr_monitor`)**:
   - Expose `pr_monitor` tool in `src/devops_cli/ai/mcp/server.py` for AI agent environments.
4. **Agent Instruction & Governance Alignment**:
   - Mandate running `devops pr monitor` immediately after creating or pushing to a PR branch in `AGENTS.md`, `src/devops_cli/ai/instruction_generator.py`, `docs/ROUTINE_TASKS.md`, and `docs/SDLC.md`.
   - Mandate concise, effect-driven commit messages.
   - Prohibit concluding tasks or asking user to merge with pending checks or unresolved review threads.
5. **Comprehensive Testing**:
   - Unit tests for `pr_monitor` subsystem and Typer CLI commands in `tests/test_github_pr_monitor.py` and `tests/test_pr_cmd.py`.

---

## 2. Implementation Checklist

- [x] Author task tracking file `docs/agent/tasks/task-170-pr-monitor-copilot-checks.md`
- [x] Add help, message, and error strings in `src/devops_cli/lang/en/`
- [x] Implement `src/devops_cli/github/pr_monitor.py` with `PRMonitorStatus`, `get_pr_monitoring_status`, and `monitor_pr`
- [x] Implement `devops pr monitor` / `devops pr wait` command in `src/devops_cli/commands/pr.py`
- [x] Expose `pr_monitor` tool in `src/devops_cli/ai/mcp/server.py`
- [x] Author unit tests in `tests/test_github_pr_monitor.py`
- [x] Author CLI tests in `tests/test_pr_cmd.py`
- [x] Update `AGENTS.md` with PR monitoring gate and concise commit messages
- [x] Update `src/devops_cli/ai/instruction_generator.py` template
- [x] Update `docs/ROUTINE_TASKS.md` and `docs/SDLC.md`
- [x] Regenerate documentation via `devops docs generate --sync-readme`
- [x] Validate entire CI suite via `uv run devops ci`
- [ ] Open draft PR targeting `release/v0.2.17` and verify via `devops pr monitor`
