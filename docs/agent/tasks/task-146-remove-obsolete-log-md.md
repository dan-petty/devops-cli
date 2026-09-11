# Task 146: Remove Obsolete Development Log and Redundant Pending Features Docs (`docs/LOG.md`, `docs/PENDING_FEATURES.md`)

**Issue**: [#146](https://github.com/dan-petty/devops-cli/issues/146)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.16`
**Priority**: `priority/p3-low`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

`docs/LOG.md` was an early monolithic development log that accumulated historical notes and phase updates. Similarly, `docs/PENDING_FEATURES.md` duplicated milestone feature lists already canonically maintained in `docs/ROADMAP.md`. In modern releases, all planning, deliverables, and chronological activities are formally tracked across:
1. **GitHub Issues & Projects v2**: Grounded task lifecycle (`Backlog` -> `Ready` -> `In Progress` -> `In Review` -> `Done`).
2. **Modular Per-Task Architecture (`docs/agent/tasks/`)**: Isolated per-task specifications eliminating merge conflicts.
3. **`CHANGELOG.md` & `docs/RELEASE_NOTES.md`**: Authoritative release histories and user-facing release notes.
4. **`docs/ROADMAP.md`**: Master roadmap and milestone deliverables (single source of truth).

Retaining `docs/LOG.md` and `docs/PENDING_FEATURES.md` creates documentation drift, redundant tracking overhead, and token bloat in LLM context windows.

---

## 2. Planned Changes

1. **Delete Obsolete Files**:
   - `docs/LOG.md`: Remove obsolete development log.
   - `docs/PENDING_FEATURES.md`: Remove duplicate milestone document in favor of `docs/ROADMAP.md`.
2. **Clean Pointers & References**:
   - `README.md`: Remove pointers to `docs/LOG.md` and `docs/PENDING_FEATURES.md`.
   - `docs/KNOWN_ISSUES.md`: Remove citation of `docs/LOG.md`.
   - `docs/ROUTINE_TASKS.md`: Remove `docs/LOG.md` compaction reference.
   - `docs/SDLC.md`: Remove `docs/PENDING_FEATURES.md` synchronization references.
   - `AGENTS.md`: Remove `docs/LOG.md` and `docs/PENDING_FEATURES.md` from mandatory planning artifacts list.
3. **Verification**:
   - Run `devops docs generate --sync-readme` to ensure documentation references and README stay clean.
   - Run full CI quality gate (`uv run devops ci`).
