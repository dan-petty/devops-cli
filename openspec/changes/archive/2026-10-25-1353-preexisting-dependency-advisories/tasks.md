# Tasks

## 1. Write the failing test

- [x] 1.1 Add `test_base_revision_dependency_advisory_is_preexisting` to `tests/test_review_admission.py` verifying that an advisory the base revision already has is listed under Pre-existing, and a new pin's advisory under Introduced.
- [x] 1.2 Verify that the test fails on current code (`uv run devops ci test tests/test_review_admission.py -k test_base_revision_dependency_advisory_is_preexisting`).

## 2. Implement the fix

- [x] 2.1 Implement base revision pin extraction and base advisory admission in `src/devops_cli/ai/review/pipeline.py` within `_audit_file_dependencies`.
- [x] 2.2 Verify that the test passes (`uv run devops ci test tests/test_review_admission.py -k test_base_revision_dependency_advisory_is_preexisting`).
- [x] 2.3 Run full admission tests to verify no regressions (`uv run devops ci test tests/test_review_admission.py`).

## 3. Quality checks and archive

- [x] 3.1 Run static checks and verification (`uv run devops ci`).
- [x] 3.2 Archive the OpenSpec change with `uv run devops openspec archive 1353-preexisting-dependency-advisories`.
