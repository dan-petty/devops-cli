## 1. Transport Injection and Helpers

- [x] 1.1 Add `transport` parameter to `CloudflareClient.__init__` and pass it to `new_http_client`
- [x] 1.2 Implement `_require_account` and `_require_zone` helpers and consolidate the 14 check sites

## 2. HTTP Edge Tests

- [x] 2.1 Write failing tests first in `tests/cloudflare/test_client.py` for Access applications, policies, DNS, tunnels, and error paths
- [x] 2.2 Verify tests pass through real `CloudflareClient` methods with `httpx2.MockTransport`
- [x] 2.3 Verify `_require_account` and `_require_zone` coverage across all 14 dependent methods

## 3. Verification and CI

- [x] 3.1 Verify coverage of `src/devops_cli/cloudflare/client.py` increases above 85%
- [x] 3.2 Run fast checks, full CI, and archive OpenSpec change
