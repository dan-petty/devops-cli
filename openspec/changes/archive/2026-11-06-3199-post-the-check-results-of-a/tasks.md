# Tasks

## 1. Build PR check evidence text and fail-to-pass links

Reads: `src/devops_cli/github/check_verdict.py`, `src/devops_cli/config/constants.py`.
Changes: `src/devops_cli/github/pr_evidence.py` (new), `tests/github/test_pr_evidence.py` (new).

- [x] 1.1 In `tests/github/test_pr_evidence.py`, write tests for comment generation: header with head SHA, table with check names and links, pipe escaping, skipped checks listing, and conditional fail-to-pass links for fix PRs. Assert that feat PRs omit the fail-to-pass section, and `--attribution` appends footer lines. Verify test failure on base code
- [x] 1.2 In `src/devops_cli/github/pr_evidence.py`, implement `build_pr_evidence_comment` taking `PRCheckItem` lists, head SHA, PR title, and optional attribution. Escape pipe characters in check names, format the markdown table, and append the fail-to-pass link when the title matches a defect and the check passed. Verify `tests/github/test_pr_evidence.py` passes

## 2. Add devops pr evidence command and client helpers

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
Changes: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr_evidence.py` (new), `tests/commands/test_pr_dry_run.py`, `tests/ai/mcp/test_mcp.py`.

- [x] 2.1 In `tests/commands/test_pr_evidence.py`, write tests for `devops pr evidence`: new comment via POST, updating existing marked comment via PATCH, usage error on free text, and zero network calls during `--dry-run`. Verify test failure on base code
- [x] 2.2 In `src/devops_cli/github/client.py`, add paginated `list_issue_comments` and `update_issue_comment` methods. In `src/devops_cli/commands/pr.py`, add `evidence` command with `@dry_run_class("request-plan")`, `--attribution`, `--repo`, and `--dry-run` options. In `src/devops_cli/lang/en/help.py` and `messages.py`, add help and message strings. Register `pr evidence` in `tests/commands/test_pr_dry_run.py` and `tests/ai/mcp/test_mcp.py`. Verify tests pass

## 3. Document command and regenerate CLI reference

Reads: `CONTRIBUTING.md`, `README.md`.
Changes: `CONTRIBUTING.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/pr.md`.

- [x] 3.1 In `CONTRIBUTING.md`, document `devops pr evidence <number>` for posting check results. Run `uv run devops docs generate --sync-readme` to update `README.md`, `docs/CLI_REFERENCE.md`, and `docs/commands/pr.md`. Verify `uv run devops ci docs` passes

## Criteria

- The command reads check runs for the head commit and formats a markdown table with check conclusions and links.: group 1
- The comment includes a fail-to-pass check link for fix pull requests with passing fail-to-pass runs, and omits it for feat pull requests.: group 1
- Pipe characters in check names are escaped in markdown tables.: group 1
- The command maintains one marked comment per pull request, updating via PATCH on subsequent runs.: group 2
- The command rejects free-text input and derives counts from GitHub check runs.: group 2
- The dry-run execution makes zero external requests and outputs planned requests.: group 2
- The command appends caller-specified attribution text when `--attribution` is provided.: group 1
- CLI documentation and README reflect the new command.: group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
