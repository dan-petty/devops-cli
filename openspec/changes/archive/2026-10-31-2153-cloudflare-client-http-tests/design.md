# Design: Cloudflare Client HTTP Edge Tests

## Context

`src/devops_cli/cloudflare/client.py` provides the `CloudflareClient` class for communicating with the Cloudflare API v4. It manages Cloudflare Access applications and policies, DNS records, and Cloudflare tunnels.

## Design Details

### 1. Transport Injection in CloudflareClient

Add `transport: httpx2.BaseTransport | None = None` to `CloudflareClient.__init__`:
```python
    def __init__(
        self,
        token: str,
        account_id: str | None = None,
        zone_id: str | None = None,
        base_url: str = CONST_URL_CLOUDFLARE_API_BASE,
        sleep: Callable[[float], None] = clock.sleep,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        ...
        self._transport = transport
```
In `_request()`, forward `self._transport` to `new_http_client(level=EgressLevel.PUBLIC, read_timeout=30.0, transport=self._transport)`.

### 2. Consolidated Account and Zone Checks

Define helper methods:
```python
def _require_account(self, account_id: str | None = None) -> str:
    resolved = account_id or self._account_id
    if not resolved:
        raise CloudflareAPIError("Account ID is required but neither passed nor configured.")
    return resolved


def _require_zone(self, zone_id: str | None = None) -> str:
    resolved = zone_id or self._zone_id
    if not resolved:
        raise CloudflareAPIError("Zone ID is required but neither passed nor configured.")
    return resolved
```
Replace manual checks across all 14 methods with calls to these helpers.

### 3. Comprehensive Edge Tests in `tests/cloudflare/test_client.py`

Create tests utilizing `httpx2.MockTransport`:
- Access application creation checking method, URL, and body payload.
- Policy create and update with email and CIDR inclusion rules.
- Invalid CIDR rejection raising `CloudflareAPIError`.
- DNS create, update, delete, and reconcile (`sync_dns_records`).
- Tunnel resolution, configuration fetch, and configuration update.
- Error handling on HTTP network failures and non-2xx responses.
- Parametrized tests covering all public methods requiring account or zone IDs.
