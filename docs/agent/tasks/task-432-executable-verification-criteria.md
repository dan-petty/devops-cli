# Task 432: Executable Verification Criteria

**Issue**: [#432](https://github.com/dan-petty/devops-cli/issues/432)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

This was scheduled on the premise that personas emit `verification_criteria` as deterministic shell assertions (`git check-ignore -v <path>`, `git ls-files`, `grep -n <symbol> <file>`) which nothing executes. The recorded data demonstrated that across 3,167 criteria in 59 review sessions, only 3 began with real commands, while 3,069 were unexecutable prose descriptions.

This deliverable transforms verification criteria into executable and verified assertions:
1. Constrained persona prompts (`review.md`, `review_output_instruction.md`, `compose.md`, `prompt.md`) and the finding schema (`Finding.verification_criteria`, `Finding.invalidation_criteria`) so a criterion is either an allowlisted read-only command (`git grep`, `git ls-files`, `python -c`, `ruff check`, `pytest`, `jq`) with `executable: true` or explicitly marked unexecutable prose with `executable: false`.
2. Implemented the command allowlist validator and bounded subprocess execution sandbox in `devops_cli.ai.review.review_environment` with POSIX process group isolation (`start_new_session=True`), defensive signal termination, and bounded output truncation.
3. Attached `CriterionExecutionResult` outputs directly to `Finding.criteria_execution_results`.
4. Derived objective tool-grounded `confidence_score` and `status` from sandbox execution pass/fail outcomes, while preserving absent confidence scores when only unexecutable prose criteria exist.

#### Deliverables Completed:
- [x] Constrain persona prompts and finding schema so criteria are either commands from a closed read-only allowlist or explicitly marked unexecutable.
- [x] Define structured `VerificationCriterion` and `CriterionExecutionResult` models in `devops_cli.ai.review_schema`.
- [x] Implement closed read-only command allowlist (`CONST_ALLOWED_CRITERIA_BINARIES`, `CONST_ALLOWED_GIT_SUBCOMMANDS`, `CONST_DISALLOWED_SHELL_TOKENS`, `CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES`).
- [x] Implement bounded subprocess sandbox in `devops_cli.ai.review.review_environment` with POSIX process group isolation, timeout bounding, and output truncation.
- [x] Attach captured execution results to findings (`criteria_execution_results`).
- [x] Derive confidence score and status from actual execution outcomes ($K / N$ pass rate, invalidation refutation), without manufacturing scores from unexecuted prose.
- [x] Unit and integration test coverage with structural tuple equality assertions (`tests/test_executable_criteria.py`).
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ project-wide.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Evidence

- `tests/test_executable_criteria.py`: 17 passed in 17s.
- `tests/test_review_verification.py`: 84 passed in 17s.
- `tests/test_review_pipeline.py`: 28 passed in 19s.
- `tests/test_personas.py`: 4 passed in 7s.
- `tests/test_architectural_invariants.py`: 13 passed in 13s.
- `devops scan complexity`: 100% compliance across `review_environment.py`, `review_schema.py`, and `test_executable_criteria.py`.
