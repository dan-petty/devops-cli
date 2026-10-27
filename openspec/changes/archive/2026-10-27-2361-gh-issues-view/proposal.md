# Proposal

## Why

Issue #2361: a reader can list issues with `devops gh issues list`, but cannot read one issue. The list cuts each title to 50 characters and shows no body, state or date. To read one issue, the reader must run `gh issue view`, which AGENTS.md rule 7 forbids for agents because it does not pace requests against the rate limit. `devops pr view` and `devops gh runs view` exist, so `issues` is the only one of the three groups that cannot view one item.

## What Changes

- `devops gh issues view <number>` prints one issue: its number, title, state, web URL, milestone, labels, assignees, created and updated dates, and its full body. It cuts nothing.
- The command reads the issue with one `GET /repos/{repo}/issues/{number}` through the GitHub session, and parses the answer into the `GitHubIssue` model that `issues list` already uses. `--repo/-R` names another repository, as for `issues list`.
- An issue that does not exist is an error that names the number and the repository, and the exit status is 1.
- A number that belongs to a pull request is an error that names `devops pr view <number>`, and the exit status is 1. The REST issues endpoint answers for pull requests too and marks them with a `pull_request` key.
- `_parse_single_issue` takes the web address of an issue from `html_url` before `url`. A REST answer holds the API address in `url`, so the REST fallback of `issues list` shows the wrong address today. `gh issue list --json` has no `html_url`, so its `url` still gives the web address.
- The command prints the text as plain text, so Rich markup in a title or a body shows as written.
- The command is a new observable command, so it carries a spec delta. This change fits one pull request. It adds the capability `gh-issues-view`.
- The command is a read-only MCP tool, `gh_issues_view`, with the other `gh issues` reads.
- The group keeps its name `issues`. The change adds no group `issue`.
- Out of scope: issue comments, timeline events and sub-issue links.

## Capabilities

### New Capabilities

- `gh-issues-view`: how `devops gh issues view` reads and prints one issue, and how it refuses a number that names no issue or names a pull request.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/github/issues.py` (the new reader `get_repository_issue` and a text renderer), `src/devops_cli/commands/gh.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/constants.py` (the MCP exposure table) and the knowledge-base task `github_project_management.md`.
- Tests: `tests/test_github_issues.py` (the reader), `tests/test_gh_cmd.py` (the command), `tests/test_fastmcp_contracts.py` (the MCP tool `gh_issues_view`).
- Documents: the generated `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/gh.md` and `docs/MCP_TOOLS.md`.

## Feasibility

- Command output on `main`: `uv run devops gh issues --help` lists `list`, `create`, `triage`, `status` and `edit`, and no `view`. `uv run devops gh --help` has no group `issue`.
- `GitHubIssue`, `_parse_single_issue` and `get_github_session()` exist in `src/devops_cli/github/issues.py`. `GitHubSession.rest` raises `GitHubNotFoundError` for a 404, with the request path in the message.
- GitHub documents `GET /repos/{owner}/{repo}/issues/{number}` and says that it answers for pull requests too, with a `pull_request` key.

## Existing Tool Considered

- `gh issue view` covers the need, but AGENTS.md rule 7 forbids bare `gh`. The change reuses the GitHub session, `_parse_single_issue` and `GitHubIssue`. It adds one reader function, one renderer and one command, and no dependency. The change deletes no internal code.
