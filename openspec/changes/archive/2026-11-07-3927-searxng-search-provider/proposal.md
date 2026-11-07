# Proposal

## Why

The chain of web search providers (#3925) lists `searxng` and skips it, because no provider class exists. The project runs no search service of its own: Firecrawl answers HTTP 402, and DuckDuckGo has no second path. SearXNG (manifest item #3924) is a keyless search service that the cluster will run. The chain needs a client for it (#3927).

## What Changes

- A new class `SearxngProvider` in `src/devops_cli/ai/web_search.py`, with the name `searxng`, listed in `PROVIDERS`. It sends `GET {search.searxng_url}/search` with `q`, `format=json`, `language` (from `search.language`), `categories` and `pageno=1`, through `http_client(level=configured_level(...))`. A loopback address needs no flag; a cluster Service address needs `ai.allow_private_network`.
- The client follows no redirect. SearXNG answers a query that starts with `!` with a redirect, so a redirect is a failure with its status as the result. A reply with another status than 200 is a failure with its status as the result. The client reads at most 1 MiB; a larger reply is `degraded`.
- The provider maps each item of `results` to a `SearchHit` with the provider `searxng`. An empty `results` with a non-empty `unresponsive_engines` is `degraded`; an empty `results` with an empty `unresponsive_engines` is `empty`.
- New setting `search.searxng_url` (variable `DEVOPS_CLI_SEARCH_SEARXNG_URL`) with no default. Without it the provider is not configured and the chain skips it. A direct call raises `ConfigurationError` that names the setting.
- `SearchProvider` gains `method`, and the dry run of `devops roadmap alternatives` lists the method of the first configured provider (`GET` for SearXNG, not always `POST`).
- An address that the egress check refuses (`SSRFBlockedError`) passes the search on and counts as `refused` for the provider, as a failed provider does. Without this, a cluster address with the flag off would stop the whole search before DuckDuckGo.
- `k8s/devops/configmap.example.yaml` names the cluster address, and `k8s/README.md` and the generated settings documents describe the setting.
- The change is observable in a setting, a metric result and a dry run, so it carries a spec delta for `web-search`.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `web-search`: The SearXNG provider, its request, its failure rules and the setting `search.searxng_url`

## Impact

- Code: `src/devops_cli/ai/web_search.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/telemetry/instruments.py`
- Tests: `tests/ai/test_web_search_searxng.py` (new), `tests/fixtures/searxng/search_reply.json` (new), `tests/ai/test_web_search.py`, `tests/roadmap/test_roadmap_dry_runs.py`
- Documents: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md` (generated), `k8s/README.md`, `k8s/devops/configmap.example.yaml`
- Dependencies: none

## Feasibility

- The API: the SearXNG document `docs/dev/search_api.rst` at commit 629368e40 (the commit of the pinned image `2026.10.23-629368e40`), read on 2026-11-07, says that `GET /search` takes `q`, `categories` (comma separated), `language`, `pageno` and `format`, and that a format that `search.formats` does not list answers HTTP 403.
- The engines that the manifest keeps (`searx/settings.yml` at that commit) sit in the categories `general` (wikipedia, duckduckgo), `it` (stackoverflow, askubuntu, superuser, mdn, docker hub, github, pypi) and `science` (arxiv). The provider asks for `general,it,science`. This is read from the engine files, not from a live pod.
- NOT RUN: a live query. The SearXNG manifests (#3924) are not in `main`, so no pod exists. The reply fixture holds the shape that the API document gives, not a saved reply. The live check (#3929) must replace the fixture with a reply saved from the pinned digest and must check the categories; this change moves that criterion to #3929.
- The redirect: `searx/webapp.py` answers with a redirect when `result_container.redirect_url` is set, which a bang query causes (researcher, 2026-11-07). The test `test_a_redirect_is_a_failure_and_no_second_request_is_sent` holds the client to it. The query guard already refuses a query that starts with `!` or `:`.
- `configured_level` gives loopback, or private with `ai.allow_private_network`. The tests in `tests/ai/test_web_search_searxng.py` show a loopback address works with the flag off and a cluster address needs it.
- The Brave Search API and the `allows_keep` flag are not part of the design (the owner dropped them on 2026-11-07).

## Existing Tool Considered

The project's `http_client` and `configured_level`, `service_base_url`, and the SearXNG JSON API. Rejected: a Python SearXNG client package (none read; the call is one request and one JSON object) and the `pydantic-ai` search tools (they take no transport, so they skip the egress check). The written cost is about 25k tokens to build and keep, and 1 hour.

## Dependencies

None for the code. The manifest item #3924 deploys the service, and the live check #3929 holds the fixture to a real reply.
