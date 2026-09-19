# Task 267: Replace Inconsistent N-Gate References with Gated Across Codebase and Docs

**Issue**: [#267](https://github.com/dan-petty/devops-cli/issues/267)
**PR**: [#268](https://github.com/dan-petty/devops-cli/pull/268)
**Status**: Merged
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

Replace all inconsistent and hard-to-maintain `N-Gate` (e.g. `7-Gate`, `10-Gate`, `7-gate`, `10-gate`) references across code, tests, help strings, and documentation with a unified `Gated` convention.

#### Key Deliverables:
- [x] 1. Update release PR description generator in `src/devops_cli/commands/release.py` (`10-Gate` -> `Gated`).
- [x] 2. Update release tests in `tests/test_release.py` (`10-Gate` -> `Gated`).
- [x] 3. Update CLI help strings in `src/devops_cli/lang/en/help.py` (`7-gate` -> `Gated`).
- [x] 4. Update knowledge base topics (`src/devops_cli/ai/knowledge_base/`).
- [x] 5. Update core documentation (`ARCHITECTURE.md`, `RELEASE_CYCLE.md`, `CHANGELOG.md`, `docs/RELEASE_NOTES.md`, `docs/ROADMAP.md`).
- [x] 6. Regenerate and synchronize CLI documentation (`devops docs generate --sync-readme`).
- [x] 7. Ensure 100% passing status across all CI quality gates (`uv run devops ci`).

---

## 2. Verification Results

- **Unit Tests**: `uv run pytest tests/test_release.py` -> 39/39 passing (100%).
- **Architectural Invariants**: `uv run pytest tests/test_architectural_invariants.py` -> 8/8 passing (100%).
- **Complexity Scan**: `uv run devops scan complexity src/devops_cli/commands/release.py` -> Within standard limits ($M \le 10$, depth $\le 5$).
- **Documentation Freshness**: `uv run devops docs generate --sync-readme` -> Verified clean synchronization across `docs/CLI_REFERENCE.md`, `docs/commands/release.md`, and `README.md`.
- **Search Verification**: `git grep -iE "[0-9]+-gate"` -> 0 matches found across tracked repository.
