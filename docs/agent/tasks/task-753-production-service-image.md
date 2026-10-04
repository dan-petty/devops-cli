# Task: Production Service Image for Scheduled Jobs and Webhook Handlers (#753)

**Issue**: [#753](https://github.com/dan-petty/devops-cli/issues/753)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, priority/p1-high, scope/release

## Description
Build and publish a dedicated production service image for `devops-cli` to execute scheduled jobs and webhook handlers in the homelab Kubernetes cluster. The image packages Python 3.14 runtime, `gh` CLI, `git`, and `devops-cli` virtual environment into a hardened, non-root (`1000:1000`), read-only container with `/etc/gitconfig` credentials. Verified through local and CI smoke testing under strict security constraints (`--read-only`, `--tmpfs`, `--cap-drop ALL`, `no-new-privileges`), Trivy vulnerability scanning, SPDX SBOM attestation, and cryptographic build provenance signing.

## Acceptance Criteria
- [x] Root `Dockerfile` multi-stage build packaging Python 3.14 runtime, `gh` CLI, `git`, and `/app/.venv` on `python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4` and `ghcr.io/astral-sh/uv:0.12.16@sha256:adc68cd785ca65ea25c0611043b0a00b4ea3a22e1b54102fc084406d888082ee`.
- [x] Local smoke testing passes under full security sandbox:
  - Container health probe: `/healthz` returns `{"status":"ok", ...}` and version `0.2.26`.
  - Non-root user validation: `id -u` prints `1000`.
  - Tooling verification: `gh --version` and `git --version` exit 0.
  - Python security sandbox probe exits 0 writing to `DEVOPS_CLI_DATA_DIR` on tmpfs and initializing git repository.
  - Hardening validation: build tools (`uv`, `gcc`, `pytest`) are absent.
- [x] DevContainer image continues building cleanly with the new root `.dockerignore`.
- [x] Smoke test implemented as a unified, shellcheck-compliant `run:` block with identical logic in `ci.yml` and `release.yml`.
- [x] Architectural invariant tests parametrized across devcontainer and service-image path filters, verifying `.dockerignore` tracking and `@sha256:` base image digest pinning (`tests/test_architectural_invariants.py`).
- [x] Workflow invariants verified in `tests/test_ci.py`: CI job permissions, `push: false`, release job step sequence (build, smoke, scan, push, attest), and Trivy inputs.
- [x] Pinned `aquasecurity/trivy-action` commit (`ed142fd0673e97e23eac54620cfb913e5ce36c25`) and nested `setup-trivy` commit SHA (`3fb12ec12f41e471780db15c232d5dd185dcb514`).
- [x] Added `docker` package ecosystem tracking to `.github/dependabot.yml`.
- [x] Documented service image attestation verification command in `docs/ROUTINE_TASKS.md`.
- [x] Authored changelog fragment `changelog.d/753.md` without modifying shared files.
- Pending a person: `gh attestation verify oci://ghcr.io/dan-petty/devops-cli/service:v0.2.26 -R dan-petty/devops-cli --signer-workflow dan-petty/devops-cli/.github/workflows/release.yml`
- Pending a person: `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/service:v0.2.26 --format '{{ json .SBOM }}'`
- Pending a person: `DOCKER_CONFIG=$(mktemp -d) docker pull ghcr.io/dan-petty/devops-cli/service:v0.2.26`
- Pending a person: `docker run --rm ghcr.io/dan-petty/devops-cli/service:v0.2.26 --version`

## Deliverables
- [x] `Dockerfile`: Multi-stage service image definition.
- [x] `.dockerignore`: Root context allowlist admitting only build requirements.
- [x] `.trivyignore`: Trivy vulnerability suppression configuration.
- [x] `.github/workflows/ci.yml`: Added `service-image` job and `.dockerignore` change tracking.
- [x] `.github/workflows/release.yml`: Added `service-image` build, smoke, scan, push, and attest job.
- [x] `.github/dependabot.yml`: Added `docker` ecosystem monitoring.
- [x] `tests/test_architectural_invariants.py`: Parametrized path-filter and image digest pinning tests.
- [x] `tests/test_ci.py`: CI and release workflow invariant tests.
- [x] `docs/ROUTINE_TASKS.md`: Updated release procedure with attestation verification.
- [x] `changelog.d/753.md`: Changelog fragment.
