# Design

## Cause

`CloudflareClient.list_access_applications` and `CloudflareClient.get_access_policies` issue a single `GET` request.
When the response spans multiple pages, they drop records beyond page 1.
Because `_ensure_access_application` checks for the target domain only within the returned list, it creates duplicate applications when the domain exists on a later page.
In addition, `_request` invokes `httpx2.Client.request` without retry logic.
Cloudflare rate limit responses (HTTP 429) or transient 5xx errors terminate the operation immediately.

## Fix

1. Add `_get_paginated(self, path: str, *, params: dict[str, Any] | None = None) -> list[Any]`.
   The helper iterates across pages starting at page 1.
   It supplies `page` in query parameters and reads `result_info.page` and `total_pages` from the response.
   When `result_info` is missing or `curr_page >= total_pages`, it terminates iteration.
   Update `list_dns_records`, `list_access_applications`, and `get_access_policies` to consume `_get_paginated`.
2. Add retry logic in `_request` using `tenacity.Retrying`.
   Configure `stop=tenacity.stop_after_attempt(DEFAULT_CLOUDFLARE_MAX_RETRIES)`.
   Configure `retry=tenacity.retry_if_result(_should_retry_response)`.
   The predicate returns `True` for HTTP 429 and status codes between 500 and 599.
   Other status codes, including HTTP 403, return `False`.
   Configure a wait strategy that inspects the `Retry-After` header when available.
   Pass `sleep=self._sleep` to `Retrying`, defaulting to `devops_cli.core.clock.sleep`.
3. In `CloudflareClient.__init__`, accept an optional `sleep: Callable[[float], None] = clock.sleep`.
   This enables tests to inject sleep functions directly.

## Test

1. Add tests in `tests/test_cloudflare_commands.py`:
   - `test_cloudflare_client_sync_access_application_finds_page_two_app`: verifies that `sync_access_application` finds an existing application on page 2 of a two-page response and creates nothing.
   - `test_cloudflare_client_get_access_policies_paginates_all_pages`: verifies that `get_access_policies` fetches and returns all policies across multiple pages.
   - `test_cloudflare_client_request_retries_429_with_retry_after`: verifies that an initial HTTP 429 with `Retry-After: 1` retries and succeeds on the subsequent HTTP 200 response without sleeping wall-clock time.
   - `test_cloudflare_client_request_does_not_retry_403`: verifies that an HTTP 403 error is not retried and raises `CloudflareAuthError`.
