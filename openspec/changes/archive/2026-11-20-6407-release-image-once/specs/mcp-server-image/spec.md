## MODIFIED Requirements

### Requirement: The release publishes the MCP server image
The release SHALL build the `mcp-server` target one time and push it by digest, then smoke-test, scan, attest and tag that digest, in that order, only in the run that creates a release. It SHALL tag the image with the release tag and `latest`. The build SHALL set `no-cache-filters: mcp-server`.

#### Scenario: Publish job order
- **WHEN** a person reads the `MCP Server Image` jobs of the first release after the merge with `uv run devops gh run view <run_id>`
- **THEN** `Build` ran first, then `Verify`, then `Attest & Tag`, and `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/mcp-server:latest` gives the digest that `Build` pushed
