# Task 697: Defect PRs Carry Their Hardening Readiness Blocker and Post-Merge Audit

**Issue**: [#697](https://github.com/dan-petty/devops-cli/issues/697)
**Status**: Done
**Milestone**: `v0.2.34`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

The rule requiring defect PRs to add guardrails to declared surfaces (`AGENTS.md`, task files, knowledge base, anti-hallucination catalog) was documented in `AGENTS.md` and `docs/SELF_IMPROVEMENT.md` but unenforced. This deliverable delivers a measurement command (`devops pr hardening-report`), a post-merge audit workflow that hands findings to intake, and a shared defect-PR classifier, ensuring hardening compliance is verified and violations are surfaced.

Per the 2026-10-08 refinement, Slice 2 (the readiness blocker) is deferred to #998's verdict module, the `SELF_IMPROVEMENT.md` rewording is dropped, and Slice 3 hands findings to intake rather than opening an issue via `create_repository_issue`.

#### Key Deliverables:
- [x] **Defect PR Classifier** (`src/devops_cli/github/defect_classifier.py`, `src/devops_cli/github/__init__.py`):
  - Added `classify_defect_pr`, `is_defect_pr`, `match_hardening_surface`, and `audit_pr_hardening`.
  - Classifies pull requests as defects if they carry `type/bug` or `type/security` labels or match Conventional Commits `fix(...)` / `fix:` titles.
- [x] **Declared Hardening Surfaces** (`src/devops_cli/config/constants.py`):
  - Defined `CONST_HARDENING_SURFACES`: `AGENTS.md`, `src/devops_cli/ai/tasks/*.md`, `src/devops_cli/ai/knowledge_base/`, `common_hallucinations.json`.
  - `docs/ROADMAP.md` is strictly excluded because it is a generated view.
- [x] **Hardening Report Command** (`src/devops_cli/commands/pr.py`):
  - Implemented `devops pr hardening-report [--pr N] [--fail-on-missing] [--format table|json] [--limit N]`.
  - Evaluates additions on declared surfaces for defect PRs, supports single PR auditing and bulk merged PR inspection, with table and JSON outputs.
- [x] **Post-Merge Audit Workflow** (`.github/workflows/defect-pr-hardening-audit.yml`):
  - Triggers on `pull_request` types `[closed]` gated on `merged == true` and defect labels (`type/bug`, `type/security`).
  - Executes `devops pr hardening-report --pr "$PR_NUMBER" --fail-on-missing`.
  - Hands unhardened defect findings to roadmap intake on failure via `devops roadmap intake`.
  - Implements skip-not-fail for fork PRs.
- [x] **Workflow Contract Tests** (`tests/test_workflow_contracts.py`):
  - Added `assert_audit_workflow_contract`, `test_defect_pr_hardening_audit_workflow_contract`, `test_defect_pr_hardening_audit_workflow_mutation`.
  - Added `test_audit_workflow_devops_commands_resolve` verifying static resolution of workflow commands against the Typer CLI app.
- [x] **Unit & Integration Tests** (`tests/test_defect_classifier.py`, `tests/test_pr_hardening_report.py`):
  - Added comprehensive test suites with structural tuple equality assertions.
- [x] **Changelog Fragment** (`changelog.d/697.md`).
- Hardening readiness blocker gate in `devops pr check-readiness` deferred to #998.

---

## 2. Technical Invariants & Verification

- Consolidated structural tuple equality assertions across all test suites.
- McCabe cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained across all new and modified modules.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
