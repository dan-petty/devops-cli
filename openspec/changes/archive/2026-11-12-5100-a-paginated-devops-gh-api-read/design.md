# Design

## Decisions

- **Add the page size in `session_path`.** The read (`listing_text`) and the dry-run plan of `devops gh api --paginate` both use `session_path`, so the plan names the URL that the read sends. `GitHubSession.pages()` stays a reader of the path it gets: the rule is a rule of `gh api`, not of the session.
- **Copy each step of `addPerPage` (gh v2.103.1, `pkg/cmd/api/pagination.go`).** The path splits at its first `?`, as `strings.IndexRune` splits it. `urllib.parse.parse_qs` with `keep_blank_values=True` reads the query, and the check takes the first value of `per_page`, as Go's `url.Values.Get` gives it. A first value that is empty, or a `per_page` with no `=`, does not count as set, as in gh. The pair goes after `&` when the path has a `?`, else after `?`, so the path is the path of gh, also for an endpoint that ends in `?`. `urlencode` writes the pair.
- **The page size is `DEFAULT_GH_REST_PER_PAGE` (100).** gh writes the same number (`addPerPage(requestPath, 100, params)` in `pkg/cmd/api/api.go`).
- **The `params` step of gh does not apply.** gh keeps a `per_page` given with `-f` or `-F`. `reads_through_session` gives each read with a gh flag to gh, so the session never gets such a read.

## Rejected alternatives

- **Read and write the path with `urlsplit` and `urlunsplit`.** `urlunsplit(urlsplit('/repos/o/r/labels?'))` gives `/repos/o/r/labels`: the empty query and its `?` go. The path would then be `labels?per_page=100`, not the `labels?&per_page=100` of gh. `urlsplit` also moves a `#` fragment out of the query, which gh does not do.
- **Copy the parse errors of Go's `url.ParseQuery`.** gh adds `per_page=100` also when Go cannot parse the query (a `;` in it, or a `%` with no two hex digits after it), even when the query sets `per_page`. `parse_qs` reads such a query with no error, so the session keeps the `per_page` of the endpoint there. To copy gh, the module needs a written copy of the parse rules of Go. httpx2 sends such a query as it is typed (`httpx2.URL('https://api.github.com').join('/repos/o/r/issues?q=%zz;x&per_page=5')` keeps it), so the only difference is the second `per_page` that gh appends to an endpoint that sets `per_page` and also holds a query that Go refuses. The cost of a written parser is more than the value for such an endpoint.
- **Use `listing_path` of `roadmap/stores/github_store.py`.** It appends `per_page` to every endpoint after a check for `?` in the text, so an endpoint that sets `per_page` gets a second one. Its callers build the endpoint and know that it sets no `per_page`, so it does not need the rule of gh.
- **Add the page size in `GitHubSession.pages()` or `RestTransport.read_page`.** The session reads the path that its caller gives. A caller that wants another page size would have no way to ask for it, and the rule of `gh api` would move into code that is not about `gh api`.
