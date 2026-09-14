# Task 175: Project Field Options Synchronization, Complete Pagination & Generic Owner Resolution

**Issue**: [#175](https://github.com/dan-petty/devops-cli/issues/175)
**PR**: [#173](https://github.com/dan-petty/devops-cli/pull/173)
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`

---

## 1. Description & Architectural Objectives

Fix GitHub Projects v2 custom field synchronization to ensure single-select field options (specifically `In Review`, `Backlog`, `Ready`) defined in `.github/project-template.json` are automatically provisioned on existing project fields. Ensure full pagination across all GitHub API queries (`projectsV2/items`, `repos/issues`, `repos/pulls`), and generically resolve personal user vs organization project owners without hardcoded usernames.

### Key Objectives
1. **Single-Select Option Synchronization (`provision_remote_project_fields`)**:
   - Inspect existing single-select fields from `field-list`.
   - Detect missing options defined in `project-template.json` (such as `In Review` on default GitHub status fields).
   - Update remote field options using GraphQL mutation `updateProjectV2Field` without overwriting existing options.
2. **Complete Pagination Across API Queries**:
   - Add `--paginate` to `_fetch_project_item_urls` and support both `users/` and `orgs/` endpoints.
   - Add `--paginate` and `per_page=100` to `_fetch_repository_issues` and `_fetch_repository_prs`.
3. **Generic Owner Resolution**:
   - Implement `_resolve_project_owner_arg(owner)` using dynamic authenticated user detection (`gh api user --jq .login`).
   - Eliminate hardcoded personal account usernames.
   - Provide fallback retry in `_edit_project_item_field` for personal projects.
4. **Draft PR Warning in PR Monitor**:
   - Display a warning rather than a generic error when PR is still a draft in `_handle_monitor_exit`.
5. **Comprehensive Testing**:
   - Unit tests covering option synchronization, pagination, and dynamic owner resolution in `tests/test_github_projects.py`.

---

## 2. Implementation Checklist

- [x] Ground issue [#175](https://github.com/dan-petty/devops-cli/issues/175) in GitHub Projects tracking
- [x] Author dedicated task tracking file `docs/agent/tasks/task-175-project-field-sync-pagination.md`
- [x] Update `docs/agent/task.md` index
- [x] Implement dynamic owner resolution without hardcoded usernames in `src/devops_cli/github/projects.py`
- [x] Implement complete pagination for project items, repository issues, and pull requests
- [x] Implement single-select field options synchronization in `provision_remote_project_fields`
- [x] Update draft PR exit handler in `src/devops_cli/commands/pr.py`
- [x] Author comprehensive unit tests in `tests/test_github_projects.py`
- [x] Validate test suite and code coverage via `pytest`
- [x] Run `devops ci` quality gate
