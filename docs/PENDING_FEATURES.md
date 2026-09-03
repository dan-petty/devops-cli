# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.9` (Active Release)
1. **Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`)**: Generic strongly typed `StagePipeline[ContextT, ResultT]` framework with `@trace_span` telemetry, context scratchpad handoffs, and error containment.
2. **Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`)**: Centralized `HttpClientBroker` with HTTP/2 multiplexing, SSRF private network isolation, and traceparent propagation.
3. **Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`)**: Declarative chaos fault injector supporting pod disruption, latency simulation, and auto-recovery validation.
4. **Continuous IDE File Watcher & Instant Review (`devops ai review path --watch`)**: Watchdog-backed listener triggering incremental multi-persona reviews on active file changes.
5. **Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`)**: Lockfile-aware automated CVE patching via `uv lock --upgrade-package`, dry-run summaries, and git topic branch staging.
6. **Isolated Dockerized Workload Sandbox Environment (`devops test sandbox` / `devops docker sandbox`)**: Ephemeral, rootless container test harness and isolated execution sandbox for multi-container integration tests.
7. **Enterprise Vault & Cloud KMS Secret Broker (`devops vault`, `devops config vault`)**: HashiCorp Vault REST API and Cloud KMS secret broker with KV-v2 engine support, zero-plaintext storage, and OS Keyring fallback.
8. **Kubernetes Background Port-Forward Daemon Management (`devops k8s port-forward --daemon|status|stop`)**: Background process lifecycle tracking with managed PID state (`.data/k8s/port_forwards.json`), status inspection, and graceful termination.

### Previous Milestone: `v0.2.8` (Completed)
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
