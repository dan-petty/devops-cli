# Task 205: Remediate Review Findings & Enhance Self-Improvement Loop (Session 20260914-030848)

**Issue**: [#205](https://github.com/dan-petty/devops-cli/issues/205)
**Status**: Done
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/review`

---

## 1. Description & Architectural Objectives

Remediate verified security, path containment, error handling, and formatting findings from automated multi-persona review session `20260914-030848`, calibrate deterministic pre-verification and review system prompts to disarm non-existent file hallucinations, and enhance the self-improvement feedback loop.

### Key Deliverables
1. **Subprocess Environment Isolation & Telemetry Command Sanitization**:
   - In `src/devops_cli/core/process_pipeline.py`, replace ambient `dict(os.environ)` with `build_subprocess_env(env)` to prevent leaking ambient secrets and tokens to child processes.
   - Sanitize command strings in telemetry spans using `_sanitize_command_for_telemetry`.
2. **Vault Path Validation Error Handling**:
   - In `src/devops_cli/commands/vault.py`, catch `(ValueError, VaultConfigurationError)` in `vault_get`, `vault_set`, and `vault_sync` to emit clean error output without tracebacks.
3. **SSRF & Internal Hostname Telemetry Sanitization**:
   - In `src/devops_cli/exceptions/security.py`, sanitize `target_url` in `SSRFBlockedError.details` using `safe_url[:256]`.
   - In `src/devops_cli/security/sanitizer.py`, mask internal hostnames (`.local`, `.lan`, `.internal`, `.home`, `.corp`) as `<internal-host>` in `sanitize_telemetry_endpoint`.
4. **Deterministic Pre-Verification & Path Containment Hardening**:
   - In `src/devops_cli/ai/review/verification.py`, enforce repo root containment in `_resolve_target_file`.
   - In `_deterministic_pre_verification`, immediately invalidate findings targeting non-existent files (`status="INVALIDATED"`, `invalidation_reason="Target file does not exist in repository"`).
   - In `src/devops_cli/ai/rag/library_store.py`, validate that `local_contracts_dir / f"{package}.json"` remains contained within `local_contracts_dir`.
   - In `src/devops_cli/ai/harness/repo_context.py`, validate containment of `target_dir` within `workspace_dir`.
   - In `src/devops_cli/github/milestones.py`, reject absolute roadmap paths and enforce repository containment.
5. **Robustness, Output Formatting & Serialization Safety**:
   - In `src/devops_cli/github/pr_threads.py`, support string/non-numeric thread and comment identifiers in `threads_map` indexing.
   - In `src/devops_cli/output/file_writer.py`, use `yaml.safe_dump`.
   - In `src/devops_cli/output/formatters/scalars.py`, escape code text in `format_code_span` using `rich.markup.escape`.
   - In `src/devops_cli/sandbox/probe.py`, `src/devops_cli/telemetry/waterfall.py`, and `src/devops_cli/valkey/rate_limiter.py`, parenthesize multi-exception clauses (`except (ErrA, ErrB):`).
6. **Review System Prompts & Anti-Hallucination Memory Calibration**:
   - Register `HALLUCINATION-NONEXISTENT-FILE` and `HALLUCINATION-EXISTING-GUARD-OVERLOOKED` in `src/devops_cli/ai/review/common_hallucinations.json`.
   - Update `src/devops_cli/ai/tasks/verify_finding_system.md` and `src/devops_cli/ai/tasks/review.md` with explicit falsification rules.
   - Update `docs/SELF_IMPROVEMENT.md` with session `20260914-030848` analysis, root causes, remediations, and lessons learned.
   - Export review feedback dataset via `devops review export-feedback`.

---

## 2. Verification & Acceptance Criteria

- [ ] All unit tests authored in canonical submodule test files pass 100%.
- [ ] Non-existent file hallucinations are deterministically invalidated.
- [ ] Architectural invariants satisfied (cyclomatic complexity $\le 10$, nesting depth $\le 5$).
- [ ] All 10 `devops ci` quality gates pass cleanly.
- [ ] `feedback_dataset.jsonl` updated via `devops review export-feedback`.
