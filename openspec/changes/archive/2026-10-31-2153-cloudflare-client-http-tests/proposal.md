# Proposal: Cloudflare Client HTTP Edge Tests

## Why

Issue #2153 addresses untested write and error paths in `src/devops_cli/cloudflare/client.py`.
1. `src/devops_cli/cloudflare/client.py` has 97 missed statements in test coverage. Its write operations for Access applications, Access policies, DNS record creation, update, and deletion, and tunnel configuration reads and updates lack end-to-end HTTP tests.
2. The client instantiates `new_http_client` directly inside each request without allowing an injected transport parameter, which previously prevented tests from providing custom transports without monkeypatching.
3. Tests in `tests/commands/test_cloudflare_commands.py` patch `httpx2.Client.request` and client methods, which violates the testing rule that tests double only external process edges.
4. Repetitive account and zone requirement checks across 14 methods duplicate logic rather than using shared helpers.

## What Changes

- Add a `transport` parameter to `CloudflareClient.__init__` and pass it to `new_http_client(level=EgressLevel.PUBLIC, read_timeout=30.0, transport=self._transport)`.
- Consolidate account ID and zone ID checks in `CloudflareClient` into `_require_account` and `_require_zone` helper methods.
- Add comprehensive HTTP-level unit tests in `tests/cloudflare/test_client.py` using `httpx2.MockTransport`:
  - Access application creation.
  - Access policy creation and updates with allowed emails and bypass CIDRs.
  - Access policy validation refusing invalid CIDR specifications.
  - DNS record creation, update, deletion, and reconciliation logic in `sync_dns_records`.
  - Tunnel identification resolution, configuration read, and configuration update.
  - HTTP error handling, 4xx/5xx responses, and error message extraction.
  - Parametrized tests for `_require_account` and `_require_zone` covering all 14 dependent public methods.
- Verify request objects and whole return values using `example.com` domains.
- Increase coverage of `src/devops_cli/cloudflare/client.py` above 85% and pass all CI checks.

## Feasibility

- `new_http_client` in `src/devops_cli/http/client.py` already supports the `transport` parameter. Passing it through `CloudflareClient.__init__` enables clean transport injection.
- `httpx2.MockTransport` is part of `httpx2` and allows simulating arbitrary HTTP responses without network calls or monkeypatching.
- The 14 account and zone check sites are internal to `CloudflareClient` and map directly to `self._require_account()` and `self._require_zone()`.

## Existing Tool Considered

- `httpx2.MockTransport` is the standard mock transport for `httpx2`. Using it avoids third-party HTTP mocking libraries or monkeypatching `httpx2.Client.request`.
