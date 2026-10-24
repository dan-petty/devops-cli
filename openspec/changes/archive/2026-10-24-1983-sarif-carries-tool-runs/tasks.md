# Tasks

## 1. The run of a tool holds the records of that tool

- [x] 1.1 Write failing tests: the run of a tool holds each record of that tool under `tool_runs`, the driver takes the version of the records when no result names one, a tool with records and no result gets no run, and the run of a scanner that ran holds its records beside its invocation. Each document validates against the vendored SARIF 2.1.0 schema (`uv run devops ci test tests/test_security_sarif.py`).
- [x] 1.2 Add `tool_runs` to `to_sarif` in `src/devops_cli/security/sarif.py`, and write the records and the driver version in `_run_for` (`uv run devops ci test tests/test_security_sarif.py`).
- [x] 1.3 Map each field of `ToolRun` to SARIF 2.1.0 in the module docstring of `src/devops_cli/security/tool_executor.py`, with the section that stops each name the record cannot fill (`uv run ruff check src/devops_cli/security/tool_executor.py`).

## 2. The review writes its records to `findings.sarif`

- [x] 2.1 Write a failing test: the SARIF document of a review holds the records of Gitleaks in the run of Gitleaks, Bandit with no result gets no run, and the document validates against the schema (`uv run devops ci test tests/test_review_tool_runs.py`).
- [x] 2.2 Pass `self.tool_executor.runs` to `to_sarif` in `_persist_session_artifacts` of `src/devops_cli/ai/review/pipeline.py` (`uv run devops ci test tests/test_review_tool_runs.py`).
- [x] 2.3 Name `findings.sarif` in the section "Tool Run Records" of `docs/SELF_IMPROVEMENT.md`, and sync the documentation (`uv run devops docs generate --sync-readme` and `uv run devops docs check`).

## Workflow follow-up

- The record of a run holds its exit code and the success of the run as its scanner decides it, and the SARIF export writes one invocation for each record with `executionSuccessful`, `exitCode` and a `commandLine` whose placeholders are in `run.redactionTokens`: moved to #2100.
- The record names the repository of the checkout, so the SARIF export writes `versionControlProvenance` for a commit that is not dirty: moved to #2101.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
