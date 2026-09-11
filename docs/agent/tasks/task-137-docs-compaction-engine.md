# Task 137: Automated Release Series Documentation Compaction Engine (v0.2.x -> v0.3.x)

**Issue**: [#137](https://github.com/dan-petty/devops-cli/issues/137)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Implement automated, declarative documentation compaction functionality in `devops-cli` under `devops docs compact` and `devops_cli.docs.compactor` capable of summarizing historical release series (specifically `v0.2.x` milestones, highlights, matrix entries, and sprint logs) when transitioning to `v0.3.x`.

This fulfills the SDLC requirements defined in `AGENTS.md` (Section 3: *Mandatory Historical Documentation Compaction on Major & Minor Releases*) and `docs/ROUTINE_TASKS.md` (Cadence C, Step 8: *Automated Historical Documentation Compaction*).

### Key Deliverables
1. **Core Compaction Engine (`src/devops_cli/docs/compactor.py`)**:
   - `DocCompactor` class providing:
     - `compact_roadmap(content: str, series: str = "v0.2") -> str`: Consolidates completed `v0.2.x` subsections into a single summary block and compacts prioritization matrix rows by category.
     - `compact_release_notes(content: str, series: str = "v0.2") -> str`: Merges individual `v0.2.X` highlight sections into a unified `Highlights of v0.2 Series` section.
     - `compact_log(log_content: str, series: str = "v0.2") -> tuple[str, str]`: Moves historical entries to `docs/agent/archive/historical-phases-<series>.md` and inserts pointer references in `docs/LOG.md`.
     - `compact_all(...)`: Orchestrates full or selective compaction with dry-run and check capabilities.
2. **CLI Subcommand Integration (`devops docs compact`)**:
   - Integrated into `src/devops_cli/commands/docs.py` with `@dry_run_command`, `--series`, `--dry-run`, `--check`, `--roadmap-only`, `--release-notes-only`, and `--log-only`.
3. **Domain Exceptions & Localization**:
   - `DocCompactionError` in `src/devops_cli/exceptions/docs.py`.
   - Localized strings in `src/devops_cli/lang/en/help.py` and `messages.py`.
4. **FastMCP Server Registration**:
   - Expose `docs_compact` tool in `src/devops_cli/ai/mcp/server.py`.
5. **Test-First Verification (TDD)**:
   - Comprehensive test suite in `tests/test_docs_compactor.py`.
   - 10-gate CI suite (`uv run devops ci`).

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#137) with milestone `v0.2.16`.
- [x] Create dedicated topic branch `feat/docs-compaction-engine`.
- [x] Create task tracking document `docs/agent/tasks/task-137-docs-compaction-engine.md`.
- [x] Author test-first test suite `tests/test_docs_compactor.py`.
- [x] Implement `src/devops_cli/exceptions/docs.py` and export in `devops_cli.exceptions`.
- [x] Implement `src/devops_cli/docs/compactor.py` and export in `devops_cli.docs`.
- [x] Update `src/devops_cli/lang/en/help.py` and `messages.py`.
- [x] Implement `devops docs compact` command in `src/devops_cli/commands/docs.py`.
- [x] Register `docs_compact` tool in `src/devops_cli/ai/mcp/server.py` and export schemas.
- [x] Verify unit tests and 10-gate CI suite (`devops ci`).
- [x] Commit, push to `origin/feat/docs-compaction-engine`, and open PR targeting `release/v0.2.16`.
