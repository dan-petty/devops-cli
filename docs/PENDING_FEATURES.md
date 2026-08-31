# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.6` (Scheduled)
1. **Infracost IaC Cloud FinOps Engine (`devops tf cost`)**: Automated cloud expenditure calculation on Terraform diffs with PR comment integration and OS Keyring credential resolution.
2. **Sigstore Cosign Container Provenance (`devops docker sign|verify`)**: Keyless OIDC and Ed25519 container image signing and verification.
3. **Syft & Grype Automated SBOM & Vulnerability Scanner (`devops scan sbom`)**: Automated Software Bill of Materials generation in CycloneDX/SPDX formats.

### Upcoming Milestone: `v0.2.7` (Scheduled)
1. **Isolated Dockerized Workload Sandbox (`devops test sandbox`)**: Ephemeral rootless container test harness with read-only rootfs and cgroup bounds.
2. **Adversarial Multi-Agent Debate (`devops ai review --debate`)**: Multi-turn debate between `devsecops` and `architect` personas to eliminate false-positive findings.

---

## 📖 Related Strategic Documents
- **Master Strategic Roadmap**: [`docs/ROADMAP.md`](ROADMAP.md)
- **Active Working Log**: [`docs/LOG.md`](LOG.md)
- **System Architecture**: [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Knowledge Base Task Manuals**: [`src/devops_cli/ai/knowledge_base/`](../src/devops_cli/ai/knowledge_base/README.md)
