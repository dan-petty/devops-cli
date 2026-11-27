# Tasks

## 1. Require the checks of the repository file

Kind: behavior.

Reads: `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/baseline.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/support/github_repository.py`.

Changes: `src/devops_cli/github/onboard/baseline.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/routes.py`, `tests/github/onboard/test_onboard_rows.py`.

- [x] 1.1 Write the tests of the plan, of the confirmed run, of a baseline ruleset with no required checks rule and of a file that cannot be read, and watch them fail.
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py`
- [x] 1.2 Read the `github/repository.yaml` of the default branch in row 10, check it against the schema, and merge its required checks rule into the ruleset.
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py`

## 2. Documents

Kind: documents.

- [x] 2.1 Name the repository file in row 10 of `docs/repos/onboard.md`, and add a Status History line to ADR 0035.
  - Verification: `$ uv run devops ci docs`
