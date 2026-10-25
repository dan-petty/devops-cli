# Tasks

## 1. Write the failing test

- [x] 1.1 Add `test_rejected_dependency_advisory_is_omitted_and_counted` to `tests/test_review_admission.py` verifying that a dependency advisory with an invalid line number is omitted from findings and counted in `rejection_counts`.
- [x] 1.2 Verify that the test fails on current code (`uv run devops ci test tests/test_review_admission.py -k test_rejected_dependency_advisory_is_omitted_and_counted`).

## 2. Implement the fix

- [x] 2.1 Update `_admit_advisory_finding` and `_audit_dep_vulnerability` in `src/devops_cli/ai/review/pipeline.py` to pass `rejection_counts`, sync with the active profiler, and return `None` when `frozen is None`.
- [x] 2.2 Update `_write_review_profile` in `src/devops_cli/ai/review/runner.py` to sync `orchestrator.rejection_counts` to the profiler.
- [x] 2.3 Verify that the new test passes (`uv run devops ci test tests/test_review_admission.py`).

## 3. Quality checks and archive

- [x] 3.1 Run static checks and verification (`uv run devops ci`).
- [x] 3.2 Archive the OpenSpec change with `uv run devops openspec archive 1302-rejected-advisories-omitted`.
