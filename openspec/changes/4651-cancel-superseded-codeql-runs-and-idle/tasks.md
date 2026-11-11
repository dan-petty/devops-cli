# Tasks

## 1. Workflows

Kind: workflows. Reads: `src/devops_cli/github/check_verdict.py`. Changes: `.github/workflows/codeql.yml`, `.github/workflows/fail-to-pass.yml`, `.github/workflows/cleanup-devcontainer.yml`, `tests/invariants/test_workflow_contracts.py`.

- [x] 1.1 Give `codeql.yml` a concurrency group that cancels a superseded pull request run and keeps each run of `main`, and give the `analyze` job `timeout-minutes: 15`
  - Verification: `$ uv run devops ci --only actionlint,zizmor`
- [x] 1.2 Skip the Fail-to-Pass job for an edit of the body alone, give that run a concurrency group of its own, and change the contract tests of the job condition and of the group to the new form
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.3 Remove the `pull_request` `closed` trigger of `cleanup-devcontainer.yml` and the script lines that only that trigger used
  - Verification: `$ ! git grep -n -F CLOSING_PR .github/workflows/cleanup-devcontainer.yml`

## 2. Documents

Kind: documents. Changes: `CONTRIBUTING.md`.

- [x] 2.1 Say in the fail-to-pass entry of `CONTRIBUTING.md` that an edit of the body alone does not start the check again
  - Verification: `$ uv run devops ci docs`
