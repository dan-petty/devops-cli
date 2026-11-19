# Tasks

## 1. Behavior: count a changed test that errors on base as proof

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`.

- [x] 1.1 Add tests to `tests/ci/test_fail_to_pass.py`: a replay whose only changed test file fails to collect on base exits 0 and names the file as the proof, a changed test that errors on setup satisfies the replay, an unchanged test that errors on base refuses the replay, a file that only gains a comment and fails to collect on base refuses the replay, and the dry run names the condition `a test that failed or errored on base is unchanged`.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 Add `is_file_changed` to `src/devops_cli/ci/changed_tests.py`. In `src/devops_cli/ci/fail_to_pass.py`, map a collection error to its changed test file in `_test_location`, read failures and errors in `_unchanged_failures`, replace `changed_failed_count` with `proof`, and print the proof line. Change the messages and the dry-run conditions to say "fails or errors".
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py tests/ci/test_changed_tests.py`

## 2. Documents

- [x] 2.1 State the rule in the module docstring of `src/devops_cli/ci/fail_to_pass.py`, in `docs/TESTING.md` and in "Fail-to-Pass Evidence" of `CONTRIBUTING.md`.
  - Verification: `$ uv run devops ci --check --only docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
