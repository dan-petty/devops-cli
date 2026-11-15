# Design

## Decisions

### 1. Add dedicated MCP ignore entry for kubectl CVE-2026-78661
`.trivyignore-mcp-server` holds a dedicated entry for `CVE-2026-78661 exp:2026-11-17` with a comment citing kubectl v1.37.2, golang.org/x/net 0.62.0, and tracking issue #5582. This ensures the MCP server image scan remains independent of `.trivyignore`'s gh entry, which expires on 2026-11-21.

### 2. Follow 14-day security cap policy
The first entries for kubectl were added on 2026-11-08, establishing a 14-day cap ending on 2026-11-22 per `SECURITY.md#a-finding-with-no-fix`. The expiration is set to 2026-11-17 (3-day renewal interval matching existing kubectl entries).

## Rejected Alternatives

### 1. Build kubectl from source with fixed modules
Rejected: AGENTS.md rule 3 and project policy favor official upstream release binaries rather than custom source builds.

### 2. Rely on gh entry in .trivyignore without MCP entry
Rejected: Once the gh entry in `.trivyignore` expires or is removed upon upgrading gh, the MCP server image scan would fail due to kubectl's vendored copy of x/net.

### 3. Defer until upstream kubectl release
Rejected: No stable release containing x/net 0.62.0 or later and x/text 0.41.0 or later exists on 2026-11-14.
