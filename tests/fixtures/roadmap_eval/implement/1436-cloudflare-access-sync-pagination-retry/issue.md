## Problem
Lines cited at 05e9388 (`release/v0.2.29`).

- **Access listings read only the first page.**
  - `list_access_applications` (`cloudflare/client.py:627-637`) reads only the first page of `accounts/{id}/access/apps`. `get_access_policies` (`:660-670`) does the same for `.../policies`.
  - Both endpoints are paginated; the official SDK types them as `V4PagePaginationArray`.
  - `_ensure_access_application` (`:672-690`) looks for the domain on that first page and creates the application when it is not there. An account with more applications than one page holds therefore gets a duplicate.
- **Only the DNS listing paginates** (`list_dns_records`, `:361-386`, with `_is_last_dns_page`, `:241-246`).
- **Nothing is retried.** `_request` (`:272-295`) has no retry, so a 429 from Cloudflare's API rate limit or a transient 5xx fails a sync midway.
- **The official SDK (`cloudflare` 5.9.0) is not a fit.** Its `http_client` must be an `httpx.Client`: `_base_client.py:916` checks the type. This project's egress-checked clients are httpx2 clients (#898, #1314).

## Proposed remedy
- **Pagination.** One paginated GET helper over `result_info.page` and `total_pages`, used by the DNS records, Access applications and Access policies listings.
- **Retries.** Retry 429 and 5xx with tenacity (already a dependency), honouring `Retry-After`, with a bounded attempt count. A 4xx other than 429 is not retried.

## Acceptance criteria
- [ ] With an existing application on page 2 of a two-page answer at the HTTP fake, `sync_access_application` finds it and creates nothing.
- [ ] Access policies spread over two pages are all returned.
- [ ] A 429 with `Retry-After: 1` followed by a 200 succeeds without a real sleep: the test injects tenacity's sleep.
- [ ] A 403 is not retried.
- [ ] Dummy hosts in tests are exactly `example.com`.
- [ ] Tests run offline with fakes only at process and HTTP edges; each new test runs under 1 s.
- [ ] `uv run devops ci` passes.

Related: #1335 (this client moves onto the egress factory), #1314, #1327.

Found by the 2026-10-08 client-library audit.

Opened as a borrow (#1153, `budget/borrowed`): the agent filing quota is spent for this cycle, and this is a defect or security finding of the owner-requested 2026-10-08 client-library audit.
