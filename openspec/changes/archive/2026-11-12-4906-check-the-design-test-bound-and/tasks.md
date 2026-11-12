# Tasks

## 1. Workflow: the bound of one design test

- [x] 1.1 Make the contract test of the job `design-tokens` assert the command `uv run pytest tests/design -n 0 --timeout 60` and a test bound that is more than 0 and shorter than the step limit.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Give the step "Run the Design Tests" the option `--timeout 60`, and say in the comment of the job that the test bound is shorter than the step.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Tests: the hex of each source color

- [x] 2.1 Add a test to `tests/design/test_tokens.py` that compares the `hex` of each of the 66 source colors with the hex of its `components`.
  - Verification: `$ uv run devops ci test tests/design/test_tokens.py`

## 3. Documents

- [x] 3.1 In `docs/DESIGN.md`, tell a person in "Change a token" to give a color the same value in `components` and in `hex`, and list the new check in "Checks".
  - Verification: `$ uv run devops ci docs`
