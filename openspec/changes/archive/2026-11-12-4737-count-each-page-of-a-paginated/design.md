# Design

## Decisions

- **The session reads a REST GET listing.** `reads_through_session` in the new module `src/devops_cli/github/api_pages.py` takes the endpoint, the method, the template, `--cache` and the other gh flags. It is true only for a GET of a path with no gh placeholder, no template, no `--cache` and no other gh flag. The command then prints `listing_text`. Every other read goes to gh as before, with the gh walk timeout `DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS`.
- **One walk in the session.** `GitHubSession._follow` follows `rel="next"` from page 1 up to the page cap. `paginate()` reads the items of each page through `RestTransport.page`, and `pages()` reads each page whole through `RestTransport.read_page`. `SessionGitHubAPI.page` now calls `read_page` and checks the items. An empty array is the last page in both.
- **Print as gh prints.** With no filter, the items of array pages print as one compact JSON array, as gh joins the pages of an array listing. Each object page prints on its own line. With `--jq`, the filter runs on each page, as in gh, and each value prints by gh's rules (go-gh `jsonScalarToString`): a string as text, null as an empty line, a boolean, a whole number with no decimals, any other number with two, and an array or an object as compact JSON with sorted keys.
- **A bad filter reads no page.** The filter compiles before the first page is read, and a compile error raises `ValidationError`. A filter that fails on a page raises `ValidationError` naming the page, after the earlier pages printed.
- **Errors keep their class.** A failed page raises the `GitHubOperationError` subclass of the session, and the command exits with its exit code. The output passes through `mask_secrets`, as the gh output does.

## Rejected alternatives

- **Count the pages of the gh walk.** gh writes no page count. `--include` puts the headers of each page into stdout, mixed with the `--jq` output, and `GH_DEBUG=api` writes each body to stderr. Neither is a stable interface, and both keep the walk unconditional.
- **Page by gh, one gh process for each page.** It needs a `Link` parser over gh's `--include` output and sends no conditional request. ADR 0006 removed such a page loop.
- **Keep gh when `--jq` is given.** In the agent transcripts of the workspace, 899 of 2,028 `gh api ... --paginate` lines carry `--jq`, the largest share, so the undercount stays.
- **Fill `{owner}` and `{repo}` from the git origin.** gh chooses its base repository from `GH_REPO`, the default that `gh repo set-default` keeps, and the remotes. The git origin can name another repository, so gh keeps these reads.
- **Apply the filter to the joined listing.** gh runs it on each page, so `length` prints one count for each page. The same filter must print the same lines on both paths.
