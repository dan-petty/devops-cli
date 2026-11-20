## REMOVED Requirements

### Requirement: The tools lock installs a cloudflared release that rejects the compromised eMudhra intermediates
**Reason**: The tools lock and `devops install-tools` are gone (#4363). The devtools image installs cloudflared on a host.
**Migration**: The tag of Deployment `cloudflared` keeps its requirement, and the third-party image scan reports a finding in that image.

## ADDED Requirements

### Requirement: The scan of the cloudflared image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan, in its matrix entry `cloudflared`, the image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` with `.github/actions/image-scan` at exit code 0 under the category `trivy-image-cloudflared`, and SHALL exit 0 whatever it finds. It takes the place of the test that held the tag to a floor (#2322, #4363).

#### Scenario: A pull request changes the cloudflared Deployment
- **WHEN** a pull request changes `k8s/cloudflared/deployment.yaml`, and a person runs `uv run devops gh pr checks <number>`
- **THEN** the check `Third-Party Image Scan (cloudflared)` passes also when Trivy reports a finding, and its log names the image of the Deployment
