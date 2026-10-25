# Proposal

## Why

Issue #1140: when a review scans multiple files with a tool such as Kube-linter or Pluto, a failure on one file marks the whole tool as failed.
The tool produces valid findings on good files, but the report marks every file for that tool as failed in the coverage table.
The Static Analyzers table also marks the whole tool as failed instead of recording the failure per file.
In addition, git diff blocks for deleted files can reach review pages even when the files no longer exist.

## What Changes

- Deleted paths from `git diff --name-status` do not reach review pages or targets.
- A failed file in a multi-file tool scan does not mark the whole tool as failed when other files succeed.
- The scan outcome records failed files with their error reasons.
- The coverage matrix marks each failed file as `failed(<reason>)` in its own row and marks successful files as `scanned`.
- When $N$ of $M$ files fail ($0 < N < M$), the tool status reads `ran; N of M files failed`.
- The Static Analyzers table displays `ran; N of M files failed: <reason>`.
- Findings from valid manifests continue to be admitted.

## Capabilities

### New Capabilities

- `review-scanner-file-failure`: a review records static scanner execution outcomes per file. A failure on one file does not mark the tool as failed when other files succeed. The coverage matrix records the failure on the row of the file, and the tool reports how many files failed.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `_observe_outcome`, `_scan_kubernetes_manifests`, `_scan_container_and_lockfiles`, `_static_analyzer_states`, `_static_analyzer_reasons`, `_static_analyzer_failed_files`, `_resolve_effective_tool_states`, `_resolve_tool_file_status`, `_compute_coverage_matrix`, `_static_analyzer_summary`, and `_static_analysis_line`.
- `src/devops_cli/ai/review/runner.py`: `_prepare_branch_content`, `_prepare_pr_content`, and `_execute_review_workflow` filter deleted files from pages.
- `src/devops_cli/security/base.py`: `ScanOutcome` supports tracking failed files.
- `tests/`: tests covering deleted file filtering in branch review, per-file failure reporting, and two-manifest review.

## Feasibility

- The issue describes review runs where Kube-linter and Pluto failed on 2 files out of 21 files, causing the tool to report `failed` despite finding 30 valid candidates.
- In `src/devops_cli/ai/review/pipeline.py`, `_observe_outcome` overwrites the tool outcome with `ANALYZER_FAILED` if any single file fails.
- In `src/devops_cli/ai/review/runner.py`, `_execute_review_workflow` filters deleted files from `all_files` but leaves them in `pages`.
- By tracking failed files per tool and filtering deleted files from `pages`, both criteria are satisfied without breaking existing contracts.

## Existing Tool Considered

The existing `ScanOutcome` and coverage matrix infrastructure in `devops_cli` covers static analysis reporting.
Extending `ScanOutcome` and `_compute_coverage_matrix` to track failed files follows the pattern established by `unscanned` in #1144.
