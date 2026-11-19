## REMOVED Requirements

### Requirement: Each MCP ignore entry stays valid
**Reason**: Its scenario is a test that reads `.trivyignore-mcp-server` and the wall clock. That test fails Tests & Coverage on each pull request after an `exp:` date, and Trivy already drops an expired entry (#6381).
**Migration**: The requirement "An expired MCP ignore entry stops hiding its finding" makes the MCP Server Image scan the proof of the `exp:` date.

## ADDED Requirements

### Requirement: An expired MCP ignore entry stops hiding its finding
Each entry of `.trivyignore-mcp-server` SHALL hold a comment with its reason and tracking issue, and an `exp:YYYY-MM-DD` date. The MCP Server Image scan SHALL report the finding of an entry after its `exp:` date, because Trivy drops an expired entry. Thus the scan fails until a person renews or removes the entry.

#### Scenario: The scan reports the finding of an expired entry
- **WHEN** The MCP Server Image job runs `trivy image --ignorefile .trivyignore-mcp-server --exit-code 1` after the `exp:` date of an entry.
- **THEN** Trivy reports the finding of that entry, and the scan exits 1.
