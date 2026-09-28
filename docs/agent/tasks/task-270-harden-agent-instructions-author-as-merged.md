# Task 270: Harden Agent Instructions to Author Deliverables as Merged and Prohibit Administrative Tracking PRs

**Issue**: [#270](https://github.com/dan-petty/devops-cli/issues/270)
**Status**: Done
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

Harden `AGENTS.md` with explicit, binding engineering instructions:
- [x] 1. **Author All Code, Documentation, Status & Wording as Merged/Committed**: Codify the requirement that all code, documentation, checklists, deliverable descriptions, and task tracking files must be written from the outset in their final completed state as they will read once committed and merged.
- [x] 2. **Strict Prohibition of Standalone Tracking Commits & Follow-Up Status PRs**: Codify the strict prohibition against creating one-off task tracking commits, topic branches, or follow-up pull requests solely to adjust or flip task statuses post-merge.
- [x] 3. **Strict Prohibition of Inconsistent N-Gate Numbering & Unified `Gated` Terminology**: Codify the strict prohibition against hardcoded gate numbering (`7-Gate`, `10-Gate`) and mandate the unified `Gated` terminology across all code, tests, docstrings, help strings, and documentation.

---

## 2. Verification Results

- **Invariants & Quality Gates**: `uv run devops ci` passing 100% across all checks.
- **Documentation Freshness**: `uv run devops docs generate --sync-readme` verified clean.
- **Instruction Integrity**: `AGENTS.md` updated and hardened.
