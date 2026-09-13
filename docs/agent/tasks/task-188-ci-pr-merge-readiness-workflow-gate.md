# Task 188: Gate Pull Request Workflow on Unresolved Review Threads and Merge Blockers

**Issue**: [#188](https://github.com/dan-petty/devops-cli/issues/188)
**PR**: [#187](https://github.com/dan-petty/devops-cli/pull/187)
**Status**: In Review
**Milestone**: `v0.2.17`
**Taxonomy**: `type/bug`, `scope/ci`, `priority/high`, `status/in-review`

---

## 1. Overview & Objectives
Update GitHub Actions pull request workflow (`.github/workflows/ci.yml`) and `devops-cli` PR commands to ensure that any issue causing merging to be blocked must be fixed before a pull request can merge. This includes checking for unresolved review discussion threads, merge conflicts with target branch, non-ready/draft states, and validating triggers on `ready_for_review`.

---

## 2. Deliverables
- [x] Add `types: [opened, synchronize, reopened, ready_for_review]` to `.github/workflows/ci.yml` `pull_request` trigger.
- [x] Add `devops pr check-readiness` command in `src/devops_cli/commands/pr.py` to inspect PR mergeability and fail if unresolved review discussion threads or merge conflicts exist.
- [x] Add REST API fallback for `devops pr list` to guarantee zero failures during GraphQL rate limit events.
- [x] Integrate merge readiness check step into `.github/workflows/ci.yml`.
- [x] Author unit tests in `tests/test_pr_cmd.py` validating `devops pr check-readiness` with clean, conflicting, and unresolved thread conditions.
- [x] Verify full CI suite (`devops ci`) and commit changes to `feat/181-native-gh-cli-pr-governance`.
- [x] Remediate merge-blocking issues across all active release PRs (PR #184, PR #186, PR #187).
