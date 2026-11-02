# Design

## Decisions

- **Create a dedicated evidence builder in `src/devops_cli/github/pr_evidence.py`**:
  - `devops pr evidence` formats a sticky markdown table of check runs and test evidence.
  - Putting the builder in `pr_evidence.py` separates markdown formatting from CLI argument parsing.
- **Reuse `read_check_runs` from `src/devops_cli/github/check_verdict.py`**:
  - `read_check_runs` uses paginated GitHub sessions and maps responses to `PRCheckItem` models.
  - This avoids duplicate REST queries and preserves skip and cancellation normalization.
- **Identify existing evidence comments using marker line and author identity**:
  - Look for `<!-- devops-cli:pr-evidence -->` at the start of issue comments.
  - Verify that the comment author matches the authenticated GitHub user to prevent comment spoofing.
  - Update matching comments via PATCH; create new comments via POST when none match.
- **Conditionally include fail-to-pass check run links**:
  - Inspect the pull request title using `CONST_DEFECT_TITLE_PATTERN`.
  - Include the fail-to-pass link only when the pull request represents a defect or fix and the check run succeeded.
- **Escape pipe characters in check run names**:
  - Sanitize check names using `name.replace("|", r"\|")` to prevent table formatting breakage.
- **Follow the `request-plan` dry-run contract with zero external requests**:
  - `devops pr evidence` carries `@dry_run_class("request-plan")`.
  - Dry run emits planned requests for reading checks, reading comments, and writing comments without dispatching network calls.
  - Requirement `pr-commands-request-plans` in `command-dry-run-class` is updated to include `pr evidence` as the eighteenth command.
- **Expose `--attribution` as an optional flag**:
  - Accept `--attribution` to append caller-provided agent attribution footers, matching `devops pr describe --attribution`.
- **Exclude `pr evidence` from MCP tools**:
  - Add exclusion entries to `tests/ai/mcp/test_mcp.py` to satisfy `test_all_cli_commands_are_either_exposed_or_excluded`.

## Rejected Alternatives

- **Extend `devops pr checks` to post comments**:
  - Rejected because `devops pr checks` provides terminal tables for interactive console use. Combining comment posting into `pr checks` mixes inspection and mutation concerns.
- **Perform network calls during dry run**:
  - Rejected because `command-dry-run-class` strictly requires zero external requests for `request-plan` commands.
- **Match comments by author login alone**:
  - Rejected because a maintainer or bot might post multiple conversational comments on the pull request. Combining the marker line with author identity ensures exact targeting.
- **Automatic agent detection without CLI option**:
  - Rejected because the environment does not expose reliable, standard agent markers across different runtimes.
