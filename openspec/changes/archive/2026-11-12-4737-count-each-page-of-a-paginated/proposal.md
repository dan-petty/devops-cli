# Proposal: #4737

## Why

`run_gh` counts a gh command as one request with the status `none` (`_execute_gh_single_attempt` and `count_request` in `src/devops_cli/github/rate_limiter.py`). gh walks every `Link` page of `gh api --paginate` in one process, so a walk of 7 pages counts as 1 request. `devops gh api --paginate` sends all its reads this way, so the GitHub request panels undercount by an amount that nobody can measure. Closes #4737.

## What Changes

- `devops gh api --paginate` reads a REST GET listing through the GitHub session. The session paces each page, counts each attempt with the status of its answer and sends a page it holds an answer for with `If-None-Match` (#3497). A listing of 4 pages adds 4 to `devops_cli_github_requests_total`.
- gh keeps the paginated reads that the session does not send as gh does: GraphQL, a write, an endpoint with a gh placeholder (`{owner}`, `:repo`), a full URL, `--template`, `--cache` and any other gh flag, such as `--slurp`.
- `--jq` runs on each page through jq.py, the Python binding of jq, and prints each value as gh 2.103.1 prints it.
- `GitHubSession.pages()` gives each page of a REST listing whole: an array, or an object such as a search answer. `paginate()` and `pages()` share one walk with the same page cap.
- A dry run of a session read lists its `GET` and URL, repeated for each page.
- The metrics row taxonomy read stays on `GhCliClient.api(paginate=True)`, because #3941 moves it to the session and removes the second listing. The scoped intake read stays with #3670. The rate-limit gauges stay with #4752.

The command counts its requests in another way and prints through another path, which a consumer observes, so the change has a spec delta.

## Capabilities

- `github-api-metrics` (modified, ADDED requirement): a paginated `devops gh api` read of a REST GET counts each page.

## Impact

- The count of an agent's paginated REST reads goes up to the number of pages. The Service sends no `devops gh api` command.
- A REST listing past `DEFAULT_GH_MAX_PAGINATED_PAGES` (100) pages fails with `GitHubUnreadError` naming the cap. gh had no cap.
- A new runtime dependency, `jq==1.13.0` (BSD-2-Clause). It has wheels for CPython 3.14 on Linux (glibc and musl), macOS and Windows.
- No setting or manifest changes. The change fits one pull request.

## Feasibility

- Source: `_execute_gh_single_attempt` calls `count_request(target_resource, method, None, ...)` once for each gh process, and `_calculate_effective_cost` gives 1 or 2 with no regard to `--paginate`.
- Command output, 2026-11-12: `devops gh api 'repos/dan-petty/devops-cli/issues?state=open&per_page=100' --paginate --jq length` printed 7 lines (6 of 100 and one of 7), so gh read 7 pages in one counted request.
- Source: `SessionGitHubAPI._request` in `src/devops_cli/github/session_transport.py` calls `count_request` with the status of each attempt, and `GitHubSession.paginate` reads one page for each request.
- Command output with the change, 2026-11-12: the same read through the session printed 7 lines of the same form.
- gh 2.103.1 output, 2026-11-12: `devops gh api meta --jq '"str", null, true, 1.5, 0.125, 3, {"b":1,"a":"x"}'` printed `str`, an empty line, `true`, `1.50`, `0.12`, `3` and `{"a":"x","b":1}`. The new printer gives the same lines.
- Census, `git grep -n -- --paginate src` after the change: `commands/gh.py` (3: the option, the argv of the reads that gh keeps, the gh walk timeout), `github/api_pages.py` (the module text), `github/client.py` (2: `GhCliClient.api` for the metrics taxonomy read of #3941, and the text of `parse_paginated_json`), `github/metrics.py` (1: the dry-run line of that read, #3941), `config/constants.py` (1: the argv parser table), `config/defaults.py` (1: the text of the gh walk timeout) and `github/request_classifier.py` (1: text). Only `commands/gh.py` and the #3941 read send a gh walk.

## Existing Tool Considered

- The GitHub session (#983, ADR 0006, gidgethub 6.0.0) reads the pages. It already paces, counts, retries and sends conditional requests.
- jq.py 1.13.0 (BSD-2-Clause, released 2026-10-18, PyPI and github.com/mwilliamson/jq.py) runs the `--jq` filter. gh runs gojq, so a filter keeps the jq language.
- Built: the printer of the values a filter gives, as gh prints them (about 40 lines). Cost: about 150,000 tokens and 2 hours to build, and about 10,000 tokens a year to keep it equal to gh's output.
- The change deletes no internal code. `GhCliClient.api(paginate=True)` and `parse_paginated_json` go with #3941.
