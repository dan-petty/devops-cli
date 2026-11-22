# Tasks

## 1. The filters of a workflow judge the pull request

Kind: behavior. Reads: `src/devops_cli/github/client.py`, the GitHub workflow syntax reference. Changes: `pyproject.toml`, `uv.lock`, `src/devops_cli/github/workflow_triggers.py`, `src/devops_cli/github/client.py`, `tests/github/test_workflow_triggers.py`.
Adds: `PullRequestChange`, `starts_on_pull_request`

- [x] 1.1 Write the failing tests in the new file `tests/github/test_workflow_triggers.py`: each example row of GitHub's filter pattern cheat sheet that wcmatch reads as GitHub does, as a `paths` or a `branches` filter that takes or skips the pull request; the ordered `!` rule (`sub-project/**` then `!sub-project/docs/**`, and `'*.md'`, `'!README.md'`, `README*`); `paths-ignore` and `branches-ignore`; both filters together; a pull request with no changed file; the triggers as a string, a list and a mapping, with `pull_request_target`; and each case of design decision 5 that takes the pull request. The file errors on the base at collection, because the module does not exist there
  - Verification: `$ uv run devops ci test tests/github/test_workflow_triggers.py`
- [x] 1.2 Add wcmatch 12.0.4 to the dependencies of `pyproject.toml` and lock it. Add `src/devops_cli/github/workflow_triggers.py` with `_PULL_REQUEST_TRIGGERS`, `PullRequestChange` and `starts_on_pull_request`, as design decisions 2 to 5 say. Delete `_runs_on_pull_request` and `_PULL_REQUEST_TRIGGERS` from `src/devops_cli/github/client.py`, and give `GitHubClient.pull_request_workflow_at` a `change: PullRequestChange` parameter that it gives to `starts_on_pull_request` for each workflow file
  - Verification: `$ uv run devops ci test tests/github/test_workflow_triggers.py`

## 2. The verdict gives the changed files to the workflow filters

Kind: behavior. Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`, `tests/support/fakes/github.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`.

- [x] 2.1 Write the failing tests. In `tests/github/test_merge_readiness.py`: a workflow whose `pull_request` event has `paths: [k8s/**]` gives `no_ci` for a pull request that changes only `README.md`, and a pending-check blocker for one that changes `k8s/app.yaml`; the same workflow keeps the pending-check blocker when the compare answer holds `CONST_GITHUB_COMPARE_FILES_LIMIT` files and none is under `k8s/`; a workflow that lists only `pull_request_target` keeps the pending-check blocker; the INFO advisory of no CI holds the new line. In `tests/commands/test_pr.py`: `pr ready` marks the pull request ready and exits 0 for the `README.md` case, and exits 8 and marks nothing for the `k8s/app.yaml` case; the no-CI tests assert the new line
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py`
- [x] 2.2 In `assess_merge_readiness`, read the changed files before `_judge_checks`. The new `_pull_request_change` builds the `PullRequestChange` from the payload and that read (the base branch, and the new and old path of each changed file, or None for an unread or truncated list), and `_judge_checks` gives it to `pull_request_workflow_at` through `_can_run_on_pull_request`. Change `readiness_no_ci` and `ready_no_ci` in `src/devops_cli/lang/en/messages.py` to the line of design decision 7, and the docstrings of `_can_run_on_pull_request`, `_judge_checks`, `_no_ci` and `_validate_pr_ready` to the new rule
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py tests/github/test_workflow_triggers.py`

## 3. State the rule in the help text

Kind: documents. Reads: `src/devops_cli/commands/pr.py`, `docs/commands/pr.md`. Changes: `src/devops_cli/commands/pr.py`, `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/MCP_TOOLS.md`, `.agents/skills/devops-pr-ci/SKILL.md`, `.claude/skills/devops-pr-ci/SKILL.md`, `.kilocode/skills/devops-pr-ci/SKILL.md`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 3.1 Change the docstring of `pr ready` in `src/devops_cli/commands/pr.py`: a head commit with no check waits for one unless no workflow at the head can start a check on the pull request, because none runs on a pull request or its branch and path filters skip it. Give step 6 of the three copies of the `devops-pr-ci` skill the same rule. Run `uv run devops docs generate`, which also writes the help text into `docs/commands/gh.md` and `docs/MCP_TOOLS.md`, and update the MCP tool listing snapshot with `uv run pytest -n 4 tests/ai/mcp/test_mcp_tool_listing.py --snapshot-update`
  - Verification: `$ uv run devops ci --check --only docs` passes, and `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
