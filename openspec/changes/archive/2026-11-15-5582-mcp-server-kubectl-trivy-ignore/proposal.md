# Proposal: #5582

## Why

The MCP Server Image scan reads `.trivyignore` and `.trivyignore-mcp-server`, and Trivy's ignore format has no path field. The `CVE-2026-78661` entry of `.trivyignore` exists for gh, expires on 2026-11-21, and also hides the finding in the pinned kubectl v1.37.2 (golang.org/x/net 0.57.0, fixed in 0.62.0).

No stable kubectl release holds x/net 0.62.0 or later and x/text 0.41.0 or later on 2026-11-14, so the bump waits on an upstream release. The three HIGH findings of kubectl v1.37.2 are:
- `CVE-2026-56851` in golang.org/x/text 0.40.0, fixed in 0.41.0
- `CVE-2026-78669` in golang.org/x/net 0.57.0, fixed in 0.60.0
- `CVE-2026-78661` in golang.org/x/net 0.57.0, fixed in 0.62.0

On 2026-11-14, Trivy scan proof on kubectl v1.37.2 confirmed these three findings.

The change gives the kubectl finding its own entry in `.trivyignore-mcp-server`, with a 3-day expiry inside the 14-day cap that ends on 2026-11-22, so the MCP scan stays green when the gh entry expires; the bump and the deletion of the entries are deferred until a release qualifies.

Closes #5582.

## What Changes

- Add a `CVE-2026-78661 exp:2026-11-17` entry to `.trivyignore-mcp-server` with a comment naming kubectl, the fix in golang.org/x/net 0.62.0, and tracking issue #5582.
- Add unit tests in `tests/invariants/test_mcp_server_image.py` verifying that:
  - `proposal.md` records the Trivy proof (CVE-2026-56851, CVE-2026-78669, CVE-2026-78661, golang.org/x/net 0.57.0, golang.org/x/text 0.40.0, fixes 0.62.0 and 0.41.0, and date 2026-11-14).
  - `.trivyignore-mcp-server` holds the `CVE-2026-78661` entry with valid comment naming kubectl, 0.62.0, and `#5582`.
  - The MCP scan does not depend on the gh entry in `.trivyignore`.
  - Each MCP ignore entry stays valid with reason, issue number, and unexpired date.

## Capabilities

### Modified Capabilities
- `mcp-server-image`: specify and verify `.trivyignore-mcp-server` entries for kubectl CVE-2026-78661 independent of `.trivyignore`.

## Impact

- Prevents MCP Server Image scan CI check failures when the gh ignore entry expires.
- Maintains compliance with SECURITY.md "A Finding with No Fix".

## Feasibility

Confirmed against `.trivyignore` and `.trivyignore-mcp-server`. The kubectl binary v1.37.2 contains the three findings and upstream stable release v1.37.2 has no newer release with the fixes on 2026-11-14.

## Existing Tool Considered

Trivy's ignore mechanism with `.trivyignore-mcp-server` is used directly as specified in the project security policy.
