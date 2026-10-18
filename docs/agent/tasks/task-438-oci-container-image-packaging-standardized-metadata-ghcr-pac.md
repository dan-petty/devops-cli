# Task 438: OCI Container Image Packaging, Standardized Metadata & GHCR Package Integration

**Issue**: [#438](https://github.com/dan-petty/devops-cli/issues/438)
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`
**Feasibility**: Verified against local Docker engine multi-arch compilation, `.github/workflows/release.yml` GitHub Actions schema, and `devops devcontainer validate` CLI command.

---

## 1. Description & Objectives

Container images built and published to GitHub Container Registry (GHCR) (such as workstation devcontainers and standalone CLI runner images) lack standardized Open Container Initiative (OCI) image annotations and build metadata, preventing GitHub from automatically connecting packages to the repository, displaying package details, and managing repository-level access permissions.

#### Key Deliverables:
- [x] OCI Metadata & GHCR Specification Alignment: Adopt standard OCI Image Spec labels (`org.opencontainers.image.source=https://github.com/dan-petty/devops-cli`, `org.opencontainers.image.description`, `org.opencontainers.image.licenses=MIT`, `org.opencontainers.image.title`, `org.opencontainers.image.revision`, `org.opencontainers.image.version`, `org.opencontainers.image.created`, `org.opencontainers.image.documentation`) across container manifests and GitHub Actions workflows (`Dockerfile`, `.devcontainer/Dockerfile`, `.github/workflows/release.yml`).
- [x] Multi-Architecture Packaging & Provenance: Multi-platform compilation (`linux/amd64`, `linux/arm64`) using Buildx and QEMU for both devcontainer base image and standalone `devops` CLI container; generate cryptographic SLSA provenance attestations and CycloneDX/SPDX SBOMs during package publication; enable layer caching via GitHub Actions cache backend.
- [x] Automated Pre-Publish Validation: Add automated pre-publish validation (`devops devcontainer validate --oci-labels <labels> --expected-source <url>`) ensuring `org.opencontainers.image.source` matches canonical repository URL before any push to `ghcr.io`.
- [x] Unit and integration test coverage with structural tuple equality assertions in `tests/test_devcontainer.py`, `tests/test_ci.py`, and `tests/test_workflow_contracts.py`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
