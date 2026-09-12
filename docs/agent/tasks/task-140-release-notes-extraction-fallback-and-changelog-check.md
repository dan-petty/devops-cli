# Task 140: Add Release Notes Extraction Fallback and Enforce Changelog Version Check

**Issue**: [#140](https://github.com/dan-petty/devops-cli/issues/140)
**PR**: [#160](https://github.com/dan-petty/devops-cli/pull/160)
**Status**: Done
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

Resolve release orchestration failures where release notes extraction fails due to missing version headers or changelog discrepancies:
1. `devops release check`: Enforce matching version in `CHANGELOG.md` when verifying releases. Fail with code 1 instead of emitting a non-fatal warning if `CHANGELOG.md` is missing or disagrees with `pyproject.toml`.
2. `devops release notes`: Implement a layered fallback mechanism:
   - Primary: Extract from `CHANGELOG.md`.
   - Secondary fallback: Extract from `docs/RELEASE_NOTES.md`.
   - Tertiary fallback: Extract from git commit log (`git log <prev_tag>..HEAD` or `git log -n 20`).
3. `.github/workflows/release.yml`: Add defensive fallback to git commit log if release notes extraction command fails or produces an empty file.
4. Comprehensive test-first validation in `tests/test_release.py`.

---

## 2. Planned Changes

1. `src/devops_cli/commands/release.py`:
   - Update `release_check`: Treat missing or mismatched `CHANGELOG.md` version as a fatal error (`Exit(1)`).
   - Implement `_extract_docs_release_notes(root: Path, version: str) -> str | None`.
   - Implement `_extract_git_commit_notes(root: Path, version: str) -> str | None`.
   - Update `_extract_changelog_notes` to flexibly match optional `v` prefix.
   - Update `release_notes` command to utilize layered fallbacks so it reliably succeeds.
2. `.github/workflows/release.yml`:
   - Guard `Extract Release Notes` step with fallback to `git log` if empty.
3. `tests/test_release.py`:
   - Add unit tests verifying:
     - `devops release check` fails when `CHANGELOG.md` version is missing or mismatched.
     - `devops release check` passes when `CHANGELOG.md` matches `pyproject.toml`.
     - `devops release notes` extracts notes from `CHANGELOG.md`.
     - `devops release notes` falls back to `docs/RELEASE_NOTES.md` when changelog entry is absent.
     - `devops release notes` falls back to `git log` when neither markdown file has the target version.

---

## 3. Progress Tracker

- [x] Dedicated Topic Branch (`fix/140-release-notes-fallback-changelog-check`)
- [x] Test-First Specification in `tests/test_release.py`
- [x] Implementation in `src/devops_cli/commands/release.py`
- [x] Hardening in `.github/workflows/release.yml`
- [x] Verification of Quality Gates (`uv run devops ci`)
- [x] Pull Request authoring & CI monitoring
- [x] Squash Merge to `release/v0.2.16` & Issue Closure (#140, #160)
