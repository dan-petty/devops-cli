# Design

## Context

Issue #1324 migrates GitHub-facing commands (`devops pr`, `devops gh`, `devops repos`) to thin adapters tested over process and session fakes.
Commands must contain CLI argument parsing, option validation, and output formatting. Domain logic belongs in package modules.

## Architecture Decisions

### Rate Limit View Extraction

Create `devops_cli.github.rate_limit_view`:
- `format_reset_time(epoch_seconds: int | float) -> str`: Formats epoch timestamps into UTC strings and countdowns.
- `parse_rate_limit_payload(stdout: str) -> dict[str, Any]`: Validates and parses rate limit JSON payloads.
- `format_rate_limit_rows(resources: dict[str, Any]) -> list[list[str]]`: Generates display rows for rate limit tables.

`devops_cli.commands.gh` calls these functions directly.

### Branch Update Planning Extraction

Create `devops_cli.github.branch_update`:
- `open_prs_argv(repo: str | None, base: str | None) -> list[str]`: Generates argument list for querying open pull requests.
- `plan_update_all_prs(target_repo: str | None, target_base: str | None, dispatch_ci: bool = False) -> list[PlannedRequest]`: Generates planned requests for batch updates.
- `plan_update_single_pr(number: int, target_repo: str, expected_head_sha: str | None = None, dispatch_ci: bool = False) -> list[PlannedRequest]`: Generates planned requests for a single update.

`devops_cli.commands.pr` calls these functions for dry-run request planning.

### Clone Destination Parsing Extraction

In `devops_cli.git.operations`:
- `parse_clone_destination(url: str) -> tuple[str, str]`: Extracts organization or group and repository name from a Git clone URL.

`devops_cli.commands.repos` calls this function.

### Pull Request Template Invariant Test

Move template tests to `tests/invariants/test_pull_request_template.py`:
- `test_pr_template_asks_for_the_issue_and_its_change_and_nothing_a_check_decides`
- `test_pr_template_reads_as_the_squash_commit_message`

Update `docs/TESTING.md` to register `test_pull_request_template.py` as an invariant test subject.
