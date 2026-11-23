# Proposal: #6406

## Why
The devcontainer image is published, attested, and tagged at each release with no vulnerability scan. The service, runner, and mcp-server images are scanned only when built. Nothing scans published digests again. A CVE published after a release stays unseen until the next release, and no record exists.

## What Changes
- Add the `upload-sarif` input to `.github/actions/image-scan` to permit scanning in jobs that lack write permissions.
- Run `image-scan` in `devcontainer-smoke` with exit code 0, upload the SARIF artifact, and upload SARIF to GitHub Code Scanning in the `devcontainer` job of `.github/workflows/release.yml`.
- Run `image-scan` in `devcontainer` job with exit code 0, upload the SARIF artifact, and upload SARIF to GitHub Code Scanning in a new `scan-upload` job of `.github/workflows/devcontainer-image.yml`.
- Add a daily scheduled workflow `.github/workflows/image-rescan.yml` at 04:45 UTC to scan `:latest` tags of `service`, `runner`, `mcp-server`, and `devcontainer` with exit code 0 and upload SARIF to GitHub Code Scanning.

## Capabilities
- Daily vulnerability rescan of published container images.
- Release and daily vulnerability scans of the devcontainer image.

## Impact
- GitHub Code Scanning receives SARIF analyses for `trivy-image-devcontainer`, `trivy-image-service`, `trivy-image-runner`, and `trivy-image-mcp-server`.
- No disruption to releases: all new scans run with exit code 0 (report-only).

## Feasibility
Confirmed against `.github/actions/image-scan/action.yml`, `.github/workflows/release.yml`, and `.github/workflows/devcontainer-image.yml`. Workflow linter checks pass with `actionlint` and `zizmor`.

## Existing Tool Considered
Trivy through the existing local action `.github/actions/image-scan` and `github/codeql-action/upload-sarif`. No new tool is introduced.
