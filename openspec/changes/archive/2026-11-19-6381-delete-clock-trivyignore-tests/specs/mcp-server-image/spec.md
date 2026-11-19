## REMOVED Requirements

### Requirement: Each MCP ignore entry stays valid
**Reason**: Its scenario is a test that reads `.trivyignore-mcp-server` and the wall clock. That test fails Tests & Coverage on each pull request after an `exp:` date, also when the pull request changes no image (#6381).
**Migration**: No requirement replaces it. Trivy drops an ignore entry from 00:00 UTC of its `exp:` date. The MCP Server Image job joins `.trivyignore`, `.trivyignore-mcp-server` and `.trivyignore-tofu` into one ignore file, so its scan reports a finding again from the last `exp:` date of that ID in the three files.
