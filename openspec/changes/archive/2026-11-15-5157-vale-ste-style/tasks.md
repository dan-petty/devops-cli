# Tasks

## 1. Check the prose with Vale

Reads: `src/devops_cli/ai/tasks/style_ste100.md`, `src/devops_cli/tools_lock/tools.lock`.

Changes: `.vale.ini`, `.vale/styles/STE/*.yml`, `src/devops_cli/tools_lock/tools.lock`, `tests/docs/test_vale_ste.py`, `tests/support/vale.py`, `CONTRIBUTING.md`.

- [x] 1.1 Add the four rules and the pin, and install the tool with `devops install-tools --tool vale`.
  - Verification: `$ vale docs/TESTING.md`
- [x] 1.2 Write the fixture tests, and run them with the installed tool on PATH.
  - Verification: `$ uv run devops ci test tests/docs/test_vale_ste.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
