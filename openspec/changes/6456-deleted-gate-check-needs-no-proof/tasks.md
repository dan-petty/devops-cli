# Tasks

## 1. Behavior: a gate check module that only loses checks needs no proof

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `tests/gate/runner.py`. Changes: `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_changed_tests.py`, `tests/ci/test_fail_to_pass.py`.

- [x] 1.1 Add tests that fail on the base. In `tests/ci/test_changed_tests.py`: a module that loses a `check_*`, a constant that only that check read and the text of a comment gives the name `<module>.<check>`; a module gives no name when another check changes, when a check is added, when a helper changes, when a kept statement moves, when a left-out statement binds a name that the head uses, when a left-out statement is a top-level call, when the base or the head is missing, and when a side does not parse. In `tests/ci/test_fail_to_pass.py`: a fix that changes no source code and only deletes a check exits 0, starts no gate row and names the check; a fix that deletes one check and changes another runs the gate row; a fix that deletes a check and adds one runs the gate row; a fix that also changes a `.py` file under `src/` still needs a proof; a fix with one module that only loses a check and one changed module runs the row and names only the changed module.
  - Verification: `$ uv run devops ci test tests/ci/test_changed_tests.py tests/ci/test_fail_to_pass.py`
- [x] 1.2 Add the function that gives the deleted checks of a module to `src/devops_cli/ci/changed_tests.py`. In `src/devops_cli/ci/fail_to_pass.py`, read the base and the head of each changed check module in `changed_tests`, add `ChangedTests.deleted_checks` and `FailToPassReport.deleted_gate_checks`, keep the modules that only lose checks out of `gate_checks`, and print the new message `fail_to_pass_deleted_checks` of `src/devops_cli/lang/en/messages.py`.
  - Verification: `$ uv run devops ci test tests/ci/test_changed_tests.py tests/ci/test_fail_to_pass.py`

## 2. Documents

Kind: other.

- [x] 2.1 State the rule in the module docstrings of `src/devops_cli/ci/fail_to_pass.py` and `src/devops_cli/ci/changed_tests.py`, in "Fail-to-Pass Evidence" of `CONTRIBUTING.md`, and in `docs/TESTING.md` (the list of changes that get no test, and the Fail-to-Pass rule of #6080).
  - Verification: `$ uv run devops ci docs`
