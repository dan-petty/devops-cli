# Design

## Decisions

- **One function over the existing `http_client`.** `fetch_page_text` in `src/devops_cli/ai/page_text.py` builds an unpooled client at `EgressLevel.PRIVATE`: the service is internal, and the page host is checked by the function itself because the page URL is a body field and no connect of this client reaches it. An unpooled client follows no redirect, so a redirect from the service ends the fetch.
- **`is_loopback_or_private_host` for the page host.** It already holds `is_non_public_ip`, `is_cloud_metadata_host` (which holds `is_cloud_metadata_name`), the legacy IPv4 spellings and the public DNS name test. The new code holds no list and no regex. A public name that resolves to a private address passes this check; the service pins the address it dials and refuses it (Crawl4AI `egress_broker`), and #3894 tests that.
- **Stream the reply and count bytes.** The client reads chunks and stops at `DEFAULT_CRAWL4AI_MAX_REPLY_BYTES`, so a large page cannot fill memory. This is the same loop as `fetch_registry_ruleset` in `src/devops_cli/security/semgrep_registry.py`.
- **Two caps.** The byte cap protects the process. The `max_chars` cap protects the model context, and `truncated` tells the caller that the text is partial.
- **`source_url` is the requested URL.** The reply names a `url` too, but it is data from the service. The result never takes the URL from it.
- **A refusal of the page URL is no fetch.** It raises before any request and does not count in `devops_cli_crawl4ai_fetches_total`, so the alert of #3893 on failed fetches does not fire on a bad model argument.
- **The setting is a plain `HttpUrlStr`.** The cluster value is an HTTP Service address (`http://crawl4ai.devops.svc.cluster.local:11235`). A `k8s://` address is not accepted: the CLI reaches the service through the tunnel host, as the project's rule for cluster services says.
- **The credential is not in the config file.** `Credential("crawl4ai.api_token")` has `in_file` false: the keyring, a variable or Vault holds it.

## Rejected alternatives

- **The Crawl4AI Python package in-process.** It brings Playwright and Chromium into the Service image (issue #3887).
- **`web_fetch_tool` of `pydantic-ai`.** It fetches without a browser, so JavaScript pages fail (issue #3887).
- **A second IP and name check in the new module.** `is_loopback_or_private_host` exists, and a home-made check is a major finding in this project.
- **Count a refused page URL as `error`.** It is a bad argument and not a failed fetch, and it would make the failed-fetch alert fire on model mistakes.
- **A pooled client with redirects.** A pooled client follows redirects by default; the service answers the call and a redirect from it is not expected.
