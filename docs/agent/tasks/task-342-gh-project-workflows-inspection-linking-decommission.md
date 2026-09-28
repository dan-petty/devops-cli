# Task 342: GitHub Projects v2 Built-In Workflows Inspection & Linking, Decommission Bot Project-Automation Workflow

**Issue**: [#342](https://github.com/dan-petty/devops-cli/issues/342)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

The automated GitHub Actions workflow `.github/workflows/project-automation.yml` was repeatedly failing because `github-actions[bot]` does not have permission to mutate user-owned GitHub Projects v2 boards (`createProjectV2` / item mutations on personal user accounts). In addition, project boards were not reliably discovered when queries relied strictly on organization/user scopes rather than the linked repository's GraphQL projects connection.

This task resolves the root cause by:
1. Decommissioning `.github/workflows/project-automation.yml` in favor of native GitHub Projects v2 built-in workflows (which execute server-side within GitHub without requiring bot permissions or Actions minutes).
2. Adding CLI tooling (`devops gh project workflows list`) to inspect project automations, their enabled/disabled state, and direct configuration links.
3. Enhancing `link_project_to_repository` and `find_remote_project` to query linked repository projects via GraphQL `repository.projectsV2`, resolving user boards without permission errors.
4. Adding an explicit guard to `create_remote_project` so `github-actions` runners cannot attempt unauthorized project creation on user accounts without an explicit personal access token (`PROJECT_TOKEN`).

#### Key Deliverables:
- [x] **Decommission Bot Project Automation Workflow**: Removed `.github/workflows/project-automation.yml` and updated documentation/comments in `.github/workflows/ci.yml`.
- [x] **Project Workflow Inspection CLI**: Added `devops gh project workflows list` supporting tabular view and `--json` machine-readable output.
- [x] **Repository Project Discovery & Linking**: Updated `_find_project_via_repo` and `find_remote_project` to resolve linked repository projects first, and fixed parameter formatting in `link_project_to_repository`.
- [x] **Bot Guard in Project Creation**: Guarded `create_remote_project` against unauthorized `github-actions` bot executions.
- [x] **Test Coverage & Architectural Invariants**:
  - Authored unit test suite in `tests/test_gh_project_workflows.py` with structural tuple equality assertions.
  - Verified cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all modified modules.
  - Verified 100% compliance with Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Unit Tests**: 12/12 passed in `tests/test_gh_project_workflows.py`.
- **Architectural Invariants**: All invariants passed in `tests/test_architectural_invariants.py`.
- **Complexity Scan**: Passed with $M \le 10$ and depth $\le 5$.
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
