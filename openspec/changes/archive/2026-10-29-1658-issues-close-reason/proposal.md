# Proposal

## Why

Issue #1658: no `devops gh` command closes an issue with a reason. `devops gh issues edit --state closed` sends no `state_reason`, so GitHub records the close as completed. No `devops gh` command posts an issue comment either. AGENTS.md forbids bare `gh`, and rule 2 tells an agent to close a superseded issue as rejected. So an agent closes such an issue with two raw `devops gh api` calls, and a person cannot see from the command that the reason and the evidence go together. #1017 and #996 were closed with "Superseded by #1150" but recorded as completed.

## What Changes

- New command `devops gh issues close <number> --reason completed|not-planned [--comment-file <path>] [--repo <owner/name>] [--dry-run]`.
  - It reads the issue first. It refuses a number that is no issue of the repository, a pull request, and an issue that is already closed, and it writes nothing then.
  - When `--comment-file` is given, it posts the file's text as a comment first, then closes the issue with `state=closed` and the `state_reason` of the reason. `-` reads the comment from standard input. The comment never comes from the command line. An empty comment is refused.
  - When the close fails after the comment, the error says that the comment is on the issue and that the issue is still open, so a second run without `--comment-file` closes it without a second comment.
  - `--dry-run` sends no request and prints the requests a run makes: the read of the issue, the comment when one is given, and the close.
  - A reason that is not `completed` or `not-planned` exits 2 and names the allowed values, before any request.
- `RoadmapStore.close(number, reason, comment=None)` is the one place that reads, comments and closes, in that order. Both adapters have it. The GitHub store sends the close as one `PATCH` of the issue with `{"state": "closed", "state_reason": ...}` on standard input, through `issue_edit_args` and `run_gh`, so the rate limiter paces it.
- `StoreRequests.close` lists the same requests for the dry run, from the same argument builders.
- The command is an MCP tool beside `gh issues edit`.
- The help of `devops roadmap intake`, which says to close an issue as not planned to keep it off the roadmap, names the command.
- The command carries a spec delta: the new capability `gh-issues-close`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `gh-issues-close`: how `devops gh issues close` closes an issue with a reason and an optional comment, what it refuses, and its dry run.

## Impact

- `src/devops_cli/roadmap/store.py`, `roadmap/github_store.py`, `roadmap/memory_store.py`, `roadmap/request_plan.py`.
- `src/devops_cli/github/issues.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/config/constants.py` (the MCP exposure table).
- `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/roadmap_github_fake.py`, `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_github_store.py`, `tests/commands/test_gh_issues_close.py`.
- The regenerated `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/gh.md` and `docs/commands/roadmap.md`.

## Feasibility

- GitHub's REST documentation for "Update an issue" (`PATCH /repos/{owner}/{repo}/issues/{issue_number}`, API version 2022-11-28, read on 2026-10-29) lists `state` (`open`, `closed`) and `state_reason` (`completed`, `not_planned`, `duplicate`, `reopened`, `null`), and says of `state_reason`: "Ignored unless state is changed." So a `PATCH` cannot change the reason of an issue that is already closed, and the command refuses such an issue instead of reporting a change that GitHub ignores. A person reopens it with `devops gh issues edit <number> --state open` first.
- A close as a duplicate needs `duplicate_issue_id`, the ID of the original issue, and #2223 leaves the close of a duplicate to a person. The issue asks for `completed` and `not-planned` only, so this change has no duplicate reason.
- On origin/main f9493fa4, `GitHubRoadmapStore.comment` posts a comment with `comment_args` through `_write` and `run_gh`, and `_send_edit` sends one `PATCH` of an issue with JSON on standard input and keeps the issue GitHub returns. `_require_issue` reads the issue and refuses a pull request or a missing issue. `InMemoryRoadmapStore._close` closes an issue for a `CloseReason` and records it. `CloseReason` (`roadmap/store.py`) already names `completed` and `not_planned` as GitHub does. `close_issue_args`, which the issue names, was deleted by #1952.
- `devops gh issues` has `list`, `view`, `create`, `triage`, `status` and `edit`, and no `close`.

## Existing Tool Considered

`gh issue close <number> --reason "not planned" --comment <text>` covers the need, but AGENTS.md rule 7 forbids bare `gh`, because the `devops` commands pace each request against the rate limit. The change adds no request builder of its own: the close is a `PATCH` through `issue_edit_args` and `run_gh`, as every issue write of the store is, and the comment uses the store's `comment`. Written cost of the command: about 60k tokens to build, little upkeep, because it reuses the store's writes; about two hours. The change deletes no code: no other path closes an issue with a reason.
