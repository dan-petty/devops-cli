# Proposal

## Why

Issue #1983: A review keeps the `ToolRun` of every run of its tools in `profile.json` and in `review.md`. Its SARIF document, `findings.sarif`, does not hold these records. So a consumer of the document cannot see which version, binary, config or ruleset gave a result. The issue is part 5 of the tracker #772.

## What Changes

- `to_sarif` in `src/devops_cli/security/sarif.py` takes the records of the runs (`tool_runs`). The SARIF run of a tool holds each record of that tool in its property bag under `tool_runs`, with the field names of `ToolRun`, in the order of the runs.
- The driver of the run names the version of the records when no result names a version and the records name one version.
- A record gives no tool a run. A tool that has records and no result has no run in the document.
- The review passes the records of its `RecordingToolExecutor` to `to_sarif` when it writes `findings.sarif` (`src/devops_cli/ai/review/pipeline.py`).
- The module docstring of `src/devops_cli/security/tool_executor.py` gives the SARIF 2.1.0 name of each field. It also tells why the record fills no `invocation`, no `artifact` and no `versionControlProvenance`.
- `docs/SELF_IMPROVEMENT.md` tells where `findings.sarif` holds the records.

The SARIF document of a review is output that a consumer reads, so the change carries a spec delta. It makes the capability `sarif-export`, because no capability holds the SARIF documents of devops-cli.

The issue asks for more than this change writes. The design tells, for each part, the section of the SARIF 2.1.0 specification that stops it:

- The issue asks that a `ToolRun` hold the exit code of its run, for `executionSuccessful`. SARIF says that the exit code does not tell if a tool succeeded (section 3.20.14). The only SARIF name for the exit code is `invocation.exitCode`, and the record cannot fill an invocation. The exit code stays out of the record. A follow-up holds it.
- The issue asks for the binary digest, the config digest, the ruleset digest and the targets digest as `run.artifacts` with `hashes`, and for the commit as `versionControlProvenance`. The record does not hold the values that SARIF requires there.

The issue leaves to a person the question if a clean tool gets a run. This change answers it from the specification, as the owner asked on 2026-10-22 for open design questions. A run with no results says that the tool ran and found nothing (section 3.14.23). A record does not say that the tool succeeded. So a record alone gives no run. The SARIF document of `devops scan` keeps its rule: a scanner whose outcome is `ran` gets a run, also with no results.

This change fits in one pull request.

## Capabilities

### New Capabilities

- `sarif-export`: what a run of a SARIF document of devops-cli holds. This change adds the records of the review tools.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/security/sarif.py`: `to_sarif` takes `tool_runs` and writes each record in the run of its tool.
- `src/devops_cli/ai/review/pipeline.py`: the review passes its records to `to_sarif`.
- `src/devops_cli/security/tool_executor.py`: the module docstring maps the fields of `ToolRun` to SARIF 2.1.0.
- `docs/SELF_IMPROVEMENT.md`: the section "Tool Run Records" names `findings.sarif`.
- Tests in `tests/test_security_sarif.py` and `tests/test_review_tool_runs.py`.

## Feasibility

I confirmed the premise against the real system, at origin/main 90687950:

- The OASIS SARIF 2.1.0 specification, Errata 01 (`sarif-v2.1.0-errata01-os-complete.html` from docs.oasis-open.org), sections 3.5.2, 3.14.23, 3.14.28, 3.20.2, 3.20.9, 3.20.14, 3.23.3, 3.23.4, 3.24.2, 3.24.6 and 3.24.11. The design quotes each one.
- The vendored schema `tests/fixtures/sarif-schema-2.1.0.json` (Errata 01). It requires `executionSuccessful` in an `invocation` and `repositoryUri` in a `versionControlDetails`. It lists `driver` as an artifact role. It allows any value in a property bag.
- `record_tool_run` builds the record before the tool starts. `ToolResult` holds the exit code, and `ToolRun` does not.
- `_handle_json_output` and `_handle_non_json_output` in `src/devops_cli/security/base.py` decide if a scan succeeded from the exit code and from the parsed output together. So no executor can read success from the exit code.
- `_persist_session_artifacts` in `src/devops_cli/ai/review/pipeline.py` calls `to_sarif` with no outcomes. The review keeps its records in `self.tool_executor.runs`.
- `digest` and `file_digest` in `src/devops_cli/ai/run_store.py` give the first 16 hexadecimal digits of a SHA-256. The config, ruleset and targets digests are digests of a sorted list, not the hash of one file.
- `devops scan report` keeps no records. Only the review wraps its executor in a `RecordingToolExecutor`. The SARIF that CI uploads to code scanning comes from `devops scan report`, so this change sends no record to code scanning.

## Existing Tool Considered

- `sarif-om` (Microsoft, the SARIF object model for Python) has had no release since 1.0.4 on 2019-10-05. It is not maintained.
- `sarif-pydantic` 0.6.2 (2025-11-04) is a project of one author before 1.0, with no license in its package metadata.
- Neither library changes which SARIF names a record can fill: that follows from the specification. The emitter in `src/devops_cli/security/sarif.py` already builds the document, and `jsonschema`, a dependency, checks each emitted document against the vendored OASIS schema in the tests. This change adds one property to a run and builds no new tool.
- The change deletes no internal code.
