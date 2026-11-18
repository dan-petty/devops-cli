# Proposal

## Why

The six image scan steps of `.github/workflows/ci.yml` and `release.yml` use `aquasecurity/trivy-action` v0.36.0. The action calls `aquasecurity/setup-trivy` v0.2.6 unless `skip-setup-trivy` is true. `setup-trivy` restores a cached binary, and on a cache miss it runs `contrib/install.sh` from the Trivy repository. That script downloads the release archive from GitHub with no retry option in the action. A GitHub outage with HTTP 5xx answers on a cache miss fails the scan step (#4229).

## What Changes

- `.github/workflows/ci.yml`: In jobs `service-image`, `runner-image`, and `mcp-server-image`, set up the uv toolchain, install Trivy via `uv run devops install-tools --tool trivy --only-missing`, add `$HOME/.local/bin` to `GITHUB_PATH`, and configure `aquasecurity/trivy-action` with `skip-setup-trivy: "true"`.
- `.github/workflows/release.yml`: In jobs `service-image`, `runner-image`, and `mcp-server-image`, set up the uv toolchain, install Trivy via `uv run devops install-tools --tool trivy --only-missing`, add `$HOME/.local/bin` to `GITHUB_PATH`, and configure `aquasecurity/trivy-action` with `skip-setup-trivy: "true"`.
- This change alters only GitHub Actions workflows and adds no observable consumer behavior, so it sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflows: `.github/workflows/ci.yml`, `.github/workflows/release.yml`

## Feasibility

- `devops install-tools --tool trivy --only-missing` is already used in `ci.yml`, verifies the SHA-256 in `tools.lock`, and retries downloads.
- `aquasecurity/trivy-action` v0.36.0 supports `skip-setup-trivy: "true"` to use the pre-installed binary on `PATH`.
- Verified with `uv run devops ci --check --only actionlint,zizmor`.

## Existing Tool Considered

`devops install-tools`, which retries failed downloads and verifies pinned SHA-256 hashes against `tools.lock`.

## Dependencies

None.
