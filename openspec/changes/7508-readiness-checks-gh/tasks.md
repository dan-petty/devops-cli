# Tasks

## 1. Read the checks of the verdict with gh pr checks

Kind: behavior.

Reads: `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_plans.py`.

Changes: `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `pyproject.toml`, `uv.lock`, `tests/github/test_pr_check_verdict.py`, `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`; deletes `src/devops_cli/github/workflow_triggers.py` and `tests/github/test_workflow_triggers.py`.

- [x] 1.1 Write the tests of `read_pr_checks`: the gh arguments, each bucket, `no checks reported`, a failed read and output that is no list. Write the tests of the verdict, `pr ready`, `check-readiness`, `pr monitor`, `pr checks` and the plan of `check-readiness` against the answers of `gh pr checks` and the rules of `main`, and watch them fail.
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/github/test_merge_readiness.py tests/commands/test_pr.py tests/commands/test_pr_cmd.py tests/commands/test_pr_dry_run.py`
- [x] 1.2 Add `read_pr_checks`, judge the checks with it, read the rules of the base branch when the head reports no check, and add the rules read to the plans of `check-readiness` and `pr monitor`.
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/github/test_merge_readiness.py tests/commands/test_pr.py tests/commands/test_pr_cmd.py tests/commands/test_pr_dry_run.py`
- [x] 1.3 Delete `workflow_triggers.py` and its tests, `GitHubClient.pull_request_workflow_at`, `read_commit_checks` and the REST read of the commit statuses, the REST fallback of `fetch_pr_check_verdicts`, `_render_pr_checks_fallback`, the message `ready_no_ci` and the dependency `wcmatch`.
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/github/test_merge_readiness.py tests/commands/test_pr.py tests/commands/test_pr_cmd.py tests/commands/test_pr_dry_run.py tests/ai/mcp/test_mcp_tool_listing.py`

## 2. Documents

Kind: other.

Changes: `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/MCP_TOOLS.md`.

- [x] 2.1 Regenerate the command reference for the new help of `devops pr ready`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #7509: wait for the checks of `devops pr monitor` with `gh pr checks --watch`.
- #7510: read the checks of the roadmap rows with `gh pr checks`, and delete `latest_run_of_each_check`.
- #7512: wait for and merge the template pull request of `devops repos onboard` with `gh`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
