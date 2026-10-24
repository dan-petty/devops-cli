# Tasks

## 1. Implement deleted file filtering and per-file scanner failure reporting

- [x] 1.1 Write failing test for branch review deleting a YAML file to verify deleted paths reach neither pages nor targets
- [x] 1.2 Write failing test for two manifests where one fails, verifying the good manifest findings are admitted, coverage matrix records `failed(<reason>)` on the failed manifest and `scanned` on the good manifest, and tool status reads `ran; 1 of 2 files failed: <reason>`
- [x] 1.3 Update `ScanOutcome` to track `failed_files`
- [x] 1.4 Update `_observe_outcome`, `_scan_kubernetes_manifests`, `_scan_container_and_lockfiles` to record per-file failures and aggregate `ran; N of M files failed` status
- [x] 1.5 Update `_static_analyzer_reasons`, `_static_analyzer_summary`, `_static_analysis_line`, `_resolve_effective_tool_states`, `_resolve_tool_file_status`, and `_compute_coverage_matrix`
- [x] 1.6 Update `_prepare_branch_content`, `_prepare_pr_content`, and `_execute_review_workflow` in `runner.py` to filter deleted files from `pages`
- [x] 1.7 Run tests and verify `uv run devops openspec check` and `uv run devops ci` pass
