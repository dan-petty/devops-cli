# Task 438: OCI Container Image Packaging, Standardized Metadata & GHCR Package Integration

**Issue**: [#438](https://github.com/dan-petty/devops-cli/issues/438)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Container images built and published to GitHub Container Registry (GHCR) (such as workstation devcontainers and standalone CLI runner images) lack standardized Open Container Initiative (OCI) image annotations and build metadata, preventing GitHub from automatically connecting packages to the repository, displaying package details, and managing repository-level access permissions.

#### Key Deliverables:
- Context & Rationale*: Container images built and published to GitHub Container Registry (GHCR) (such as workstation devcontainers and standalone CLI runner images) lack standardized Open Container Initiative (OCI) image annotations and build metadata, preventing GitHub from automatically connecting packages to the repository, displaying package details, and managing repository-level access permissions.
- OCI Metadata & GHCR Specification Alignment*: Adopt standard [OCI Image Spec labels](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#labelling-container-images) (`org.opencontainers.image.source=https://github.com/dan-petty/devops-cli`, `org.opencontainers.image.description`, `org.opencontainers.image.licenses=MIT`, `org.opencontainers.image.title`, `org.opencontainers.image.revision`, `org.opencontainers.image.version`, `org.opencontainers.image.created`, `org.opencontainers.image.documentation`) across all `Dockerfile` manifests and GitHub Actions container build workflows (`docker/metadata-action`, `.devcontainer/devcontainer.json`, and `.github/workflows/release.yml`), automatically linking published GHCR packages directly with `https://github.com/dan-petty/devops-cli`.
- Multi-Architecture Packaging & Provenance*: Integrate Buildx multi-platform compilation (`linux/amd64`, `linux/arm64`) for both the devcontainer base image and standalone `devops` CLI container; generate cryptographic SLSA provenance attestations and CycloneDX/SPDX SBOMs during package publication; enable layer caching via GitHub Actions cache backend.
- Refactoring Potential & Automated Verification*: Consolidate container build definitions in `.devcontainer/` and `.github/workflows/release.yml`; add automated pre-publish validation (`devops devcontainer validate` / OCI label inspection) ensuring `org.opencontainers.image.source` matches the canonical repository URL before any push to `ghcr.io`.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
