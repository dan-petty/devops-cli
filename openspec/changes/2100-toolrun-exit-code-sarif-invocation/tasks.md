# Tasks

## 1. The record of a run holds how the run ended

- [x] 1.1 Write failing tests: a settled record holds the exit code and the success, and no exit code after a timeout or a signal. `RecordingToolExecutor` keeps the settled record in the place of the run and refuses a second settle. A scan of Gitleaks settles a run that found something as succeeded, and a run with output that is not JSON or that timed out as failed. mypy settles exit code 2 as failed. The executor contract holds the settle of each executor (`uv run devops ci test tests/test_review_tool_runs.py tests/test_tool_executor_contract.py`).
- [x] 1.2 Add `ToolRun.exit_code`, `ToolRun.success`, `ToolResult.settled` and `ToolExecutor.settle` with the settle of each executor in `src/devops_cli/security/tool_executor.py` and `tests/support/fakes/tool_executor.py`. Settle each run in `src/devops_cli/security/base.py`, `src/devops_cli/security/sbom.py`, `src/devops_cli/security/mypy.py` and `src/devops_cli/review/canary.py`. Move the golangci-lint test from a stand-in for `_run_tool` to the executor fake (`uv run devops ci test tests/test_review_tool_runs.py tests/test_tool_executor_contract.py tests/test_golangci_lint_scanner.py`).
- [x] 1.3 Add the columns `Exit code` and `Succeeded` to the Tool Runs table in `src/devops_cli/ai/review/tool_runs.py` (`uv run devops ci test tests/test_review_tool_runs.py`).

## 2. The SARIF run of a tool holds an invocation for each settled record

- [x] 2.1 Write failing tests: one invocation for each settled record with `executionSuccessful`, `exitCode` and `commandLine`; no `exitCode` after a timeout; no invocation for a record that is not settled; the placeholders of the command lines in `redactionTokens`; a run with empty results for a clean tool with no result, and with no results for a failed one. Each document validates against the vendored schema (`uv run devops ci test tests/security/test_sarif_emission.py tests/test_review_tool_runs.py`).
- [x] 2.2 Write the invocations, the redaction tokens and the run of each tool that has a record in `src/devops_cli/security/sarif.py` (`uv run devops ci test tests/security/test_sarif_emission.py tests/test_review_tool_runs.py`).
- [x] 2.3 Tell the new fields and the SARIF names in the module docstring of `src/devops_cli/security/tool_executor.py`, in `docs/SELF_IMPROVEMENT.md` and in `docs/TESTING.md`, and sync the documentation (`uv run devops docs generate --sync-readme` and `uv run devops docs check`).

## Workflow follow-up

- The record names the repository of the checkout, so the SARIF export writes `versionControlProvenance` for a commit that is not dirty: #2101.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
