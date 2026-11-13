# Tasks

## 1. The gate row imports the source of its tree

Kind: behavior. Reads: `tests/gate/runner.py`, `src/devops_cli/core/process.py`. Changes: `tests/ci/test_fail_to_pass.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/config/constants.py`.

- [x] 1.1 Write the failing test: with an interpreter that finds `devops_cli` in the head `src/`, a fix that adds `k8s/b.yaml`, lists it in `src/` and changes a check module is satisfied, and the check module that the fix does not change passes on base
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 Add `CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT`, which puts the `src/` of the working folder first on `sys.path`, and use it in `gate_row_argv`
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.3 Replay the head of pull request #5357 with the fix: the k8s gate row fails only the changed case on base
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main --head <head of #5357>`

## 2. Documents

Kind: other. Changes: `CONTRIBUTING.md`.

- [x] 2.1 Say in the Fail-to-Pass Evidence item of CONTRIBUTING.md that each gate row run imports the code under `src/` of its own tree
  - Verification: `$ uv run devops ci docs`
