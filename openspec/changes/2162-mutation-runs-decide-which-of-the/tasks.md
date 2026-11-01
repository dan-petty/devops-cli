# Tasks

## 1. Run mutation testing and write the report

Reads: none. Changes: `openspec/changes/2162-mutation-review-scanner/mutation-report.md`.

- [ ] 1.1 A test that asserts the file openspec/changes/2162-mutation-review-scanner/mutation-report.md exists and contains a row for each of the 18 test files with columns for mutants killed (full suite) and mutants surviving (file excluded). This test fails because the file does not exist yet, and verify that `test -s openspec/changes/2162-mutation-review-scanner/mutation-report.md && grep -c 'mutant' openspec/changes/2162-mutation-review-scanner/mutation-report.md` fails on the base
- [ ] 1.2 For each of the 18 files, identify the source functions whose lines the file covers. Run `uv run devops ci mutate` on those functions. Run the test suite once with all tests and once with the file excluded via `--ignore=<file>`. Record the mutant IDs killed by the full suite and the mutant IDs that survive only when the file is excluded. Write the results to the report file as a table with columns: file, mutants killed (full suite), mutants surviving (file excluded), unique mutants, and verify that `test -s openspec/changes/2162-mutation-review-scanner/mutation-report.md && grep -c 'mutant' openspec/changes/2162-mutation-review-scanner/mutation-report.md` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Delete or merge files with no unique mutant

Reads: none. Changes: `tests/ai/review/test_cited_code.py`, `tests/commands/test_review.py`, `tests/commands/test_review_removed_options.py`, `tests/test_custom_personas.py`, `tests/test_review_advisory_backing.py`, `tests/test_review_deduplication.py`, `tests/test_review_defects_comments.py`, `tests/test_review_defenses_and_verification.py`, `tests/test_review_history.py`, `tests/test_review_location_paths.py`, `tests/test_review_loop_hardening.py`, `tests/test_review_regression_harness.py`, `tests/test_review_taxonomy_and_severity.py`, `tests/test_review_verification.py`, `tests/test_structural_positional_oracles.py`, `tests/test_security_kubelinter.py`, `tests/test_security_tflint.py`, `tests/security/test_sarif_fuzzing.py`.

- [ ] 2.1 A test that asserts each file in the mutation report with zero unique mutants no longer exists, or its distinct case appears in the covering file. This test fails because the redundant files still exist, and verify that `uv run pytest --cov=devops_cli --cov-report=term` fails on the base
- [ ] 2.2 Read the mutation report. For each file with zero unique mutants, delete the file. If a file has one distinct case that no other file asserts, move that case into the file that covers the same lines. Do not delete any file matching test_architectural_invariants, test_contract, or a security-guard test name. After deletion, run the full suite and confirm coverage is unchanged or higher, and verify that `uv run pytest --cov=devops_cli --cov-report=term` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Verify CI passes and mark tasks complete

Reads: none. Changes: `openspec/changes/2162-mutation-review-scanner/tasks.md`.

- [ ] 3.1 A test that asserts `uv run devops ci` exits with code 0 and the tasks.md file has all tasks marked complete. This test fails because tasks are not yet marked complete, and verify that `uv run devops ci` fails on the base
- [ ] 3.2 Run `uv run devops ci`. Confirm exit code 0. Confirm the Tests & Coverage job duration is no longer than before. Mark all tasks in the change folder as complete, and verify that `uv run devops ci` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
