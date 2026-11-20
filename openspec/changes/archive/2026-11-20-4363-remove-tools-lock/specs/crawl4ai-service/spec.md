## MODIFIED Requirements

### Requirement: The scan of the third-party image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan, in its matrix entry `crawl4ai`, the image of the Deployment with `.github/actions/image-scan` at exit code 0 under the category `trivy-image-crawl4ai`, and SHALL exit 0 whatever it finds. The workflow SHALL run only for a pull request that changes `k8s/devops/crawl4ai/deployment.yaml`, `k8s/cloudflared/deployment.yaml`, the workflow file or the action.

#### Scenario: The scan fails the job
- **WHEN** a pull request changes `k8s/devops/crawl4ai/deployment.yaml`, and a person runs `uv run devops gh pr checks <number>`
- **THEN** the check `Third-Party Image Scan (crawl4ai)` passes also when Trivy reports a finding
- **AND** `uv run devops ci --check --only actionlint,zizmor` passes on the workflow

#### Scenario: A pull request that does not change the Deployment
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
