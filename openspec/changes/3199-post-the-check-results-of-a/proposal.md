# Proposal

## Why

CONTRIBUTING.md requires check results and fail-to-pass evidence in a pull request comment. It also forbids hand-typed counts. No command currently formats or writes this comment (#3199). Agents and developers manually compile check numbers into comments, which causes inconsistent counts and formatting errors across pull requests.

## Order and Dependencies

This change relates to #3032 (trace recording in pull request comments), #2585 (PR check-readiness gates), and #3235 (MCP exposure of PR tools). It adds a dedicated evidence command and has no blocking prerequisite issues.

## What Changes

- Add `devops pr evidence <number>` to `src/devops_cli/commands/pr.py` with the `@dry_run_class("request-plan")` decorator.
- Add `src/devops_cli/github/pr_evidence.py` to format check runs and fail-to-pass test results into structured markdown.
- Reuse `read_check_runs` from `src/devops_cli/github/check_verdict.py` to obtain normalized `PRCheckItem` records.
- Add paginated comment listing and comment updating methods to `GitHubClient` in `src/devops_cli/github/client.py`.
- Maintain a single comment per pull request using marker line `<!-- devops-cli:pr-evidence -->` and author identity matching.
- Only include a fail-to-pass check run link when the pull request title indicates a fix and the job succeeded.
- Escape pipe characters in check run names within markdown tables.
- Add `--attribution` option to `devops pr evidence` to append caller-specified attribution footers.
- In dry-run mode, emit planned requests with zero external network requests, adhering to the `request-plan` dry-run class.
- Update `command-dry-run-class` spec requirement `pr-commands-request-plans` to classify `pr evidence` as the eighteenth command.
- Add new capability `pull-request-evidence` for pull request check results and sticky evidence comments.
- Add exclusions in `tests/ai/mcp/test_mcp.py` and register the command in `PR_COMMAND_CALLBACKS` in `tests/commands/test_pr_dry_run.py`.
- Regenerate documentation and sync `README.md`.

## Capabilities

### New Capabilities

- `pull-request-evidence`: Formats and posts pull request check runs and fail-to-pass test results as a sticky pull request comment.

### Modified Capabilities

- `command-dry-run-class`: pr-commands-request-plans

## Impact

- Code: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTRIBUTING.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/pr.md`
- Tests: `tests/github/test_pr_evidence.py`, `tests/commands/test_pr_evidence.py`, `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/test_mcp.py`

## Feasibility

- In `src/devops_cli/commands/pr.py`, commands include `checks`, `monitor`, `describe`, and `ready`, with no `evidence` command.
- In `src/devops_cli/github/check_verdict.py:374`, `read_check_runs` already parses check runs into `PRCheckItem` instances.
- In `src/devops_cli/github/client.py:444`, `GitHubClient` implements `create_issue_comment`. Listing and updating comments require paginated helpers.
- In `openspec/specs/command-dry-run-class/spec.md:96-97`, `pr-commands-request-plans` classifies 17 commands with zero external requests in dry run.
- In `tests/commands/test_pr_dry_run.py:48-70`, `PR_COMMAND_CALLBACKS` registers and verifies dry-run compliance for PR commands.

## Existing Tool Considered

GitHub Actions like `marocchino/sticky-pull-request-comment` and `actions/github-script` update pull request comments in workflow jobs. However, they run exclusively inside GitHub Actions runners. A CLI command in `devops pr` allows developers, local scripts, CI workflows, and autonomous agents to post verified evidence uniformly with rate-limited GitHub client pacing and PRCheckItem parsing. Cost to build, keep, and fix is approximately 60,000 tokens and 3 hours of elapsed time.
