# Task 718: Remediate Review Findings 20260928-201857 and Enhance Feedback Loop

**Issue**: [#718](https://github.com/dan-petty/devops-cli/issues/718)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/security`, `type/refactor`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Remediate valid findings and systemic defects identified during review session `/workspaces/devops-cli/.data/reviews/20260928-201857`, increase review retries and incremental backoff for transient 4xx and 5xx HTTP gateway errors (such as Cloudflare 524 timeouts), eliminate Python 3.12+ invalid escape sequence `SyntaxWarning: "\w"` warnings across all AST parsing call sites and sandbox criteria execution, disarm tautological criteria commands from falsely auto-promoting findings, broaden anti-hallucination catalogs, harden subsystems against path traversal and socket leaks, update review and persona prompts, export review feedback dataset, and document calibration in self-improvement records.

### Key Deliverables Completed:
- [x] **HTTP 4xx/5xx Treatment & Review Retry Backoff**:
  - Increased `DEFAULT_REVIEW_RETRY_ATTEMPTS` to 6 (from 3) in `src/devops_cli/config/defaults.py`.
  - Tuned `DEFAULT_REVIEW_RETRY_MIN_BACKOFF` to 2.0s and `DEFAULT_REVIEW_RETRY_MAX_BACKOFF` to 60.0s.
  - Replaced hardcoded `retries=3` in `ReviewPipelineOrchestrator` agent creation with `DEFAULT_REVIEW_RETRY_ATTEMPTS`.
  - Refined `_clean_http_error_body` in `src/devops_cli/ai/client/base.py` to strip multi-line HTML error bodies into concise HTTP error summaries.
- [x] **Invalid Regex Escape Warnings Prevention (`SyntaxWarning: "\w"`)**:
  - Added `("PYTHONWARNINGS", "ignore::SyntaxWarning")` to `CONST_HOST_SANDBOX_DEFAULT_ENV` in `src/devops_cli/config/constants.py`.
  - Wrapped `ast.parse` in `warnings.catch_warnings()` suppressing `SyntaxWarning` across `src/devops_cli/ai/analyze/outlines.py`, `src/devops_cli/ai/analyze/symbols.py`, `src/devops_cli/ai/context_packer.py`, `src/devops_cli/ai/rag/chunker.py`, `src/devops_cli/ai/rag/metadata.py`, `src/devops_cli/ai/ast_stream.py`, `src/devops_cli/ai/ast/fallback.py`, `src/devops_cli/security/aibom.py`, and `src/devops_cli/security/reference_extractor.py`.
  - Updated review prompts (`code_review_prompt.md`, `review.md`, `review_output_instruction.md`, `verify_finding_system.md`) and persona prompt templates to explicitly instruct models to use raw strings (`r'...'`) and double backslashes (`\\\\`) in verification criteria and code blocks.
- [x] **Tautological Criteria Auto-Promotion Prevention**:
  - Hardened `_is_tautological_verification_command` in `src/devops_cli/ai/review/review_environment.py` to identify criteria commands that execute no assertions or failure conditions (e.g. pure module imports with prints), preventing auto-promotion of findings to verified status.
- [x] **Subsystem Hardening & Finding Remediation**:
  - `src/devops_cli/commands/mcp.py`: Removed lazy `__getattr__` and `_LAZY_OBJECT_MAPPING` in favor of direct symbol imports.
  - `src/devops_cli/commands/repos.py`: Replaced lazy `__getattr__` and `_LAZY_OBJECT_MAPPING` with direct symbol imports; added `validate_no_path_traversal` and `is_relative_to` checks on `repo.name` in `clone-org`.
  - `src/devops_cli/k8s/service.py`: Replaced static `.tmp` file in `switch_context` with secure `tempfile.NamedTemporaryFile(delete=False, dir=parent)` with `0o600` permissions and atomic replacement in `try...finally`.
  - `src/devops_cli/ai/rag/library_store.py`: Fixed `ensure_collection_exists` to return `True` when collection already exists.
  - `src/devops_cli/watchers/live_resource.py`: Guarded against division-by-zero and CPU pegging in refresh rate calculation with `min(30, max(1, int(1.0 / max(0.01, self.interval_seconds))))`.
  - `src/devops_cli/http/broker.py`: Ensured `close()` and `aclose()` always reset `_sync_client = None` and `_async_client = None`.
  - `src/devops_cli/http/pool.py`: Added explicit `aclose_shared_clients()` helper and safe socket cleanup.
  - `src/devops_cli/core/command_decorator.py`: Standardized `DevOpsCLIError` handler to consistently record `error_type`.
  - `src/devops_cli/k8s/informer.py`: Handled both dictionary objects and K8s API model objects in `_normalize_event`.
  - `src/devops_cli/argo/rollouts.py`: Narrowed exception handling in `_fetch_metric_value` to `(httpx2.HTTPError, ValueError, TypeError, KeyError)`.
  - `src/devops_cli/ai/instruction_generator.py`: Narrowed exception handling in `parse_project_metadata` to `(tomllib.TOMLDecodeError, OSError)`.
  - `src/devops_cli/commands/grafana.py`: Added `validate_no_path_traversal` to `dashboards_export`.
  - `src/devops_cli/ai/review/exporter.py`: Ensured root equality and relative validation consistency in output path checks.
  - `src/devops_cli/argo/gitops.py`: Added path traversal validation in `inspect_git_manifest_drift`.
  - `src/devops_cli/telemetry/memory_profiler.py`: Wrapped `_exercise_http_pool` cleanup in `try...finally`; validated custom module and function identifiers with strict regex before import.
  - `src/devops_cli/k8s/security_stream.py`: Masked secrets in `stderr_msg`.
  - `src/devops_cli/models/argo.py`: Safely parsed integer `current_step` in `from_manifest()`.
  - `src/devops_cli/ai/__init__.py`: Narrowed `ModuleNotFoundError` handling in `__getattr__` to the requested module name.
- [x] **Anti-Hallucination Catalog & Pre-Verification Expansion**:
  - `src/devops_cli/ai/review/common_hallucinations.py`: Updated `_verify_secret_scanning_ground_truth` so identifier lookups (`getattr(..., "password", ...)` or `.get("password")`) are not mistaken for secret string literals.
  - `src/devops_cli/ai/review/common_hallucinations.json`:
    - Updated `HALLUCINATION-PEP758-EXCEPT` signature patterns to match `catches <A>, <B> but this syntax is invalid`.
    - Added `HALLUCINATION-GRAPHQL-JSON-DUMPS` (GraphQL query interpolation using `json.dumps()` is safe escaping, not injection).
    - Added `HALLUCINATION-EXAMPLE-COM-WEBHOOK` (RFC 2606 `example.com` webhook placeholder is compliant dummy URL).
    - Added `HALLUCINATION-PROMETHEUS-TELEMETRY-METRIC` (standard telemetry enablement boolean gauge in `/metrics` is not an info leak).
- [x] **Calibration Records & Knowledge Documentation**:
  - Added Calibration Record for Session `20260928-201857` to `docs/SELF_IMPROVEMENT.md`.
- [x] **Feedback Dataset Export**:
  - Exported review session feedback dataset via `uv run devops review export-feedback`.
- [x] **Unit & Regression Testing with Structural Tuple Equality**:
  - Added tests for retry configuration, regex warning suppression, tautological criteria detection, and security defenses.
  - Consolidated linear test assertions into structural tuple equality checks (`assert (a, b) == (x, y)`).
  - 100% pass across all 10 quality gates in `uv run devops ci`.
