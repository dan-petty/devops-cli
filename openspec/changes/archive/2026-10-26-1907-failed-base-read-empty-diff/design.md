# Design

## Architecture

This change improves reliability and error reporting across pull request reads and reviews.

### 1. Base Revision Read Failures as Coverage Gaps

When scanning base revisions for fingerprints or calculating complexity deltas, the review reads base files via `base_revision.read(path)`.
- If the file does not exist, `read` returns `None`. The helper treats this as an absent file (normal for added files).
- If `read` raises an error (such as `GitHubOperationError` or `OSError`), the helper catches the read error and records a coverage gap in `coverage_gaps` using `_record_coverage_gap`.
- The helper continues processing the other candidate files instead of aborting the stage.
- The stage handlers `_run_static_scanners` and `_run_review_evidence` no longer use broad `except` blocks that hide unexpected errors.

### 2. Empty Pull Request Diffs

When GitHub returns an empty diff body (zero bytes) for a pull request with no changes:
- `RestTransport` decodes zero-length responses with diff media types as empty strings `""` rather than `None`.
- `GitHubClient.get_pr_diff` receives the empty string and returns it cleanly.
- Downstream review functions process the empty diff and complete without error.

### 3. Deduplicating Pull Request Files API

- `src/devops_cli/commands/pr.py` delegates pull request file listing to `GitHubClient.get_pull_files`.
- `PullRequestFile` provides default values of 0 for `additions` and `changes`.
- Removes duplicate pagination and validation helpers in `commands/pr.py`.

## Rejected Alternatives

### Alternative 1: Let base revision helpers raise unhandled exceptions

- **Proposal**: Allow `_write_base_revision_files` and `_evaluate_session_complexity_deltas` to raise errors directly.
- **Rejection Evidence**: In `ReviewPipelineOrchestrator._run_static_scanners`, an unhandled exception aborted the entire static scanning stage. All static scanner findings for the head files were lost. Recording an explicit coverage gap and continuing allows the review to inspect head files while informing the operator about the missing baseline.

### Alternative 2: Catch errors with broad `except Exception` in stage handlers

- **Proposal**: Keep or widen `except Exception` in `_run_static_scanners` and `_run_review_evidence`.
- **Rejection Evidence**: Swallowing `Exception` hides bugs and unexpected system failures with a debug log. It violates project rule 2 against swallowing errors.

### Alternative 3: Return `None` for empty diffs in `get_pr_diff`

- **Proposal**: Have `get_pr_diff` return `None` when a pull request diff has no changes.
- **Rejection Evidence**: Downstream consumers (`diff_blocks`) expect a string unified diff. An empty diff is valid text representing zero file modifications. Returning an empty string preserves type consistency across callers.
