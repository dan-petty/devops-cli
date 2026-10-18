# Task: The GitHub Session Owns Transport, Ledger, Error Classes and Link Pagination (#983)

**Issue**: [#983](https://github.com/dan-petty/devops-cli/issues/983)
**Status**: In Progress
**Milestone**: v0.2.37
**Priority**: priority/p1-high
**Scope**: scope/github
**Feasibility**: Read the gidgethub 6.0.0 wheel as locked. `gidgethub/httpx.py` imports `httpx2` before `httpx` and sends through the `httpx2.AsyncClient` it is given. `gidgethub/abc.py` awaits `handle_rate_limit_error(*, method, url, exception, attempt) -> bool` on every `HTTPException` and leaves the wait to the hook. `gidgethub/sansio.py`'s `RateLimit.from_http` reads `x-ratelimit-limit`, `-remaining` and `-reset` and returns None without all three, and `decipher_response` raises `RateLimitExceeded` only for a 403 with no quota left, `BadRequest` for a 429 and `GitHubBroken` for a 5xx. In httpx2 2.13.1, `URL.origin` is the scheme, lower-cased host and effective port, and `_send_handling_redirects` runs the request hooks before every hop. The plan's file and line references were rechecked at 30b8fdd: all still match except those in `config/constants.py`, whose symbols sit 459 lines lower, unchanged.

## Description

The process's GitHub session (#767) had a token, a login and PyGithub; two calls built their own `httpx2.Client`, and every other request went through `gh`. This item makes the session the transport: REST requests, `Link` pagination and conditional requests on gidgethub, one ledger for gh and the session, and one place that classifies failures. It is delivered as seven pull requests, in the order of the plan on the issue. [ADR 0006](../../adr/0006-github-session-requests-go-through-gidgethub.md) records the choice of gidgethub.

**The REST transport (this pull request).**

- **Dependency.** `gidgethub==6.0.0` is pinned in `pyproject.toml`; `uv.lock` gains it and `uritemplate` 4.2.0.
- **Session.** `GitHubSession.rest(method, path, *, accept=None, body=None)` returns the decoded answer: JSON as Python values, any other body as text. `GitHubSession(token, *, transport=None)` takes a transport in place of the factory's network transport, as the tests' fake does. The REST transport opens on the first request, and `close()` and `reset_github_session()` close it.
- **Transport.** `src/devops_cli/github/session_transport.py` holds `SessionGitHubAPI`, a subclass of `gidgethub.httpx.GitHubAPI`, and `RestTransport`, which owns one anyio blocking portal and the client on its loop. The client comes from `new_async_http_client(level=EgressLevel.PUBLIC)`, follows redirects, sends `CONST_GITHUB_API_VERSION` and carries one request hook, `refuse_other_origins`. The hook compares `request.url.origin` with the origin of `CONST_URL_GITHUB_API_BASE` and raises `GitHubUnreadError` naming the refused origin before anything is sent. gidgethub sends `CONST_GITHUB_USER_AGENT` as the User-Agent.
- **Pacing and ledger.** `_request` paces each attempt through `GitHubRateLimiter.acquire` in a worker thread, with the resource from `gh_request_resource(["api", path])` and `is_mutation` from `is_write_request`. `GET /rate_limit` is not paced (`gh_request_is_paced`, beside `gh_request_resource`). Each answer's quota, read with `RateLimit.from_http`, is charged to the resource `x-ratelimit-resource` names, or else to the paced one.
- **Retries.** `handle_rate_limit_error` retries a rate limit (`RateLimitExceeded`, a 429, a 403 with `retry-after`) up to `DEFAULT_GH_MAX_RETRIES` times. It waits what the ledger's new `retry_delay` gives, the rule `calculate_backoff_delay` now delegates to: the Retry-After, else until the quota resets, else jittered backoff from the secondary-limit floor. A 5xx is retried only for a read, from `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`, because GitHub may have applied a write it failed to answer. A refused connect and a refused origin are not retried. The wait is recorded with `record_throttle`, as `run_gh` records its own. `_parse_retry_after_safe` is now the public `parse_retry_after`, which the classifier reads Retry-After with.
- **Errors.** `GitHubScopeError`, `GitHubNotFoundError` and `GitHubUnreadError` are new subclasses of `GitHubOperationError`, with `CONST_GITHUB_SCOPE_ERROR_CODE`, `CONST_GITHUB_NOT_FOUND_ERROR_CODE` and `CONST_GITHUB_UNREAD_ERROR_CODE`. `GitHubFileNotFoundError` is now a `GitHubNotFoundError`, and `GitHubUnauthenticatedError` takes an `operation`. `src/devops_cli/github/error_classifier.py` maps gidgethub's exceptions by type, status and headers: a 401, a rate limit, a 403 whose `x-accepted-oauth-scopes` the token's `x-oauth-scopes` hold none of, a 404, and a 5xx or a 3xx left unfollowed. An httpx2 error or an undecodable body is `GitHubUnreadError`, and any other answer a plain `GitHubOperationError`. Every classified error carries the request path, at most 256 characters, and an answered one its status. The header names are constants in `config/constants.py`.
- **Callers.** `GitHubClient.get_pr_diff` is one `rest("GET", ..., accept=CONST_GITHUB_DIFF_MEDIA_TYPE)` call, and the redirect code that copied the token onto a github.com hop is gone. `_add_signing_key` takes the session, makes one `rest("POST", "/user/ssh_signing_keys", ...)` call and treats a 422 as already registered by its status.

## Acceptance Criteria

- [x] `rg -n "httpx2\.Client\(" src/devops_cli/github` and `rg -n 'is_redirect|netloc|urlparse|urllib|Authorization' src/devops_cli/github/client.py` print nothing.
- [x] Every request the session sends carries the session's token, `X-GitHub-Api-Version` and the constant User-Agent, and is paced and charged to the resource GitHub names: `test_a_get_carries_the_token_the_api_version_and_the_user_agent`, `test_a_response_charges_its_quota_to_the_resource_github_names` (core at 42, a response naming no resource, one naming another) and `test_a_post_is_paced_as_a_mutation_a_get_as_a_read_and_the_quota_read_not_at_all` in `tests/test_github_session.py`, over `httpx2.MockTransport`.
- [x] A 429 with `retry-after: 1` is retried once after a 1 s wait, three 502s raise `GitHubUnreadError` after two retries, and a write that gets a 502 is sent once (`test_a_429_with_retry_after_is_retried_once_after_that_wait`, `test_three_502s_raise_the_unread_error_after_the_retries`, `test_a_write_that_gets_a_502_is_not_sent_again`).
- [x] The session's client has one request hook comparing `request.url.origin` with the origin of `CONST_URL_GITHUB_API_BASE`, with no host tuple, `netloc` comparison, `startswith` or scheme-string test. The 2026-10-03 redirect table passes: a 301 to the moved repository, a relative `Location`, an upper-case host with `:443` and a 301 then a 307 are followed with the token on every hop (`test_redirects_on_the_api_origin_are_followed_with_the_token_on_each_hop`). A hop to example.com, to userinfo naming GitHub, to a look-alike host, to `http://` and to github.com raises `GitHubUnreadError` naming the origin with exactly one request recorded (`test_a_redirect_off_the_api_origin_is_refused_before_it_is_sent`).
- [x] `tests/test_github_errors.py` maps a 401, a 403 with no quota left, a 403 with `retry-after`, a 429, a 403 with a missing scope, a 403 with an accepted scope held, a 403 whose message says rate limit without its headers, a 404, a 422, a 5xx after the retries, a refused connect and an undecodable body to their classes, each with its status and path. No classification in `src/devops_cli/github/error_classifier.py` reads a response's message text.
- [x] `test_get_pr_diff_normal_and_redirect` (`tests/test_github_client.py`) and `test_add_signing_key` (`tests/test_github_ssh.py`) run over the shared fake; the signing key's 201 and 422 pass, and its missing scope and 5xx raise `GitHubScopeError` and `GitHubUnreadError`.
- [x] `reset_github_session()` stops the portal thread the session's requests ran on (`test_reset_closes_the_sessions_client_and_portal`).
- [x] Each new test's call phase is under 0.1 s, and none opens a socket or runs a real gh: the `github_api` fixture seeds the `core` quota, fails a test whose quota would need a `gh api rate_limit` refresh, and records the limiter's pauses and the retry waits instead of sleeping. Every quota header a test sends is built when the test runs, so its reset is still ahead however long the suite has been running.
- Later in #983 (PR 2): `session.paginate()` follows `rel="next"` page and cursor links, yields one flat sequence, stops when its consumer stops, raises `GitHubUnreadError` naming the endpoint and page for an empty, HTML, truncated or error-object page, and refuses a `Link` to another origin; the issue and milestone reads move onto it.
- Later in #983 (PR 3): the gh-output classifier over the `config/constants.py` table and exit code 4, and its callers; `tests/test_github_errors.py` gains the gh-output cases.
- Later in #983 (PR 4): the internal `--paginate` readers move onto `session.paginate()`, `run_gh` stops paging, and `run_gh_async`, `aiolimiter` and the page-loop helpers are deleted.
- Later in #983 (PR 5): the roadmap store's REST listings move onto the session.
- Later in #983 (PR 6): conditional requests through gidgethub's `cache=` with a bounded `cachetools` cache per session.
- Later in #983 (PR 7): the session fake moves under `tests/support/fakes/` with its contract suite, and that pull request, which closes the issue, adds `changelog.d/983.md`.
- Pending a person (live GitHub, read-only, after PR 4): `uv run devops gh api 'repos/dan-petty/devops-cli/issues?state=closed' --paginate -q '.[].number' | wc -l` prints more than 100.
- Pending a person (after PR 4): `uv run devops pr monitor <a PR with a Copilot review on its second timeline page>` reports the Copilot state, not `idle`.
- Pending a person (after PR 3): `GH_TOKEN=not-a-real-token uv run devops gh issues list -R dan-petty/devops-cli` exits 1 with the unauthenticated error and prints no issues.
- Pending a person (after PR 6): with one `devops serve` process polling, `uv run devops gh rate-limit --format json` read around two consecutive ticks shows the second tick spending fewer core requests than the first.

## Red Then Green

The new and rewritten tests were first run against the base source with only the new constants and error classes added. Every test that uses the `github_api` fixture errored, because `devops_cli.github.session_transport` did not exist and the session took no transport. `test_one_identity_reaches_pygithub_gh_and_the_quota_refresh` failed because the diff went out with `Authorization: Bearer A` from its own client. `test_register_with_token_api` failed because `_add_signing_key` was handed the token, not the session. After the change, all 70 tests in the four files pass.

## Deliverables

- [x] `docs/adr/0006-github-session-requests-go-through-gidgethub.md`.
- [x] `pyproject.toml` and `uv.lock`: `gidgethub==6.0.0`.
- [x] `src/devops_cli/github/session.py`: `rest()`, `close()`, the `transport=` argument, and `reset_github_session()` closing the session.
- [x] `src/devops_cli/github/session_transport.py`: `SessionGitHubAPI`, `RestTransport`, `refuse_other_origins`, `session_client`, `pace_request`, `charge_response` and `retry_wait`.
- [x] `src/devops_cli/github/error_classifier.py`: `classify_http_error`, `is_rate_limited`, `is_server_error`, `retry_after_seconds` and `missing_scopes`.
- [x] `src/devops_cli/github/rate_limiter.py`: `GitHubRateLimiter.retry_delay`, `gh_request_is_paced` and `parse_retry_after`.
- [x] `src/devops_cli/exceptions/git.py` and `src/devops_cli/exceptions/__init__.py`: `GitHubScopeError`, `GitHubNotFoundError`, `GitHubUnreadError`, `GitHubFileNotFoundError` under `GitHubNotFoundError`, and `GitHubUnauthenticatedError(operation=...)`, with the regenerated `docs/ERRORS.md`.
- [x] `src/devops_cli/config/constants.py`: the User-Agent, API version, diff media type, header names and three error codes. `src/devops_cli/config/defaults.py`: `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`.
- [x] `src/devops_cli/github/client.py` and `src/devops_cli/github/ssh.py`: the diff and the signing key on the session.
- [x] `tests/github_session_fakes.py` and the `github_api` fixture in `tests/conftest.py`.
- [x] `tests/test_github_session.py`, `tests/test_github_errors.py`, `tests/test_github_client.py` and `tests/test_github_ssh.py`.
- [x] `docs/agent/tasks/task-767-github-session-per-identity.md` names the header the diff now sends.

## Risks and Notes

- gidgethub sends `Authorization: token <token>`, where the old diff and signing-key code sent `Bearer`; GitHub accepts both for a personal access token or an OAuth token.
- A redirect to github.com is now refused. The old diff code followed one and copied the token onto it; nothing else in `src` sends the token to another GitHub host.
- A 5xx is retried for reads only. The plan says a 5xx is retried; a write is excluded because GitHub may have applied it, and `run_gh`, whose rules the retries follow, never retried a 5xx at all.
- The session's portal thread is a daemon thread, so a process that never resets its session still exits.
