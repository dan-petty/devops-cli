# Proposal

## Why

Issue #2005: when refine finds that an item is blocked, it records the open items that block it. Since #1758, the item waits until a person comments, the body changes or each blocking item closes. A block that names code, for example a function or a file that the item cites, does not end when that code changes. So an item can wait after the cause of its block is gone, and only a person can start refine on it again.

## What Changes

- The refine proposal gets the field `block_paths`: when the proposal has a suspected block or a dependency, the repository paths of the files that hold the code that causes the block. The proposal prompt names the field.
- Refine keeps each path that the checkout holds at the refined commit, one time and without its line, and at most `CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS` (5) paths. It records them in the job record as `refine.block_paths` only when the item has an open dependency or a suspected block. Its next-step comment then names these files in a last line.
- Without `--item`, a round looks at a waiting item again when a commit on the default branch changed one of the recorded paths at or after refine's last comment on the item. When no recorded path changed, the item keeps waiting and the round makes no model call for it.
- The store interface gets `path_changed_at(path)`: the time of the newest commit on the default branch that changed the path. The GitHub adapter reads it with one `gh api` request to the commits listing (`commits?path=<path>&per_page=1`), one time for each path in the life of the store. The in-memory adapter gets `seed_commit`.
- `comments_on` gives each comment as an `IssueComment`, its body and the time GitHub made it, so refine knows when it last commented. Intake and refine read the body from it.
- The dry-run plan of a refine round lists the commit read of each cited path of a waiting item, under the condition that no reply follows refine's last comment.
- The selection, the job record, the comment and the dry-run plan are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: ADDED requirements for the paths that refine records as the cause of a block, and for the end of a wait when that code changes.

## Impact

- Code: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/constants.py` and `src/devops_cli/lang/en/messages.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md` names `block_paths`.
- Tests: `tests/test_roadmap_refine.py`, `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_github_store.py`, `tests/test_roadmap_dry_runs.py`, `tests/test_roadmap_intake.py`, `tests/test_roadmap_return.py` and `tests/roadmap_board_fake.py`.
- Cost: a round reads the newest commit of each recorded path of an item that still waits after the comment check, at most five paths for each item, and one read for each path in a round. An item with no recorded path costs no extra request.

## Feasibility

- `GET /repos/dan-petty/devops-cli/commits?path=src/devops_cli/roadmap/refine.py&per_page=1` (read on 2026-10-24 with `uv run devops gh api`) gave one commit, `0a2bfe1f0b4c`, with `commit.committer.date` `2026-10-24T06:06:57Z`, the newest commit on the default branch that changed the file. `git log -1 --format=%cI -- src/devops_cli/roadmap/refine.py` in the checkout gave the same commit and time. A path that no commit changed, `does/not/exist.py`, gave `[]`. With `since=2026-10-24T12:00:00Z` the listing gave `[]`. So one request gives the time of the last change of a path.
- The issue comments listing that refine already reads for each waiting item (`GET /repos/{owner}/{repo}/issues/{number}/comments`) gives `created_at` for each comment (the recorded fixture `tests/fixtures/roadmap/issue-844-comments.json` holds it). So refine knows the time of its last comment with no new request.
- On the base `0a2bfe1f`, `RefinementProposal` has no field for code paths, `_still_waiting` in `refine.py` ends a wait only on a reply or on closed blockers, and the store has no commit read. The new tests fail on the base for these reasons.

## Existing Tool Considered

The GitHub REST commits API with its `path` filter gives the newest commit that changed a path, and `git log -- <path>` gives the same from a checkout. The change uses the API, through the `gh api` runner that the store already uses for single reads, so the result is the default branch on GitHub and not the state of a local checkout. Nothing is built in place of a tool. The change deletes no internal code: `replies_since_refine` and `_replies_for_model` now read the body of each `IssueComment`.
