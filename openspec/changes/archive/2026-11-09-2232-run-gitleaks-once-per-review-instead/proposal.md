# Proposal: #2232

## Why

A code review starts one sandboxed Gitleaks run for each file that it reviews. For 37 files, this took 65 seconds in the sandbox. The static stage execution time grows linearly with the number of reviewed files (#2232). Gitleaks must run once for all reviewed files over a scratch directory.

## What Changes

- Add `isolated_targets` to `GitleaksScanner` to link or copy reviewed files into the scratch directory with `materialize_targets`.
- Update `GitleaksScanner.scan` to run Gitleaks once over the materialized scratch directory for list targets.
- Update `GitleaksScanner.parse_output` to map finding file paths from the scratch directory back to the reviewed files.
- Pass `tree` to `_scan_secrets` and `run_gitleaks_scan` from `_scan_static_analysis` in `src/devops_cli/ai/review/pipeline.py`.
- Include `base` scratch directory in `tool_executor._placeholders` target paths so command template replaces the scratch directory with `{targets}`.
- Update `test_run_gitleaks_scan_list_target_runs_binary_on_every_file` to verify one Gitleaks run for list targets.
- Add tests to verify that a review of N files starts Gitleaks once and findings name reviewed files.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-stages`: Static security analysis runs Gitleaks once per review

## Impact

- Runtime performance: Static review stage runs faster by replacing N sandboxed Gitleaks executions with one execution.
- Code: `src/devops_cli/security/gitleaks.py`, `src/devops_cli/security/tool_executor.py`, `src/devops_cli/ai/review/pipeline.py`.
- Tests: `tests/security/test_security_gitleaks.py`, `tests/security/test_review_tool_runs.py`.

## Feasibility

- Source code confirmation: `GitleaksScanner.scan` at `src/devops_cli/security/gitleaks.py:139-141` iterates over `files` and calls `BaseSecurityScanner.scan` for each file.
- Pipeline confirmation: `_scan_secrets` at `src/devops_cli/ai/review/pipeline.py:1353` calls `run_gitleaks_scan(paths, ignore_tests=True, isolated=True, tool_executor=tool_executor)` without `tree`.
- Semgrep reference: `SemgrepScanner` at `src/devops_cli/security/semgrep.py:330-353` implements `isolated_targets` with `materialize_targets` and maps paths in `parse_output`.
- Gitleaks CLI capability: `gitleaks dir` accepts a directory path and scans all files in that directory recursively in one run.
- Preconditions: Gitleaks binary on PATH or faked via `ScannerFake`/`ToolExecutorFake`.

## Existing Tool Considered

Gitleaks `dir` command already scans a directory in one invocation. The review pipeline already provides `materialize_targets` helper for Semgrep. The change uses these existing capabilities. Building a custom secret detector would require 40,000 tokens to build, 10,000 tokens a year to maintain, and 20 hours of development time.

## Dependencies

None.
