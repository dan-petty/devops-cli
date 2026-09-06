# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.10` (Release Candidate)
1. **Native Pydantic AI Framework Subsystem Adoption**: Full adoption of native `pydantic_ai` modules (`toolsets`, `tools`, `template`, `settings`, `run`, `retries`, `result`, `profiles`, `providers`, `output`, `models.ollama`, `mcp`, `function_signature`, `format_prompt`, `exceptions`, `durable_exec`, `direct`, `concurrency`, `capabilities`, `common_tools`).
2. **Autonomous Common Hallucinations Registry & Hardened Matching Engine**: Category-aligned similarity guards, stop words filter, ground-truth verification, and protected canonical definitions in `src/devops_cli/ai/review/common_hallucinations.py`.
3. **Secret Sanitizer Regex Hardening**: Protected variable identifiers (e.g. `secret_storage_failed`) from accidental diff masking in `sanitization.py`.
4. **Codebase Security & Robustness Remediations**: Hardened path containment across `ext_langchain.py`, `media.py`, `vault_broker.py`, `auto_fix.py`; SSRF domain handling in `common_tools.py` and `capabilities.py`; flag injection protections in `chaos_runner.py` and `difftastic.py`; and system path disclosure sanitization in `complexity.py` and `kubelinter.py`.
5. **Persona & Verification Prompt Tuning**: Harmonized modern Python 3.14 PEP 758 multi-exception syntax and sanitization placeholder guidance across review prompts (`devsecops`, `architect`, `verify_finding_system.md`).
6. **Dedicated Agent Operational Task Tracking**: Canonical task status tracking under `docs/agent/task.md` (`docs/agent/README.md`).
7. **Codebase Hygiene, Elimination of Forbidden Patterns, and Zombie Code Removal**: Eradication of hardcoded extension sets, elimination of monkey-patch shims on `NativeRunContext` in favor of clean subclassing, removal of legacy aliases (`Tool.func`, `NativeMCPToolset`, `DevOpsCLIError.code`, `scan gitleaks/semgrep/checkov`, `rag reset`, `run_shell`, `main`, `scan_main`, `scan_app`), parameter and fallback consolidation (`now`, `DEVOPS_CLI_DATA_DIR`), and replacement of arbitrary synthetic scoring floats with mathematical keyword overlap ratios.

### Previous Milestones
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
