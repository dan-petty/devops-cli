# cloudflared-release-pin Specification

## Purpose
The cloudflared release that the tunnel Deployment runs. The pin holds a release that rejects the eight eMudhra intermediate certificates with weak private keys, so a forged certificate does not pass for a Cloudflare host or an origin.

## Requirements

### Requirement: The tunnel Deployment runs a cloudflared release that rejects the compromised eMudhra intermediates
The container image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` SHALL be the repository `cloudflare/cloudflared` at tag 2026.10.2 or later. The container runs with `--no-autoupdate`, so only a change of this tag changes the release.

#### Scenario: The Deployment names an image below the first safe release
- **WHEN** a person runs `kubectl -n cloudflared get pods -o jsonpath='{range .items[*]}{.status.containerStatuses[*].image} {.status.containerStatuses[*].imageID}{"\n"}{end}'`
- **THEN** each tunnel pod runs the image `cloudflare/cloudflared` with a tag of 2026.10.2 or later, the tag of Deployment `cloudflared`
- **AND** each `imageID` holds the same digest
- **AND** `uv run devops k8s image-pins k8s/cloudflared` resolves the image of the repository `cloudflare/cloudflared` in its registry

### Requirement: The scan of the cloudflared image only reports
The job `third-party-image-scan` of `.github/workflows/third-party-image-scan.yml` SHALL scan, in its matrix entry `cloudflared`, the image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` with `.github/actions/image-scan` at exit code 0 under the category `trivy-image-cloudflared`, and SHALL exit 0 whatever it finds. It takes the place of the test that held the tag to a floor (#2322, #4363).

#### Scenario: A pull request changes the cloudflared Deployment
- **WHEN** a pull request changes `k8s/cloudflared/deployment.yaml`, and a person runs `uv run devops gh pr checks <number>`
- **THEN** the check `Third-Party Image Scan (cloudflared)` passes also when Trivy reports a finding, and its log names the image of the Deployment
