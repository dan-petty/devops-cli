# Task 642: Remediate Review Findings 20260927-040516 and Enhance Feedback Loop

**Issue**: [#642](https://github.com/dan-petty/devops-cli/issues/642)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Remediate valid findings and systemic defects identified during review session `/workspaces/devops-cli/.data/reviews/20260927-040516`, fix subprocess sandbox criteria execution, harden repository and PR check parsers, update review verification and persona prompts against recurring false positives, and close the review feedback loop with exported feedback.

### Key Deliverables Completed:
- [x] **Subprocess Criteria Execution & Host Sandbox Environment** (`src/devops_cli/config/constants.py`):
  - Added `("HOME", "/tmp")` to `CONST_HOST_SANDBOX_DEFAULT_ENV` so subprocess criteria running inside bubblewrap (`bwrap --clearenv`) can import `devops_cli` without throwing `RuntimeError: Could not determine home directory.` during `Path.home()` calls.
- [x] **Safe GitHub API Check-Runs Parsing** (`src/devops_cli/commands/pr.py`):
  - Hardened `_failing_check_runs` against `payload.get("check_runs")` returning `None` or non-list values, preventing `TypeError: 'NoneType' object is not iterable`.
- [x] **Process Group Termination Safety** (`src/devops_cli/ai/harness/shell.py`):
  - Added explicit handling for `(ProcessLookupError, PermissionError)` in `_terminate_process_group` to handle reaped or terminated processes gracefully.
- [x] **Prompt Hardening & Invalidation Rules for Review and Verification Systems**:
  - Updated `src/devops_cli/ai/tasks/verify_finding_system.md` with explicit falsification rules:
    - **Roadmap & Specification Files**: Explicitly invalidate findings on `docs/ROADMAP.md` or planned architecture docs claiming future/unimplemented features are code defects.
    - **Pydantic Default Factories**: Invalidate claims that `Field(default_factory=dict)` or `Field(default_factory=list)` creates a shared mutable default. In Pydantic v2, `default_factory` produces a new instance per object creation.
    - **Structural Tuple Equality Assertions**: Invalidate claims that structural tuple equality in test assertions (`assert (a, b) == (x, y)`) is "incorrect assertion logic". This is a required invariant for McCabe complexity minimization.
    - **Tautological Criteria Guard**: Invalidate findings where `verification_criteria` tests the proposed fix or python builtins rather than demonstrating the vulnerability in the codebase.
  - Updated `src/devops_cli/ai/tasks/docs_review_prompt.md` to instruct models that roadmap files describe planned future work rather than existing code defects.
  - Updated `src/devops_cli/ai/personas/devsecops/prompt.md` to reinforce that architectural conventions and roadmap documents are not security vulnerabilities.
- [x] **Elimination of Brittle Constants & Anti-Pattern Refactoring**:
  - Removed `CONST_SCHEMA_FIX_HINT_TEMPLATES` from `src/devops_cli/config/constants.py` and `src/devops_cli/ai/schema_reflection.py`. Replaced manual template mapping with direct utilization of Pydantic v2's native, standard error messages (`error["msg"]`).
  - Removed ad-hoc blacklist `CONST_FORBIDDEN_SANDBOX_ENV_KEYS`. Relied on bubblewrap's native `--clearenv` isolation flag and explicit allowlist (`CONST_HOST_SANDBOX_DEFAULT_ENV`) for environment sanitization rather than arbitrary keyword filtering.
- [x] **Review Findings Reconciliation & Feedback Export**:
  - Reconciled findings in `/workspaces/devops-cli/.data/reviews/20260927-040516/findings.json` (invalidating hallucinations and marking remediations).
  - Exported feedback dataset via `devops review export-feedback --output .data/feedback_dataset.jsonl --status ALL`.
- [x] **Comprehensive Test Coverage & Architectural Invariant Gates**:
  - Added unit tests for safe check-runs parsing and payload retrieval in `tests/test_pr_check_runs.py`.
  - Updated `tests/test_schema_reflection.py` and `tests/test_host_sandbox.py` to verify native Pydantic error passthrough and host credential isolation.
  - Consolidated linear assertions into structural tuple equality checks.
  - 100% compliance across Gated CI validation suite (`uv run devops ci`).
