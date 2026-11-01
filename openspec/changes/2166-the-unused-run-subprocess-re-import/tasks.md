# Tasks

## 1. Remove unused re-import in security/ruff.py

Reads: none. Changes: `src/devops_cli/security/ruff.py`.

- [ ] 1.1 Write a test that runs uv run ruff check --select F401 src/devops_cli/security/ruff.py and asserts exit code 0 with no findings, and verify that `uv run ruff check --select F401 src/devops_cli/security/ruff.py` fails on the base
- [ ] 1.2 Remove the run_subprocess import line (line 23) from src/devops_cli/security/ruff.py. The module does not use the name and no test patches it, and verify that `uv run ruff check --select F401 src/devops_cli/security/ruff.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Remove _prepare_cmd alias and update tests

Reads: none. Changes: `src/devops_cli/core/process.py`, `tests/support/fakes/process.py`, `tests/core/test_process.py`.

- [ ] 2.1 Write a test that asserts rg -n '_prepare_cmd' src tests prints nothing, and verify that `uv run devops ci test tests/core/test_process.py` fails on the base
- [ ] 2.2 Remove the line _prepare_cmd = prepare_tool_cmd from src/devops_cli/core/process.py (line 482). In tests/support/fakes/process.py, change the import of _prepare_cmd to prepare_tool_cmd. In tests/core/test_process.py, change all references from _prepare_cmd to prepare_tool_cmd (lines 583, 585, 592, 598), and verify that `uv run devops ci test tests/core/test_process.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Add F401 re-import ceiling CI row

Reads: none. Changes: `src/devops_cli/commands/ci.py`.

- [ ] 3.1 Write a test that adds a # noqa: F401 import to a temporary file in src/, runs the new CI row, and asserts it fails. Remove the import and assert the row passes at the ceiling of 14, and verify that `uv run devops ci` fails on the base
- [ ] 3.2 Add a new row to devops ci that runs ruff check --select F401 --ignore-noqa src, counts the findings, and fails with a message naming the new sites when the count exceeds 14. The row runs on the stock runner with no install step, and verify that `uv run devops ci` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
