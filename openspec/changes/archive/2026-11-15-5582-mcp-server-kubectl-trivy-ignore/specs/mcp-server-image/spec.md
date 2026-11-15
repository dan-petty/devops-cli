# mcp-server-image Specification

## ADDED Requirements

### Requirement: The MCP ignore file holds the kubectl x/net entry
`.trivyignore-mcp-server` MUST hold a `CVE-2026-78661` entry whose comment names the kubectl finding, the fix in golang.org/x/net 0.62.0 and a tracking issue.

#### Scenario: The finding has its own entry
- **WHEN** A test reads `.trivyignore-mcp-server`.
- **THEN** A non-comment line is `CVE-2026-78661 exp:YYYY-MM-DD`, and the comment above it names kubectl, 0.62.0 and `#<number>`.

### Requirement: The MCP scan does not depend on the gh entry
The MCP Server Image scan MUST keep the `CVE-2026-78661` entry when the `CVE-2026-78661` entry of `.trivyignore` is absent, so the kubectl finding stays ignored after 2026-11-21.

#### Scenario: The gh entry is absent from the scan input
- **WHEN** A test removes every `CVE-2026-78661` line from `.trivyignore` and reads both ignore files.
- **THEN** `.trivyignore-mcp-server` still holds a `CVE-2026-78661` entry with an `exp:` date.

### Requirement: Each MCP ignore entry stays valid
Each entry of `.trivyignore-mcp-server` SHALL hold a comment with its reason and tracking issue, and an `exp:YYYY-MM-DD` date that is not past.

#### Scenario: Every entry has a reason, a tracking issue and a future expiry
- **WHEN** A test reads each entry line of `.trivyignore-mcp-server`.
- **THEN** The comment above it is non-empty and holds an issue number, and the line holds an `exp:` date after the test date.
