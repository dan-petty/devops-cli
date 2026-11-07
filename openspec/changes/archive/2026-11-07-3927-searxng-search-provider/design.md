# Design

## Decisions

- **One class, one setting.**: `SearxngProvider` follows the protocol of the chain, so the chain code changes in one place only (see the next decision). `configured` is true when `search.searxng_url` is set.
- **Add `method` to the protocol.**: The dry run printed `POST` for the first provider. SearXNG searches with `GET`, so each provider names its method, and `url` is a property for the provider whose address comes from the settings.
- **A refused address passes the search on.**: `SSRFBlockedError` is not an `httpx2.HTTPError`. A cluster address with `ai.allow_private_network` off would end the whole search with an exception, and DuckDuckGo would never run. The chain counts it as `refused` with a warning that holds the error class, and goes on.
- **Stream the reply and cap it.**: The same rule as the Crawl4AI client: the body is read in chunks and refused at 1 MiB. A SearXNG reply holds about 20 results, so the cap leaves room.
- **Categories `general,it,science` as a constant.**: The kept engines answer in these categories (see Feasibility). A setting would add a key that no one has a reason to change before the live check shows the real behavior.
- **`degraded` for a silent engine.**: SearXNG reports a suspended engine only in `unresponsive_engines`. An empty list of results with that field set is a failure of the engines, not an answer, so the chain counts `degraded` and goes on. With hits, the hits answer.
- **No redirect, no retry.**: `follow_redirects=False`. HTTP 3xx fails through `raise_for_status`, and its status is the result.

## Rejected alternatives

- **A SearXNG client package.**: None read. The call is one `GET` and one JSON object.
- **`allows_keep` on the provider.**: It existed for the Brave terms. The owner dropped Brave on 2026-11-07, and every provider's hits may be kept.
- **A default address for the setting.**: A default would send queries to a host that may not exist (no unconfigured fallback).
