## MODIFIED Requirements

### Requirement: The image jobs scan with the action
The Service, Runner and MCP Server image jobs of `ci.yml` and `release.yml` SHALL call the action with the category `trivy-image-service`, `trivy-image-runner` or `trivy-image-mcp-server`, grant `security-events: write`, and set a step timeout below the job timeout. The Service and MCP Server jobs SHALL use exit code 1, and the Runner jobs exit code 0 (SECURITY.md, Dedicated Development Resources and Sandboxes). The image jobs of `ci.yml` SHALL run when `.trivyignore.yaml` or the action changes.

#### Scenario: The image workflows are validated
- **WHEN** a developer runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/ci.yml` or `.github/workflows/release.yml`

#### Scenario: Code scanning holds each image
- **WHEN** a person runs `uv run devops gh api 'repos/dan-petty/devops-cli/code-scanning/analyses?per_page=100' --jq '[.[].category] | unique'` after the merge
- **THEN** the list holds `trivy-image-service`, `trivy-image-runner` and `trivy-image-mcp-server`

#### Scenario: A finding in the runner image reports and stops no build
- **WHEN** the Runner Image job scans a runner image whose devtools tool binaries hold a fixed HIGH finding
- **THEN** the scan step exits 0, the job log shows the finding in a table, and code scanning lists the finding under `trivy-image-runner`
