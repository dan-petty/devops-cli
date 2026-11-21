# ci-image-scan Specification

## Purpose
How CI scans each container image for vulnerabilities: one composite action runs the pinned Trivy image, records SARIF in code scanning and prints the findings in the log, and `.trivyignore.yaml` holds each image finding that no release fixes yet, scoped to one binary.

## Requirements

### Requirement: One action scans an image
`.github/actions/image-scan` SHALL run the Trivy image, pinned by tag and digest, on its `image-ref` with `--scanners vuln --severity HIGH,CRITICAL --ignore-unfixed`, its `ignore-file` (default `.trivyignore.yaml`) and its `exit-code` (default 1). It SHALL write SARIF, print the findings as a table in the log, and upload the SARIF with `upload-sarif` under its `category`, also after a failed scan.

#### Scenario: The action is validated
- **WHEN** a developer runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** the command exits 0 and reports no finding in `.github/actions/image-scan/action.yml`

#### Scenario: A finding fails the scan and the log names it
- **WHEN** a job calls the action with exit code 1 on an image that holds a fixed HIGH finding that no entry of the ignore file matches
- **THEN** the step fails, the job log shows the finding in a table, and code scanning lists an analysis of the category of the caller

### Requirement: The image jobs scan with the action
The image jobs of `ci.yml` and the `Verify` job of `release-image.yml` SHALL call the action with the category `trivy-image-service`, `trivy-image-runner` or `trivy-image-mcp-server`, grant `security-events: write`, and set a step timeout below the job timeout. The Service and MCP Server scans SHALL use exit code 1, and the Runner scans exit code 0 (SECURITY.md, Dedicated Development Resources and Sandboxes). The image jobs of `ci.yml` SHALL run when `.trivyignore.yaml` or the action changes.

#### Scenario: The image workflows are validated
- **WHEN** a developer runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/ci.yml`, `.github/workflows/release.yml` or `.github/workflows/release-image.yml`

#### Scenario: Code scanning holds each image
- **WHEN** a person runs `uv run devops gh api 'repos/dan-petty/devops-cli/code-scanning/analyses?per_page=100' --jq '[.[].category] | unique'` after the merge
- **THEN** the list holds `trivy-image-service`, `trivy-image-runner` and `trivy-image-mcp-server`

#### Scenario: A finding in the runner image reports and stops no build
- **WHEN** the Runner Image job scans a runner image whose devtools tool binaries hold a fixed HIGH finding
- **THEN** the scan step exits 0, the job log shows the finding in a table, and code scanning lists the finding under `trivy-image-runner`

### Requirement: An image entry names one finding in one binary
Each entry of `vulnerabilities:` in `.trivyignore.yaml` SHALL name one finding `id`, the Trivy target of one binary in `paths`, the package that Trivy reports in `purls`, a `statement` that names the tracking issue, and an `expired_at` date. The repository SHALL hold no other ignore file for an image scan.

#### Scenario: An entry hides the finding only in its binary
- **WHEN** a developer runs `trivy image --ignorefile .trivyignore.yaml --show-suppressed --format json` on the built MCP server image, then changes the `paths` of one entry and runs it again
- **THEN** each suppressed finding names only the binary of its entry, and the second run reports the finding of the changed entry

#### Scenario: The legacy ignore files are absent
- **WHEN** a developer runs `git ls-files .trivyignore .trivyignore-mcp-server .trivyignore-tofu`
- **THEN** the command prints no path and exits 0
