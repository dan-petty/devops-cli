# Proposal

## Why

Issue #3667: a refine round reads the comments of each item that waits, also when nothing changed on the item. In the window of #3497, refine sent 7727 GET requests, and these reads are the largest part of them. A conditional GET does not help: a comment list with no next link is not stored, so it never answers 304 (ADR 0006).

## What Changes

- The issue listing carries `comments`, the count of comments on each issue. `IssueRecord` and `Item` get the field `comments`.
- A round that reads the comments of a waiting item records what they gave in the job record: `refine.comments_seen` (the count), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues and paths that the text of the wait names).
- A later round reads the comments of a waiting item only when its count differs from `refine.comments_seen`, or the record holds none. The other exits of a wait use the record alone: a closed blocker, a commit that changed a cited path, and a closed issue or changed file that the wait on a person names.
- Apply records the marks of a waiting item once. A comment that is no reply moves the count, costs one read, and the round records the new count.
- An item that refine set Ready and a person or the stage job set back to New, and an item that an account that the jobs do not trust opened, still cost one comment read in each round. The docstring of `refine.py` says so.
- The dry-run plan lists the record of a waiting item under the condition `wait_unrecorded`.
- The selection, the job record and the dry-run plan are observable, so the change carries a spec delta. The change fits one pull request.
- The measure of the drop of GitHub requests after the change is live is the work of #3866.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: ADDED requirements for the record of a read of comments and for the round that reads no comment of an unchanged waiting item.

## Impact

- Code: `src/devops_cli/roadmap/refine.py`, `store.py`, `github_store.py`, `request_plan.py` and `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_refine.py`, `test_roadmap_store_contract.py`, `test_roadmap_dry_runs.py`, and the fakes `tests/roadmap_github_fake.py` and `tests/support/fakes/roadmap_store.py`.
- Cost: an item that waits and holds an unchanged count costs no comment read. Each existing wait costs one more read and one write of its job record, once.

## Feasibility

- `GET /repos/dan-petty/devops-cli/issues?state=open&per_page=2&labels=scope/roadmap` (read on 2026-11-07 with `uv run devops gh api`) gives `comments` for each issue (for example `{"comments":1,"number":3885}`), and the comment listing of #3667 has the same length as its `comments`. So the listing that the store already reads gives the count with no new request.
- The issue proposes `updated_at` as the mark. That does not work. Every write to an issue moves `updated_at`, the write of the job record and the comment of refine included (`test_every_write_to_an_issue_a_comment_included_moves_its_updated_at`). A mark that holds the `updated_at` of the last read can never match the value after the write that holds the mark, so each round would read again. Only a comment moves `comments`, so the count keeps the intent of the issue: read the comments only when they changed. The contract case `test_an_item_carries_the_count_of_comments_on_its_issue` shows that an edit of the job record leaves the count as it is.
- A comment that a person deletes and replaces keeps the count, so refine misses that reply until the next comment. A body edit or a new comment still ends the wait.

## Existing Tool Considered

`Item` and the job record of refine cover the need. hishel, a maintained HTTP cache for httpx, meets the same rule as the issue says: GitHub does not store a page with no next link (ADR 0006), so the comment list never answers 304. The change adds no library and deletes the read of comments from the path of an unchanged waiting item.
