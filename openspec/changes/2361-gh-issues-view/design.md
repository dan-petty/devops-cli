# Design

## Context

See proposal.md for the motivation and the evidence.

- `issues list` reads through `gh issue list` and falls back to the REST listing in `_fetch_issues_rest`. Both parse each item with `_parse_single_issue` into `GitHubIssue`.
- `GitHubSession.rest` makes one paced request. It raises `GitHubNotFoundError` for a 404 and `GitHubUnreadError` for a 5xx or a body it cannot decode.
- `write_stream` prints raw text with Rich markup off. A panel or a table would read `[x]` in an issue title as markup.
- The MCP server registers each `devops` command as a tool, so the new command appears as `gh_issues_view`.

## Goals / Non-Goals

**Goals:**

- One command prints one whole issue.
- A failure never reads as an empty issue.

**Non-Goals:**

- No comments, timeline or sub-issue links. A reader that needs them gets a separate item.
- No `--json` option. `GitHubIssue` has no JSON output on `issues list` either, and a second format is a separate item.
- No `gh issue view` call. The command uses the REST path alone.

## Decisions

**The reader uses the REST session alone.** `issues list` calls `gh issue list` first because `gh` can page and filter. A single read has nothing to page, so one REST call is the whole read, and it fails in one way. Alternative rejected: `gh issue view --json` with a REST fallback. It doubles the code paths for one request and adds a subprocess.

**A pull request is refused.** The REST issues endpoint answers for a pull request number. Printing it as an issue would show a pull request without its head, base or checks, so the reader raises `GitHubOperationError` and names `devops pr view`. `_filter_rest_issues` leaves out the same items for the same reason.

**The output is plain text.** The command writes a header of `Field: value` lines, an empty line and the body with `write_stream`. Alternative rejected: `print_panel`, which reads markup in the body.
