# Design

## Decisions

- **Put the chain in `src/devops_cli/ai/web_search.py` and delete `common_tools.py`.**: The new module holds the entry point, the providers, the guard and the counter. `common_tools.py` would hold nothing else.
- **A provider is a class with `name`, `url`, `configured(settings)` and `search(query, *, limit)`.**: A provider with a key needs only a new class and a name in `PROVIDERS` and in `SearchProviderName`. `url` lets the dry run list the request without a request.
- **A provider raises `httpx2.HTTPError` or `ValueError` and `web_search` classifies it.**: A status error counts as its HTTP status, another `httpx2.HTTPError` as `error` (no answer), and a `ValueError` as `degraded` (a reply that is not readable, such as DuckDuckGo's HTTP 202 page). The chain has one place that counts and logs.
- **Skip a listed name that has no provider.**: `searxng` is in the default list, and its provider is the item #3927. The skip is the same as for an unconfigured provider, so that item adds a class and nothing else.
- **Check the providers lazily.**: `iter_configured_providers` yields a provider only when the loop asks for it, so a search that DuckDuckGo answers reads no Firecrawl key from the keyring, and the dry run reads none with the default list.
- **A healthy empty reply passes the search on.**: The first provider with at least one hit wins. When one provider answered empty and the rest failed, the result is an empty list, because a provider did answer. When none answered, `SearchFailed` is raised.
- **The deadline is checked before each provider.**: Each provider has its own timeout (15 s and 30 s), so the sum stays under 60 s today. The check keeps the bound when a later provider adds more time.
- **Count with one counter, `devops_cli_web_searches_total{backend,result}`.**: `backend` is a provider name, or `none` for a refused query and for a search that no provider answered. The old counters named Firecrawl, and a second counter for each provider would repeat the problem.
- **Reuse the secrets scanner for the guard.**: `mask_secrets` finds a secret, `is_local_or_reserved_domain` an internal host name, and `is_private_or_local_ip` a private address. Only a full address counts: the legacy spelling `10.15` of `inet_aton` would refuse a query about a software version.
- **Send `search.language` as `Accept-Language`.**: DuckDuckGo and Firecrawl take no language parameter in the requests of this change, and the header is the standard way. SearXNG (#3927) reads the setting for its own parameter.
- **Turn web search on for a public repository when one provider is configured.**: The owner decided on 2026-11-07 that keyless DuckDuckGo may turn web search on by itself. The earlier change (#3876) left this open.
- **Keep Firecrawl last.**: The owner decided on 2026-11-07 that Firecrawl stays the last provider for one release cycle.
- **Rename the alert to `RoadmapServiceWebSearchRefused` and group it by `backend` and `result`.**: Any provider can answer 402 or 429, and the page must name which one.

## Rejected alternatives

- **The Brave Search API as a first provider.**: The owner dropped it on 2026-11-07: its terms forbid storing results and it has no free tier.
- **The `pydantic-ai` search tools.**: They take no transport, so the request skips the egress check (SECURITY.md rule 2).
- **A failover or retry library.**: The rules are about 40 lines. A retry would add a wait, and the issue asks for a pass-on at once.
- **Keep `devops_cli_firecrawl_searches_total` and add a `backend` label.**: A series of that name would count the searches of other providers, and the meaning of the name would change. The issue asks for one counter and no shim.
- **A regular expression for the e-mail address.**: `email.headerregistry.Address` of the standard library reads an address, and the repository avoids a home-grown parser when a library has one.
