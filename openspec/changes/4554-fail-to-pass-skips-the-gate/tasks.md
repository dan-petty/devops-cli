# Tasks

## 1. Gate replay (behavior)

- [x] 1.1 Write failing tests: a changed `k8s` check that fails on the base and passes on the head, a check that passes on both, a base failure of an unchanged module, a row that cannot run, a change of the case count, a named head, the report text, the dry-run plan, and a test-only fix that starts no gate row
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 List the changed gate check modules, run their rows on the base and head trees, compare the failed cases, and add the gate lines to the report and the plan
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`

## 2. Workflow trigger (behavior)

- [ ] 2.1 Write failing tests: the path filter starts the workflow for a module under `tests/gate/*_checks/`, and the comment names `tests/gate/*_checks/`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [ ] 2.2 Add `tests/gate/*_checks/**` to the path filter of `.github/workflows/fail-to-pass.yml` and correct its comment
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 3. Documents

- [ ] 3.1 Name the gate replay in CONTRIBUTING.md, the help of the command, the generated README and CLI reference, and the Purpose of the `ci-fail-to-pass` spec
  - Verification: `uv run devops docs generate --check`
