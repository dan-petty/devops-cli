# Tasks

## 1. Behavior: the session gives each page whole

- [x] 1.1 Write failing tests: `pages()` gives each array or object page in link order, an empty array is the last page, and the page cap holds
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py`
- [x] 1.2 Add `RestTransport.read_page` and `GitHubSession.pages`, and walk `paginate` and `pages` through one loop
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py`

## 2. Behavior: devops gh api --paginate reads REST pages through the session

- [x] 2.1 Write failing tests: the reads the session sends, the reads gh keeps, the printed pages and the `--jq` values, and a bad filter
  - Verification: `$ uv run devops ci test tests/github/test_github_api_pages.py`
- [x] 2.2 Write failing command tests: 4 pages add 4 to `devops_cli_github_requests_total`, `--jq` runs on each page, a 404 exits 1, and a dry run plans the `GET`
  - Verification: `$ uv run devops ci test tests/commands/test_gh_cmd.py`
- [x] 2.3 Add `src/devops_cli/github/api_pages.py` with jq.py 1.13.0, and route `devops gh api --paginate` through it
  - Verification: `$ uv run devops ci test tests/github/test_github_api_pages.py tests/commands/test_gh_cmd.py`

## 3. Documents

- [x] 3.1 State the session read of `devops gh api --paginate` in ADR 0006 and in the `devops_cli_github_requests_total` row of `docs/TELEMETRY.md`, and generate the command reference
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The metrics row taxonomy read and `GhCliClient.api(paginate=True)` move to the session in #3941.
- The rate-limit gauges that a panel compares with the counted requests come with #4752.
- Pending a person: after #4752 is live, compare one hour of the counted core requests with status other than 304 with the last value of `devops_cli_github_rate_limit_used` for core before the GitHub window reset.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
