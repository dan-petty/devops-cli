# Proposal: #5100

## Why

Since #4737, `devops gh api <endpoint> --paginate` reads a REST GET through the GitHub session. gh adds `per_page=100` to a paginated REST read when the endpoint does not set `per_page`, but the session path sends the endpoint as it is. GitHub then answers with its default page size of 30. A read with no `per_page` sends about 3.3 times more requests than gh, the `--jq` output of each page is different from the output of gh, and a listing of more than 3,000 items stops at the cap of 100 pages with `GitHubUnreadError`, where gh read it in pages of 100. Closes #5100.

## What Changes

- `session_path` in `src/devops_cli/github/api_pages.py` adds `per_page=100` (`DEFAULT_GH_REST_PER_PAGE`) to the endpoint when the first `per_page` of its query has no value, with the rule of gh 2.103.1 (`addPerPage` in `pkg/cmd/api/pagination.go`). An endpoint that sets `per_page` keeps it.
- The read and its dry-run plan use the same path, so the plan names the URL that the read sends.

The change alters the requests that a `devops gh api` command sends and the lines that it prints, which a consumer observes, so it has a spec delta.

## Capabilities

- `github-api-metrics` (MODIFIED requirement): a paginated `devops gh api` read of a REST GET counts each page, and asks for pages of 100 when the endpoint sets no `per_page`.

## Impact

- A paginated read with no `per_page` sends the number of requests that gh sent: for example, about 51 requests for 5,000 issues, not about 170.
- A listing of up to 10,000 items fits in the cap of 100 pages again.
- The `--jq` output of each page is the output of gh, because the pages are the pages of gh.
- The Service runs this code. No setting, manifest or dependency changes. The change fits one pull request.

## Feasibility

- Source, gh v2.103.1 `pkg/cmd/api/api.go`: `if opts.Paginate && !isGraphQL { requestPath = addPerPage(requestPath, 100, params) }`.
- Source, gh v2.103.1 `pkg/cmd/api/pagination.go`, `addPerPage`: it returns the path unchanged when `params` holds `per_page`, or when the text after the first `?` parses with `url.ParseQuery` and `Get("per_page")` is not empty. Else it appends `per_page=100` after `&` when the path has a `?`, or after `?`.
- Command output on main at a04e7a94c (v0.119.0 code), 2026-11-12: `devops gh api 'repos/dan-petty/devops-cli/labels' --paginate --jq length` printed `30`, `30`, `30` and `5` (4 requests).
- Command output, same day, on the gh path (the extra gh flag `-H 'Accept: application/vnd.github+json'` keeps the read with the installed gh): the same read printed `95` (1 request).
- Census, `git grep -n 'session_path(\|listing_text(' -- src`: `commands/gh.py` (2: the dry-run plan and the read) and `github/api_pages.py` (3: the two definitions and the call of `pages`). `GitHubSession.pages()` has one caller, `listing_text`. So the change reaches only `devops gh api --paginate`.

## Existing Tool Considered

- gh owns the rule. The session must send the request itself, because a gh walk counts as one request (#4737). The fix copies the rule of gh and cites its source.
- The Python standard library reads the query (`urllib.parse.parse_qs`) and writes the pair (`urllib.parse.urlencode`).
- Built: about 10 lines in `session_path`. Cost: about 60,000 tokens and 1 hour to build, and about 2,000 tokens a year to compare the rule with `addPerPage` when gh changes.
- The change deletes no internal code.
