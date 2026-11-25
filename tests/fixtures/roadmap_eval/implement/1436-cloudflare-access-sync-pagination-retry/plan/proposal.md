# Proposal

## Why

Issue #1436: Cloudflare Access application and policy listings fetch only the first page of results.
If an account has more applications than fit on one page, `_ensure_access_application` creates a duplicate application.
Only the DNS listing paginates, using an endpoint-specific helper.
Furthermore, `CloudflareClient._request` does not retry requests that fail with HTTP 429 or 5xx.
Rate limits or temporary server errors cause synchronization operations to fail midway.

## What Changes

- Add one reusable paginated GET helper to `CloudflareClient` that reads `result_info.page` and `total_pages`.
- Update `list_dns_records`, `list_access_applications`, and `get_access_policies` to use the paginated helper.
- Remove `_is_last_dns_page` and redundant pagination loops.
- Add retries with `tenacity` in `_request` for HTTP 429 and 5xx responses.
- Respect the `Retry-After` header when present, and use bounded attempts.
- Accept an optional `sleep` parameter in `CloudflareClient` to allow tests to inject a fake clock without real delays.
- Ensure HTTP 4xx responses other than 429, including 403, are not retried.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/cloudflare/client.py`
- Tests: `tests/test_cloudflare_commands.py`

## Feasibility

- The premise was confirmed by reading `src/devops_cli/cloudflare/client.py`.
- `list_access_applications` and `get_access_policies` call `self._request` once without pagination parameters.
- Cloudflare REST API v4 returns `result_info` with `page` and `total_pages` on paginated collection endpoints.
- Tenacity is already an installed dependency in the project virtual environment.
- The `clock` test fake provides monotonic and sleep seams for fast execution.

## Existing Tool Considered

- `tenacity`: already a dependency in the project, provides retry decorators, retrying loops, stop criteria, and sleep injection.
- No new external dependency is necessary.
