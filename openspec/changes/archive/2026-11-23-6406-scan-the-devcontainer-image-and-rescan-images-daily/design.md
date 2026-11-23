# Design

## Decisions

### Add `upload-sarif` input to `image-scan` action
- Context: The `devcontainer-smoke` job runs a privileged container for podman-in-podman. Architectural constraints forbid granting `security-events: write` or OIDC tokens to jobs with privileged containers.
- Decision: Add `upload-sarif: "true" | "false"` (default `"true"`) to `.github/actions/image-scan`. When `"false"`, `image-scan` writes SARIF and prints the findings table, but skips the upload step. The caller uploads the SARIF artifact with `actions/upload-artifact`. An unprivileged job with `security-events: write` downloads the artifact and uploads it with `github/codeql-action/upload-sarif`.
- Rationale: Preserves backwards compatibility for existing callers while keeping least-privilege security boundaries for privileged containers.

### DevContainer scan in `release.yml`
- Context: Release builds devcontainer image, smoke tests it, attests, and tags it.
- Decision: Scan in `devcontainer-smoke` after smoke test with `upload-sarif: "false"` and `exit-code: "0"`. Upload SARIF artifact. In `devcontainer` job, add `security-events: write`, download artifact, and upload SARIF under category `trivy-image-devcontainer`.

### DevContainer scan in `devcontainer-image.yml`
- Context: Daily workflow builds devcontainer image and smoke tests it.
- Decision: Scan in `devcontainer` job after smoke test with `upload-sarif: "false"` and `exit-code: "0"`. Upload SARIF artifact. Add a dedicated `scan-upload` job that needs `devcontainer`, holds `security-events: write` and `contents: read`, downloads artifact, and uploads SARIF under category `trivy-image-devcontainer`.

### Dedicated daily image rescan workflow
- Context: Published images need recurring scans so CVEs published after a release are detected and recorded.
- Decision: Create `.github/workflows/image-rescan.yml` with schedule `45 4 * * *` (04:45 UTC) and `workflow_dispatch`. It runs a matrix over `[service, runner, mcp-server, devcontainer]`, pulls `ghcr.io/${{ github.repository }}/${{ matrix.name }}:latest`, scans with `image-scan` at exit-code 0, and uploads SARIF directly under `trivy-image-${{ matrix.name }}`.
- Rationale: Decoupled from build workflows, runs between devcontainer build (04:15 UTC) and daily CI (05:00 UTC).

## Rejected alternatives

### Scan and upload in the same job with `security-events: write`
- Rejected: Granting `security-events: write` to a job running a privileged container violates the repository's security boundaries.

### Gate releases on scan failures (exit-code 1)
- Rejected: DevContainer binaries contain pre-existing findings that are not immediate release blockers. Owner decided on 2026-11-19 that devcontainer and daily rescans begin report-only (exit-code 0).
