# Proposal

## Why

Issue #2100: the SARIF document of a review, `findings.sarif`, holds each `ToolRun` record in the property bag of the run of its tool (#1983). It writes no `invocations`. SARIF 2.1.0 says that an invocation SHALL hold `executionSuccessful` (section 3.20.14), and the exit code alone does not tell if a tool succeeded. A `ToolRun` holds neither the exit code nor the success of its run. So the document cannot say how each run of a tool ended.

## What Changes

- `ToolRun` (`src/devops_cli/security/tool_executor.py`) gets `exit_code` and `success`. The record that an executor builds before the tool starts holds neither. `ToolResult.settled(success=...)` gives the record of how the run ended. Its exit code comes from the result, and it is empty for a run that ended on a signal or that ran out of time (section 3.20.9).
- `ToolExecutor` gets `settle(result, success=...)`. The code that runs a tool decides if the run succeeded, from the exit code and the output together, and gives the decision to the executor. `RecordingToolExecutor` puts the settled record in place of the record of the run. The direct executor, the sandbox executor and `ToolExecutorFake` keep no records, so they do nothing.
- Each caller of an executor settles its runs: the scanner base (`security/base.py`), the SBOM of Trivy (`security/sbom.py`), mypy (`security/mypy.py`) and the tool canary (`review/canary.py`). A scan succeeded when its outcome is `ran` or `coverage_gap`.
- `to_sarif` (`src/devops_cli/security/sarif.py`) writes one invocation for each settled record of a tool, with `executionSuccessful`, `exitCode` when the record holds one, and `commandLine`. The placeholders `{targets}`, `{config}` and `{ruleset}` that the command lines hold go in `run.redactionTokens` (sections 3.5.2, 3.14.28).
- Each tool that has a record gets a run in the document of a review. The run has an empty `results` array when the tool gave no result and every record of the tool succeeded. It has no `results` when a record did not succeed (section 3.14.23).
- The Tool Runs table of `review.md` shows the exit code and the success of each record.
- The module docstrings, `docs/SELF_IMPROVEMENT.md` and `docs/TESTING.md` tell the new names.

The SARIF document of a review and `review.md` are output that a consumer reads, so the change carries spec deltas for `sarif-export` and `review-tool-runs`.

This change fits in one pull request. It does not add the repository of the checkout or `versionControlProvenance`, which #2101 holds.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sarif-export`: the run of a review tool holds an invocation for each settled record and the redaction tokens of its command lines. Each tool that has a record has a run.
- `review-tool-runs`: the record of a run holds its exit code and its success, as the code that ran the tool decides it.

## Impact

- `src/devops_cli/security/tool_executor.py`: `ToolRun.exit_code`, `ToolRun.success`, `ToolResult.settled`, `ToolExecutor.settle` and the settle of each executor.
- `src/devops_cli/security/base.py`, `src/devops_cli/security/sbom.py`, `src/devops_cli/security/mypy.py`, `src/devops_cli/review/canary.py`: each caller settles its runs.
- `src/devops_cli/security/sarif.py`: invocations, redaction tokens, and a run for each tool that has a record.
- `src/devops_cli/ai/review/tool_runs.py`: two columns in the Tool Runs table.
- `tests/support/fakes/tool_executor.py`: `ToolExecutorFake.settle`.
- `docs/SELF_IMPROVEMENT.md`, `docs/TESTING.md`.
- Tests in `tests/security/test_sarif_emission.py`, `tests/test_review_tool_runs.py`, `tests/test_tool_executor_contract.py` and `tests/test_golangci_lint_scanner.py`.

## Feasibility

I confirmed the premise against the real system at origin/main a0165a16:

- OASIS SARIF 2.1.0 Errata 01 (`sarif-v2.1.0-errata01-os-complete.html` from docs.oasis-open.org), read on 2026-10-29:
  - Section 3.20.14: "An invocation object SHALL contain a property named executionSuccessful whose value is a Boolean that is true if the engineering system that started the process knows that the analysis tool succeeded, and false if the engineering system knows that the tool failed." Its note: "not all programs exit with an exit code of 0 on success and non-0 on failure."
  - Section 3.20.9: "If the SARIF producer process exited due to a signal, the exitCode property SHALL be absent."
  - Section 3.20.2: `commandLine` "is redactable".
  - Section 3.5.2: a producer that redacts "SHALL replace the sensitive information with a string whose value is an element of theRun.redactionTokens".
  - Section 3.14.23: "If the tool did not detect any results, results SHALL be an empty array." If the tool failed to begin its analysis, `results` "MAY be present, and if present SHALL be null". If it is absent, it defaults to null.
- The vendored schema `tests/fixtures/sarif-schema-2.1.0.json` requires `executionSuccessful` in an invocation, types `exitCode` as an integer, and types `results` as an array, so a document leaves `results` out rather than write null.
- `ToolRun` in `src/devops_cli/security/tool_executor.py` has no exit code field. `record_tool_run` builds it before the tool starts, and `ToolResult` holds the exit code.
- `_handle_json_output` and `_handle_non_json_output` in `src/devops_cli/security/base.py` decide the outcome of a scan from the exit code and the parsed output together.
- `ToolExecutor.run` has three callers in `src/`: `BaseSecurityScanner._run_tool`, `run_mypy_scan` and `run_tool_canary`. The review wraps its executor in a `RecordingToolExecutor`. It runs its canaries on the executor that it wraps, so the review keeps no record of a canary.
- CI uploads only `.data/scan.sarif` of `devops scan report` to code scanning (`.github/workflows/ci.yml`). That document comes from scanner outcomes and holds no records. So this change sends no new run to code scanning.
- #1982, which the issue names as its order, is closed. `tests/support/fakes/tool_executor.py` builds each record with `record_tool_run`.

## Existing Tool Considered

- `sarif-om` has had no release since 1.0.4 on 2019-10-05, and it is not maintained. `sarif-pydantic` 0.6.2 is a project of one author before 1.0, with no license in its package metadata. The #1983 change recorded both.
- Neither library decides which run succeeded: the code that ran the tool decides that. The emitter in `src/devops_cli/security/sarif.py` already builds each run. `shlex.quote` from the standard library quotes each argument of a command line. `jsonschema`, a dependency, checks each emitted document against the vendored OASIS schema in the tests.
- The change deletes the conversion of a timed-out result to `subprocess.TimeoutExpired` inside `BaseSecurityScanner._run_tool`: the scan reads the timeout from the result. It deletes the `MagicMock` that stood in for `_run_tool` in the golangci-lint test.
