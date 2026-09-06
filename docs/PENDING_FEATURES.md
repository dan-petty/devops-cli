# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.11` (Active Development)
1. **Workstation Infrastructure Valkey Migration**: Replaced all Redis components in the Kubernetes stack (ArgoCD and LLM stack) with Valkey 8.0-alpine under the BSD-3-Clause open-source license.
2. **Codebase Stylistic & Structural Drift Remediation & Parameter Establishment**:
   - Zero functions exceeding nesting depth 5 (<6 indentations) project-wide across `src/devops_cli`.
   - Reduced cyclomatic complexity $\le 10$ across tool factory closures (`FileSystem.get_tools`).
   - Standardized domain exception taxonomy inheriting from `DevOpsCLIError`, completely eradicating bare `ValueError`/`RuntimeError` across domain logic.
   - Clean test collection hygiene (`__test__ = False` on mock models) and unawaited coroutine prevention.
   - Automated architectural invariant quality gates in CI (`tests/test_architectural_invariants.py`).
3. **FastMCP Server Tool Expansion & Antigravity Schema Integration**:
   - Expanded FastMCP server from 53 to 72 registered tools achieving 1:1 parity with CLI subcommands (Kubernetes chaos/audit/lint/validate/diff, Trivy, Gitleaks, Semgrep, Checkov, AIBOM, SBOM, Vault, benchmark, git branch/PR).
   - Introduced 4 FastMCP prompt templates and 6 dynamic system resources.
   - Added `devops mcp export-schemas` subcommand.
   - Synchronized lazy tool schemas directly to Antigravity IDE (`/home/vscode/.gemini/antigravity-ide/mcp/devops-cli/`).

### Previous Milestones
- **`v0.2.10` (Completed)**: Native Pydantic AI Framework Subsystem Adoption, Autonomous Common Hallucinations Registry & Hardened Matching Engine, Secret Sanitizer Regex Hardening, Codebase Hygiene & Zombie Code Elimination.
- **`v0.2.9` (Completed)**: Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`), Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`), Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`), Continuous IDE File Watcher (`devops ai review path --watch`), Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`), Isolated Dockerized Workload Sandbox (`devops docker sandbox`), Enterprise Vault & Cloud KMS Secret Broker (`devops vault`), Kubernetes Background Port-Forward Daemon (`devops k8s port-forward`).
- **`v0.2.8` (Completed)**: Output Subsystem Modularization (`src/devops_cli/output/formatters/`), Language Message Catalog & Badge Localization (`src/devops_cli/lang/en/messages.py`), Declarative Dispatch Registries, Zombie Code Elimination.

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
