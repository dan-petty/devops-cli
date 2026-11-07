# Proposal

## Why

Web search has one backend in `main`: the hosted Firecrawl API, and the credit of its account ran out (HTTP 402). The DuckDuckGo fallback (#3876) keeps Firecrawl first, adds a second counter, and handles the second backend with a second `except` branch. A third provider, a local SearXNG (#3927), would add a third branch. The roadmap jobs need one entry point over a list of providers, so that a new provider is one class and one name (#3925).

## What Changes

- A new module `src/devops_cli/ai/web_search.py` holds `web_search(query, *, limit)`, the `SearchHit` (`url`, `title`, `snippet`, `provider`), the `SearchProvider` protocol (`name`, `url`, `configured(settings)`, `search(query, *, limit)`) and two providers: `DuckDuckGoProvider` and `FirecrawlProvider`. They are the functions `duckduckgo_search` and `firecrawl_search`, moved. `src/devops_cli/ai/common_tools.py` is deleted.
- `web_search` asks the providers of the new setting `search.providers` in order. It skips a provider that is not configured, and passes the search on at once, with no retry and no wait, when a provider fails or returns no hit. The first provider with a hit answers. It raises `SearchFailed` when no provider answered, and returns an empty list when some provider answered with no hit and the rest failed. A deadline of 60 s ends the chain. Each answer is deduplicated by its normalized URL and keeps only http and https URLs.
- A guard stops a query before any provider runs and raises `SearchQueryRefused`: an empty query, a query over 400 characters or 50 words, a query that starts with `!` or `:`, and a query that holds a secret, an e-mail address, a private address or an internal host name.
- New settings: the section `search` with `providers` (default `searxng`, `duckduckgo`, `firecrawl`; an unknown name is a validation error) and `language` (default `en`, sent as `Accept-Language`). The name `searxng` is listed and skipped until its provider exists (#3927).
- One counter `devops_cli_web_searches_total{backend,result}` replaces `devops_cli_firecrawl_searches_total` and `devops_cli_web_search_fallbacks_total`.
- The alert `RoadmapServiceFirecrawlRefused` becomes `RoadmapServiceWebSearchRefused` (by `backend` and `result`), and `RoadmapServiceAlternativesNotSearching` reads the new counter.
- `cited_web_search`, `InvestigationTools`, `AlternativesTools`, `WebSearch` and `web_search_of` lose the key argument. Web search is on for a public repository when at least one provider is configured. DuckDuckGo needs no key, so a public repository has web search with the default settings (owner decision of 2026-11-07). Firecrawl stays the last provider for one release cycle.
- `devops roadmap alternatives --dry-run` lists the request of the first configured provider.
- The change is observable in settings, a metric, an alert and the roadmap jobs, so it carries spec deltas for `web-search` (new), `roadmap-refine`, `roadmap-alternatives` and `roadmap-service-alerts`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `web-search`: The chain of providers, the query guard, the counter and the settings of web search

### Modified Capabilities

- `roadmap-refine`: Web search turns on by the providers, not by a Firecrawl key; the Firecrawl counter and the fallback requirements go
- `roadmap-alternatives`: The check is off without a configured provider; the dry run lists the first provider
- `roadmap-service-alerts`: The Firecrawl alert is renamed and reads the new counter

## Impact

- Code: `src/devops_cli/ai/web_search.py` (new), `src/devops_cli/ai/common_tools.py` (deleted), `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/exceptions/ai.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/ai/test_web_search.py` (new), `tests/ai/test_common_tools.py` (deleted), `tests/http/test_http_egress.py`, `tests/roadmap/`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml`
- Documents: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ERRORS.md` and `docs/TELEMETRY.md` (generated), `k8s/README.md`, `docs/roadmap/alternatives.md`, `docs/roadmap/refine.md`
- Manifests: the rules `RoadmapServiceWebSearchRefused` and `RoadmapServiceAlternativesNotSearching` in `k8s/monitoring/prometheus-values.yaml`
- Dependencies: none (`ddgs` stays)

## Feasibility

- The code to move exists in `main`: `duckduckgo_search` and `firecrawl_search` in `src/devops_cli/ai/common_tools.py` (read on 2026-11-07, at the commit that merged #3900). The module is moved and its callers are `cited_web_search` and `devops_cli.config`; `git grep` over `src` and `tests` lists every use.
- `ddgs` 9.16.1 gives the payload and the parse of the DuckDuckGo engine, and the request goes through `http_client(level=EgressLevel.PUBLIC)`, as the change of #3876 recorded. The test `test_the_duckduckgo_url_is_the_url_of_the_engine` fails if the URL of the engine changes.
- The Brave Search API is not a provider: the owner dropped it on 2026-11-07 (its terms forbid storing results, and it has no free tier). The chain has no keyed provider except Firecrawl.
- The provider `searxng` is the item #3927. This change lists the name in the default `search.providers` and skips it, because no provider class and no `search.searxng_url` exist yet. The settings text says so.
- Reading the key of Firecrawl through `get_firecrawl_api_key` reaches the keyring only for a provider that the search asks. A search that DuckDuckGo answers reads no key, and the dry run reads no key with the default providers.
- A query such as `macOS 10.15` is not an address: the guard reads only a full IP address (`ipaddress.ip_address`), and refuses an internal host name through `is_local_or_reserved_domain` of the secrets scanner, and a secret through `mask_secrets`.
- The cluster is not touched: the window and the one-model setting are deployed, and the Service reads the new settings from its image.

## Existing Tool Considered

The code of #3900 (`ddgs` engine parts through `http_client`) and `firecrawl_search` are moved, not rewritten. The `pydantic-ai` search tools take no transport, so they skip the egress check (the finding of the #3876 comment of 2026-11-07, SECURITY.md rule 2). No failover library is used: the rules are 40 lines, and the project HTTP entry point already gives timeouts and the egress check. For the guard, the change uses `mask_secrets`, the secrets scanner's `is_local_or_reserved_domain` and `is_private_or_local_ip`, `ipaddress`, and `email.headerregistry.Address` of the standard library. The change deletes `src/devops_cli/ai/common_tools.py`, `tests/ai/test_common_tools.py`, the two old instruments and the old alert. The written cost is about 40k tokens to build and keep, and 2 hours.

## Dependencies

None.
