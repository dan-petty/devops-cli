# Design

## Per-file scanner failure tracking

When a static scanner runs across multiple files, each file outcome is recorded.
If a file fails, its path and error reason are added to `failed_files` on the scanner outcome.
If some files succeed and some files fail ($0 < N < M$), the tool status becomes `ran; N of M files failed`.
The tool reason holds the failure reasons separated by semicolons.
The Static Analyzers table formats this as `ran; N of M files failed: <reason>`.

In the coverage matrix, each file status is resolved independently.
A file present in `failed_files` receives `failed(<reason>)`.
A file that was scanned without error receives `scanned`.

## Deleted file filtering

`BaseRevision` holds changes from `list_changed_files`, which parses `git diff --name-status -z`.
Files with `change_type == "deleted"` are excluded from `pages` in `_prepare_branch_content`, `_prepare_pr_content`, and `_execute_review_workflow`.
This ensures deleted paths reach neither pages nor targets.

## Rejected alternatives

- **Marking the tool as failed if any file fails.** This is the defect being fixed; it hides findings from valid files.
- **Filtering deleted files in `diff_blocks` alone.** `diff_blocks` parses unified diff text without repository context or revision information. Filtering at the runner where `BaseRevision` is known is reliable and preserves diff formatting.
