# Task 218: Fix Release Draft PR Description Generator and Milestone Deliverable Resolution

**Issue**: [#218](https://github.com/dan-petty/devops-cli/issues/218)
**Status**: Done
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`, `scope/github`

---

## 1. Description & Objectives

When creating release pull requests via `devops release pr`, the generator previously suffered from several issues:
1. **Milestone Deliverable Grounding**: Release PRs lacked automated milestone issue queries and grounding under merge controls.
2. **Stale Changelog Duplication**: When local git tags were missing or stale, commit extraction fell back to older tags, causing `CHANGELOG.md` to duplicate prior release deliverables under the new release heading. The PR description generator then copied these duplicated notes into PR descriptions.
3. **Outdated Quality Checklist**: The release PR template referenced an obsolete `Gated CI Quality Gate passing (devops ci run)` instead of the authoritative Gated suite (`devops ci`), with static checked boxes even in draft mode.

#### Key Deliverables:
1. **Target Milestone Deliverables Resolution ([`src/devops_cli/commands/release.py`](file:///workspaces/devops-cli/src/devops_cli/commands/release.py))**:
   - Query milestone issues via `run_gh` rate limiter and format under `### Target Milestone Deliverables` for draft PRs.
   - Fall back gracefully to branch conventional commit logs when milestone issue queries return empty or offline.
2. **Stale Duplicate Changelog Detection**:
   - Added `_is_stale_duplicate_changelog` to compare extracted release notes against the preceding release section in `CHANGELOG.md` and discard duplicate entries.
   - Added `_resolve_clean_release_notes` to cleanly fall back to branch commit logs or standardized initial preparation text.
3. **Authoritative Gated CI Checklist**:
   - Added `_build_quality_checklist` supporting dynamic draft checkbox states (`- [ ]` in draft mode vs. `- [x]` when ready).
4. **Clean Changelog & Live PR Patch**:
   - Cleaned `CHANGELOG.md` for `v0.2.19` and updated live Draft PR [#217](https://github.com/dan-petty/devops-cli/pull/217) description on GitHub.
5. **Quality Certification**:
   - Added comprehensive unit tests in [`tests/test_release.py`](file:///workspaces/devops-cli/tests/test_release.py).
   - Zero cyclomatic complexity violations ($\le 6$) and zero nesting violations ($\le 3$).
   - 100% passing across all 10 CI quality gates.
