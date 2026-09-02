# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.8` (Completed / Active Release)
1. **Output Subsystem Modularization (`src/devops_cli/output/formatters/`)**: Deconstructed monolithic formatter into `scalars.py`, `tables.py`, and `panels.py`.
2. **Language Message Catalog & Badge Localization (`src/devops_cli/lang/en/messages.py`)**: Complete localization of terminal badges, status indicators, and headers via `BadgeMessages` and `OutputMessages`.
3. **Declarative Dispatch Registries**: Table-driven AST symbols (`ast_stream.py`), AI capability settings (`capabilities.py`, `workflow.py`), and compaction strategies (`compaction.py`).
4. **Zombie Code & Legacy Shim Elimination**: Removed deprecated re-export shims and merged models directly into authoritative modules.

### Upcoming Milestone: `v0.3.0` (Scheduled)
1. **Multi-Region Workstation Mesh & Cluster Federation**: Cross-cluster service discovery and state sync.
2. **Autonomous Self-Healing Agent Pipeline**: Self-diagnostic remediation loops.
3. **Cloud-Native Ephemeral Test Environment Engine**: Dynamic Minikube/Helm ephemeral environments.

---

## 📖 Related Strategic Documents
- **Master Strategic Roadmap**: [`docs/ROADMAP.md`](ROADMAP.md)
- **Active Working Log**: [`docs/LOG.md`](LOG.md)
- **System Architecture**: [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Knowledge Base Task Manuals**: [`src/devops_cli/ai/knowledge_base/`](../src/devops_cli/ai/knowledge_base/README.md)
