# Tasks

## 1. The executor fake that records as the direct executor

- [x] 1.1 Run the two cases of an incomplete record in `tests/test_tool_executor_contract.py` over `DirectToolExecutor` and over `ToolExecutorFake(require_commit=False, require_files=False)` (`uv run devops ci test tests/test_tool_executor_contract.py`).
- [x] 1.2 Give `require_commit` and `require_files` of `ToolExecutorFake` to `record_tool_run` (`uv run devops ci test tests/test_tool_executor_contract.py`).

## 2. scanner_fake over the executor fake

- [x] 2.1 Change the third case of `tests/test_scanner_contract.py`: the stand-ins on PATH, the answer of the fake through `DirectToolExecutor`, and git through the direct executor (`uv run devops ci test tests/test_scanner_contract.py`).
- [x] 2.2 Make `ScannerFake` a `ToolExecutorFake` with the recorded runs, the stand-ins in `bin_dir` and the `scanner_fake` fixture on `DirectToolExecutor.run`. Delete its `which` and `run` doubles of the standard library (`uv run devops ci test tests/test_scanner_contract.py tests/test_scanner_tool_executor.py tests/test_security_semgrep.py`).
- [x] 2.3 Add a case to `tests/test_scanner_contract.py`: the canary of each canary tool that the fake can answer gets the recorded canary answer. Pass a run in a canary working directory on to the `run` that the fixture replaced (`uv run devops ci test tests/test_scanner_contract.py tests/test_review_canary.py tests/test_review_tool_runs.py`).
- [x] 2.4 Script the answers of the agent scan tool tests with `scanner_fake.script` (`uv run devops ci test tests/test_builtin_tools.py tests/test_mcp.py tests/test_security_gitleaks.py`).
- [x] 2.5 Run every test file that uses `scanner_fake` (`uv run devops ci test tests/test_scanner_contract.py tests/test_gateway_review_stall.py tests/test_scanner_tool_executor.py tests/test_osv_scanner.py tests/test_review_project_conventions.py tests/test_review_security_tools.py tests/test_security_semgrep.py tests/test_review_group_analysis.py tests/test_builtin_tools.py tests/test_review_static_analyzers.py tests/ai/review/test_runner.py tests/test_tool_executor_contract.py tests/test_mcp.py tests/test_security_gitleaks.py`).

## 3. Documentation

- [x] 3.1 Describe the new fake in docs/TESTING.md and in the docstrings of `tests/support/fakes/openspec.py`, `tests/test_scanner_contract.py` and `tests/test_scanner_tool_executor.py` (`uv run devops docs check`).
- [x] 3.2 Check the change (`uv run devops openspec check`).

## Workflow follow-up

- The autouse fixture `scanners_installed` in `tests/test_scanner_tool_executor.py` still patches `shutil.which`; it moves to stand-ins on PATH: moved to #2116.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
