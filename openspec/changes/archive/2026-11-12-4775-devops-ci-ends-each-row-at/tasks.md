# Tasks

## 1. The gate stops its rows

- [x] 1.1 Write the test: a SIGTERM to `devops ci --check --only format` stops the group of the row, names the row and exits 130
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`
- [x] 1.2 Run the gate through `_until_stopped`, and print a stopped line for each row that a stop signal cancels
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`

## 2. The pre-push limits

- [x] 2.1 Write the structural test and its negative control: a hook with no limit and a total of 121 s are refused
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 2.2 Put `timeout 40` and `timeout 30` on the two `devops ci` hooks, list `timeout` in the runner tools, and let the hook invariants read past the limit
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/invariants/test_runner_hooks.py tests/roadmap/test_roadmap_runner_tools.py tests/commands/test_instruction_generator.py`

## 3. Documents

- [x] 3.1 Say in `docs/SDLC.md` that the pre-push check hooks run under `timeout` and that the gate stops and names its rows
  - Verification: `$ uv run devops ci --check --only docs,openspec`
