# Proposal

## Why

Issue #1907 states that two pull request data reads in the review path fail without a clear error.
The helpers `_write_base_revision_files`, `_write_base_revision_lockfiles` and `_evaluate_session_complexity_deltas` treat a base file that failed to load as an absent file.
The review runs with a missing baseline and gives no message about the missing baseline.
`get_pr_diff` raises `GitHubUnreadError` with the text `is no diff: NoneType` when a pull request has an empty diff body.
In addition, `src/devops_cli/commands/pr.py` duplicates `GitHubClient.get_pull_files`.
This change fits one pull request.

## What Changes

This change alters user-observable review and CLI behavior:
- When a base revision file read fails, the review records an explicit coverage gap for the file with the reason `Base revision: <error>`.
- The review terminal summary and markdown report list the coverage gap in the skipped and errored files table.
- A pull request with an empty diff body returns an empty diff string without error instead of raising `GitHubUnreadError`.
- `devops pr check-readiness` reads pull request changed files through `GitHubClient.get_pull_files`.
- Removes broad exception swallowing in `_run_static_scanners` and `_run_review_evidence`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `review-coverage-gaps`: Records base revision file read failures as review coverage gaps with reasons.

## Impact

- `src/devops_cli/github/session_transport.py`: Decodes empty diff responses as empty strings.
- `src/devops_cli/github/client.py`: Adds default counts to `PullRequestFile` and documents empty diff return.
- `src/devops_cli/commands/pr.py`: Replaces `_fetch_pr_files` and `_changed_file` with `GitHubClient.get_pull_files`.
- `src/devops_cli/ai/review/pipeline.py`: Passes coverage gaps to base revision helpers and removes broad exception handling.
- `tests/test_github_client.py`: Verifies empty diff response returns an empty string.
- `tests/test_review_scope.py`: Verifies failed base file reads produce coverage gaps in review.
- `tests/test_pr_cmd.py`: Adapts pull request changed files tests to `PullRequestFile`.

## Feasibility

The premise was confirmed against the codebase:
1. `_write_base_revision_files` had `except Exception: continue` and treated failed reads as absent files.
2. `_evaluate_session_complexity_deltas` swallowed `(OSError, KeyError, ValueError, RuntimeError)` and treated failed base reads as absent files.
3. `_run_static_scanners` caught `Exception` and `_run_review_evidence` caught `(OSError, RuntimeError, ValueError)`.
4. `gidgethub` `sansio.decipher_response` returned `None` for zero-length response bodies, causing `get_pr_diff` to raise `GitHubUnreadError`.
5. `_fetch_pr_files` and `_changed_file` in `src/devops_cli/commands/pr.py` duplicated `GitHubClient.get_pull_files`.

## Existing Tool Considered

`GitHubClient.get_pull_files` already exists in `src/devops_cli/github/client.py` and provides typed `PullRequestFile` objects via `GitHubSession.paginate`. Using this method eliminates duplicate pagination and validation code in `src/devops_cli/commands/pr.py`.

Internal code deleted by this change:
- `_changed_file` in `src/devops_cli/commands/pr.py` (10 lines).
- `_fetch_pr_files` in `src/devops_cli/commands/pr.py` (8 lines).
- `ChangedFile` namedtuple in `src/devops_cli/commands/pr.py` (5 lines).
- `_PR_FILES_API` in `src/devops_cli/commands/pr.py` (2 lines).
- Broad `except Exception` in `_run_static_scanners` (4 lines).
- Broad `except (OSError, RuntimeError, ValueError)` in `_run_review_evidence` (4 lines).
