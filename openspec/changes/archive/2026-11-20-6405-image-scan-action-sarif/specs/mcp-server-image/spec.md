## MODIFIED Requirements

### Requirement: The release gate equals the pull request gate
The smoke test of the release job SHALL equal that of job `mcp-server-image` in `ci.yml`, and both jobs SHALL scan the image with `.github/actions/image-scan` under the category `trivy-image-mcp-server`.

#### Scenario: Same smoke test and scan
- **WHEN** A developer compares the two jobs and runs `git grep -c 'category: trivy-image-mcp-server' .github/workflows/ci.yml .github/workflows/release.yml`.
- **THEN** The smoke test scripts are equal, and the command prints a count of 1 for each file.

## REMOVED Requirements

### Requirement: The MCP ignore file holds the kubectl x/net entry
**Reason**: `.trivyignore-mcp-server` is gone (#6405). `.trivyignore.yaml` holds each image finding with the path of its binary and its package.
**Migration**: The requirement "An image entry names one finding in one binary" of `ci-image-scan` covers the kubectl entries.

### Requirement: The MCP scan does not depend on the gh entry
**Reason**: An entry of `.trivyignore.yaml` names the binary of its finding, so the kubectl entry does not depend on the entry of another tool (#6405).
**Migration**: The requirement "An image entry names one finding in one binary" of `ci-image-scan` covers the kubectl entries.
