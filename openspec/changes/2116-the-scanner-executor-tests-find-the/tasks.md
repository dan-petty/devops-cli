# Tasks

## 1. Find the scanners through stand-ins on PATH

Reads: `tests/security/test_scanner_tool_executor.py`, `tests/support/fakes/scanners.py` (lines 84 to 88 and 206 to 213). Changes: `tests/security/test_scanner_tool_executor.py`.

The change keeps the behavior of the tests and only changes a fixture, so no new test is written. Two repeatable checks verify it: a `git grep` that must print nothing, and the existing tests of the file.

- [ ] 1.1 Verify the base. `git grep -nE 'shutil|subprocess' -- tests/security/test_scanner_tool_executor.py` prints lines 12, 79 and 85, and `uv run devops ci test tests/security/test_scanner_tool_executor.py` passes with 54 tests
- [ ] 1.2 Rewrite the fixture `scanners_installed` in `tests/security/test_scanner_tool_executor.py`: it takes `monkeypatch` and `tmp_path`, makes `tmp_path / "scanner-bin"`, writes an executable stand-in file (`#!/bin/sh`, mode `0o755`) named after each tool of `_REVIEW_SCANS`, and sets `PATH` with `monkeypatch.setenv` to that directory followed by the old `PATH`. Drop the patch of `shutil.which`. Replace `import shutil` with `import os`, and drop `from typing import Any`
- [ ] 1.3 Verify that `git grep -nE 'shutil|subprocess' -- tests/security/test_scanner_tool_executor.py` prints nothing, and that `uv run devops ci test tests/security/test_scanner_tool_executor.py` passes with the same 54 tests
- [ ] 1.4 Verify that `uv run devops ci lint --check` and `uv run devops ci format --check` pass

## Workflow follow-up

- Pending a person: file the follow-up issue for the second `scanners_installed` fixture, in `tests/security/test_review_tool_runs.py` (line 75). It patches `shutil.which` with the same body. Issue #2116 names only `tests/security/test_scanner_tool_executor.py`.
