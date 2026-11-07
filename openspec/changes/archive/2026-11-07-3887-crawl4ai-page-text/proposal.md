# Proposal

## Why

Issue #3887: no code in `src` fetches the text of a page for a model. `firecrawl_search` in `src/devops_cli/ai/common_tools.py` returns titles, URLs and descriptions only. The project plans a Crawl4AI service in namespace `devops`. It needs one client for that service. A model chooses the page URL, so the client is an SSRF and prompt-injection boundary (SECURITY.md rules 2 and 11).

## What Changes

- New module `src/devops_cli/ai/page_text.py` with `fetch_page_text(url, *, max_chars, settings)` and the result model `PageText` (`source_url`, `text`, `fetched_at`, `truncated`). It sends `POST {crawl4ai.url}/md` with the JSON body `{"url": <page>, "f": "fit"}` and the bearer token, through `http_client(level=EgressLevel.PRIVATE)`. The client follows no redirect and has a read timeout of `DEFAULT_CRAWL4AI_TIMEOUT_SECONDS`.
- The page URL is checked before any request. Only http and https pass (`InvalidURLError` otherwise). A host that `is_loopback_or_private_host` of `devops_cli.core.validation` refuses gives `SSRFBlockedError`. That predicate holds `is_non_public_ip` and `is_cloud_metadata_name`, and it also refuses a name that is not a public DNS name, such as `kubernetes.default.svc`. No IP or name list is written in the new code.
- The client reads at most `DEFAULT_CRAWL4AI_MAX_REPLY_BYTES` of a reply, and cuts the text at `max_chars` (default `DEFAULT_PAGE_TEXT_MAX_CHARS`) with `truncated` true.
- New setting `crawl4ai.url` (no default) and credential `crawl4ai.api_token` (alias `CRAWL4AI_API_TOKEN`, keyring `crawl4ai_api_token`, never in the config file). With either one empty, `fetch_page_text` raises `ConfigurationError` that names it, and sends nothing.
- New counter `devops_cli_crawl4ai_fetches_total{result}` with `ok`, the HTTP status of a refused fetch, or `error`. A failed fetch logs one warning with the status or the class of the failure, and never the token or the page URL. A page URL that the client refuses is no fetch and does not count.
- New error `PageTextError` (`PAGE_TEXT_ERROR`) with the HTTP status when the service gave one.
- `k8s/devops/configmap.example.yaml` names the cluster value `http://crawl4ai.devops.svc.cluster.local:11235`. The generated documents (`docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`, `docs/ERRORS.md`) list the setting, the credential, the counter and the error.
- No tool and no command use the client yet: #3890 and #3892 do that. Nothing is applied to the cluster. The cluster Secret row of the token is the work of #3882, which also names the credential; this change adds the credential row that the client needs to read it.
- The change adds behavior a consumer observes, so it carries a spec delta that creates the capability `crawl4ai-page-text`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `crawl4ai-page-text`: the text of a web page from the Crawl4AI service, with the checks on the page URL, the caps on the reply and the text, and the count of each fetch.

## Impact

- `src/devops_cli/ai/page_text.py` (new), `src/devops_cli/exceptions/ai.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`.
- `tests/ai/test_page_text.py` (new), `tests/fixtures/crawl4ai/md_response.json` (new).
- `k8s/devops/configmap.example.yaml`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`, `docs/ERRORS.md`.

## Feasibility

- The reply shape of `POST /md` was read from `deploy/docker/server.py` at Crawl4AI v0.9.5 (raw file at tag `v0.9.5`, read 2026-11-07). The handler `get_markdown` starts at line 616. It answers with `JSONResponse({"url", "filter", "query", "cache", "markdown", "success": True})` (lines 644 to 651). The fixture `tests/fixtures/crawl4ai/md_response.json` holds that shape.
- The request model `MarkdownRequest` in `deploy/docker/schemas.py` at v0.9.5 has `url`, `f` (`fit`, `raw`, `bm25` or `llm`, default `fit`), `q`, `c`, `provider` and `temperature`. The body `{"url", "f": "fit"}` is valid and uses no LLM.
- The handler refuses a URL that does not start with `http://`, `https://`, `raw:` or `raw://` with HTTP 400. `handle_markdown_request` in `api.py` calls `validate_url_destination` and `enforce_egress` before the crawl. The client refuses `raw:` itself, so the service never gets inline HTML from a model.
- Without `CRAWL4AI_API_TOKEN` the service binds loopback only (`deploy/docker/entrypoint.sh` at v0.9.5, lines 27 to 33), so a service in the cluster always has a token, and the client always sends one.
- `is_loopback_or_private_host` was run on the cases of the tests: IPv4 and IPv6 literals, a decimal IPv4 spelling, `localhost`, the metadata address and name, and cluster names.
- No Crawl4AI service runs yet (#3884 plans it). The client is built and tested against the HTTP fake and the v0.9.5 reply shape only. A live check of the destination rules of the service is #3894.

## Existing Tool Considered

- The project's `http_client` with its egress levels, the settings and credential registry, `service_base_url`, the OTLP instruments with `emit`, and the predicates of `devops_cli.core.validation`. The change builds one thin function over them and no new mechanism.
- Rejected: the Crawl4AI Python package in-process, because it brings Playwright and Chromium into the Service image. Rejected: the `web_fetch_tool` of `pydantic-ai`, because it fetches without a browser, so pages that need JavaScript fail, and the project removed its own copy of it.
- The change deletes no internal code.
