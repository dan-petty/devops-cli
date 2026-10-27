# Tasks

## 1. The reader of one issue

- [x] 1.1 Write the failing tests in `tests/test_github_issues.py` with the `github_api` fake: `get_repository_issue` returns the parsed issue for `GET /repos/octo/repo/issues/9999`; a 404 raises `GitHubNotFoundError` with the repository and the number in the message; a 5xx raises `GitHubUnreadError`; an answer that is no issue object raises `GitHubUnreadError`; an answer with a `pull_request` key raises `GitHubOperationError` that names `devops pr view 12`. Verify: `uv run devops ci test tests/test_github_issues.py` fails because `get_repository_issue` does not exist.
- [ ] 1.2 Add `get_repository_issue` and `render_issue` to `src/devops_cli/github/issues.py`. Verify: `uv run devops ci test tests/test_github_issues.py` passes.

## 2. The command

- [x] 2.1 Write the failing tests in `tests/test_gh_cmd.py`: `issues view 9999 -R octo/repo` prints the whole long title, every field and every body line; empty fields show a dash; a title with Rich markup prints as written; a missing issue and a pull request number exit 1 with the messages of the spec. Add `gh_issues_view` to the expected tools in `tests/test_fastmcp_contracts.py`. Verify: `uv run devops ci test tests/test_gh_cmd.py tests/test_fastmcp_contracts.py` fails because the command does not exist.
- [ ] 2.2 Add `devops gh issues view` to `src/devops_cli/commands/gh.py` and `HELP.gh.issues_view` to `src/devops_cli/lang/en/help.py`. Verify: `uv run devops ci test tests/test_gh_cmd.py tests/test_fastmcp_contracts.py` passes.
- [ ] 2.3 Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and `docs/CLI_REFERENCE.md` lists `devops gh issues view`.

## 3. The real host

- [ ] 3.1 Run `uv run devops gh issues view 2361`, then `uv run devops gh issues view 99999`, then `uv run devops gh issues view <the number of a pull request>` in this repository. Verify: the first prints the whole issue, and the other two exit 1 with the messages of the spec.
- [ ] 3.2 Run the full `uv run devops ci --check --no-cache` in the worktree. Verify: every check passes.

## Workflow follow-up

- Issue comments and a JSON output for `issues view` are not part of this item. A reader that needs them files a separate item.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
