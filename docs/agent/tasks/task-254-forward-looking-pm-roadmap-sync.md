# Task 254: Forward-Looking Project Management, Roadmap Reconstruction, Compactor Hardening & Issue Sync

**Issue**: [#254](https://github.com/dan-petty/devops-cli/issues/254)
**PR**: [#255](https://github.com/dan-petty/devops-cli/pull/255)
**Status**: Review / In Progress
**Milestone**: `v0.2.20`
**Priority**: `priority/p0-critical`
**Scope**: `scope/github`, `scope/cli`, `scope/ai`

---

## 1. Description & Objectives

Establish a forward-looking project management paradigm across agent instructions, persona prompts, and automated tooling:
1. **Forward-Looking Mandate (`AGENTS.md` & AI Prompts)**: Project management must always be forward-looking—proactively adding ideas, suggestions, useful features, meaningful integrations, and strategic tasks to `docs/ROADMAP.md` and propelling the project in that direction. Update PM persona, Architect persona, review prompts, and agent instructions.
2. **Reconstruct Strategic Roadmap (`docs/ROADMAP.md`)**: Restore completed series summary (`v0.0.1 – v0.1.9` and `v0.2.0 – v0.2.19`), active milestone `v0.2.20 (Current Release / Active Development)`, scheduled milestones `v0.2.21`, `v0.2.22`, `v0.2.23`, and `v0.3.0 (Future Vision)`, along with the full Value vs. Effort Prioritization Matrix.
3. **Harden Documentation Compaction Logic (`src/devops_cli/docs/compactor.py`)**: Ensure compaction only ever consolidates completed milestone subsections (`- Completed`) and completed matrix rows (`✅ Completed`), strictly preserving scheduled/in-progress milestones and matrix rows.
4. **Automated Roadmap-to-Issue & Task Synchronization Engine (`src/devops_cli/github/roadmap_sync.py`)**: Parse uncompleted roadmap items from `docs/ROADMAP.md`, query existing issues/tasks to eliminate duplicates, automatically create GitHub Issues with taxonomy labels, generate local per-task tracking files, and sync to GitHub Projects v2.

#### Key Deliverables:
- [x] 1. Update `AGENTS.md` with Forward-Looking Project Management & Continuous Roadmap Evolution Mandate.
- [x] 2. Update AI persona prompts (`pm/prompt.md`, `pm/role.md`, `architect/prompt.md`) and task prompts (`code_review_prompt.md`, `diff_review_prompt.md`, `path_review_prompt.md`, `architecture_analysis_prompt.md`, `review.md`).
- [x] 3. Reconstruct `docs/ROADMAP.md` with full milestones and matrix.
- [x] 4. Harden `compactor.py` and expand `tests/test_docs_compactor.py`.
- [x] 5. Implement `src/devops_cli/github/roadmap_sync.py`, CLI command `devops gh issues sync-roadmap`, FastMCP tool `gh_sync_roadmap`, and tests in `tests/test_github_roadmap_sync.py`.
- [x] 6. Enforce $M \le 10$, depth $\le 5$, structural tuple equality in tests, and 100% pass on all 10 CI gates (`uv run devops ci`).
