# Strategic Roadmap — devops-cli

High-density product roadmap, engineering milestones, and open-source integration strategy for `devops-cli`.

## Core Vision & Design Principles

1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ runtime, `uv` virtual environments, and reproducible toolchains.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens and credentials (`github`, `grafana`, `argocd`, `ai`), eliminating plaintext storage across files, logs, and artifacts.
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`) and strict destination endpoint validation.
4. **Adaptive Workflow & Model Routing ("Own the Sensitive, Rent the Frontier")**: Decouple static single-model dependence. Dynamically route across two decision axes (Complexity and Freshness) to retain sensitive internal code on air-gapped/local open models (Granite, Qwen, DeepSeek) while renting frontier reasoning engines for high-complexity architectural design.
5. **Agent Harness Slots & Sub-Agent Local Offloading**: Partition multi-agent execution into swappable slots (Model, Skills, Tools, Sub-Agents). Offload token-intensive sub-agent tasks (code exploration, AST symbol mapping) to local open-weight models ("Big decides, small types, big checks") to achieve 85%+ token savings.
6. **Model Curation Pipeline & AI Bill of Materials (AIBOM)**: Fast, automated model supply-chain governance gating `trust_remote_code=True` via static AST/Semgrep inspection before GPU provisioning, preventing Shadow AI breaches and compiling verifiable AIBOM records.
7. **Model Dependency Chaos Engineering & Slow-Zone Resilience**: Deliberately test fallback models ("Chaos Monkey for Models") against tool suites and keep documentation/CLI `--help` 100% synchronized so lesser models can pilot automation without human coaching.
8. **Auditable Multi-Persona Code Reviews**: Domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with deterministic static metadata extraction (`SegmentMeta`), prompt boundary isolation, and closed-loop finding verification.
9. **Zero Boilerplate & Standard Library Leverage**: Expressive integration of modern standard library utilities (`pathlib`, `ast`, `collections`, `itertools`, `functools`), Pydantic v2 schemas, and strict indentation budgets (<6 levels).
10. **Complete Observability Triad & Centralized Kubernetes Logging**: Unified telemetry integrating Prometheus client metrics, Jaeger/OTel distributed tracing, and Grafana Loki centralized log aggregation with LogQL CLI querying and agentic incident diagnosis.
11. **Pre-1.0 Alpha Velocity & Post-1.0 SemVer Change Management**: Until at least release `1.0.0`, `devops-cli` is active alpha software with no intention of maintaining backwards compatibility. The codebase must remain clean of legacy references and obsolete shims at all times so that it can reach maturity at a reasonable rate. Any version after `1.0.0` will follow strict semantic versioning conventions, and use all change management best practices including feature flags, deprecations, and migration functionality.
12. **Hypothesis-Driven Trial-and-Error & Counterexample-Guided Synthesis (CEGIS)**: Never rely on fragile single-shot generation for complex defects, performance bottlenecks, or refactorings. Formulate falsifiable hypotheses, explore solution trees (Tree-of-Thought / MCTS) in ephemeral shadow worktrees, accumulate failing counterexamples as formal negative constraints (CEGIS), enforce cascading fast-fail verification gates, and minimize discovered patches to atomic, Pareto-optimal diffs.
13. **Cognitive Information Foraging & Syntopical Epistemic Hygiene**: Agents must read, research, and gather information with human-like cognitive discipline—prioritizing inspectional multi-scale outlines over monolithic token dumps, traversing information scent cues with backtracking, maintaining active marginalia, triangulating claims against ground-truth primary sources, and synthesizing syntopical mental models that resolve dialectical contradictions.
14. **Autonomous Agentic Project Governance & Grounded Lifecycle Orchestration**: Software delivery must be autonomously governed through closed-loop, agentic project management. Work items, review remediations, and architectural epics must be decomposed into atomic, traceable issues with grounded taxonomy, real-time board transitions across lifecycle states, explicit dependency tracking, and dynamic WIP budgeting to eliminate ungrounded development and project drift.
15. **Reactive Terminal Ergonomics & Unified Workstation Command Center**: The developer terminal is the primary operational canvas. Complex multi-cloud, container, AI, and project lifecycle telemetry must be synthesized into a reactive, high-density terminal user interface (TUI) with non-blocking async workers, master-detail split screens, live log streaming, and sub-second fuzzy command dispatch, eliminating context switching to fragmented web dashboards.
16. **Stochastic Language Bound by Deterministic Mechanical Oracles & Feedback Inversion**: Autonomous engineering velocity relies on pairing probabilistic LLM token generation with deterministic mechanical oracles (AST complexity parsers, structural tuple assertion consolidation, negative JSON schema validation, POSIX process group containment, and pre-flight boundary limits). As quality gates reach 100% pass rates, feedback loops dynamically invert from reactive defect remediation to proactive architectural headroom optimization.

---

## Release Milestones (Chronological Order)

### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime, Packaging & Workstation Core**: Python 3.14+ runtime with `uv` virtual environment management, cross-platform DevContainer Python lifecycle hooks (`devops devcontainer run-lifecycle`), OS Keyring zero-plaintext secret storage, SIEM audit logging (`AuditLogger`), and automated GHCR DevContainer container publishing.
- [x] **Multi-Persona Code Review Engine**: Domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`), diff pagination, line-level GitHub PR inline comments, human invalidation feedback dataset exporter (`devops ai review export-feedback`), structured scratchpad reasoning buffer (`ScratchpadBuffer`), and XML prompt boundary isolation.
- [x] **Static SecOps & Kubernetes Auditing**: Static security scanner integrations (Aqua Trivy vulnerability & IaC scans, Red Hat Kube-linter manifest audits, Derailed Popeye cluster health sanitizer, Fairwinds Pluto API deprecations, and Kubernetes RBAC policy scanner).
- [x] **Local Kubernetes & Minikube Infrastructure**: Multi-cluster Kubeconfig context switching, automated Minikube NodePort endpoint discovery (`devops k8s configure-urls`), and multi-stack lifecycle (`infra`, `llm`, `all`).
- [x] **OpenTofu Multi-Cloud Infrastructure as Code**: Full IaC command suite (`devops tf`) with production OpenTofu modules for AWS (EKS), Azure (AKS), and GCP (GKE), and FastMCP IaC tools (`tf_plan`, `tf_apply`, `tf_output`).
- [x] **Automated Quality Gates & Dynamic Documentation**: 7-gate CI quality suite (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`), dynamic Click/Typer docs introspection engine (`CLI_REFERENCE.md`, `ENV_VARS.md`, `MCP_TOOLS.md`), and automated release management suite (`devops release`).

### Distributed Observability, AI Agent Harness, Workload Sandboxing & Hardened SecOps (v0.2.0 – v0.2.23 - Completed)
- [x] **Distributed Observability & Telemetry**: Prometheus client metrics, Jaeger distributed tracing waterfalls, Loki LogQL live log streaming, and OpenTelemetry traceparent propagation.
- [x] **Next-Gen PydanticAI Agent Architecture**: PydanticAI native subsystems, multi-turn reasoning buffers, prompt mutation testing, and human-in-the-loop feedback dataset export.
- [x] **Valkey Distributed Caching & Rate Limiting**: Pure-Python RESP3 wire protocol client, token-bucket rate limiter, and vector cache slashing LLM latency.
- [x] **Code Intelligence, Tree-Sitter & Ingestion Engine**: Polyglot CST parser, library contract introspector, API drift auditor, AST context packing, and file-size/symlink resource containment boundaries.
- [x] **Workload Sandboxing & Dynamic Runtime Security**: Rootless container sandbox, endpoint health probing, dynamic fuzzing, and base security scanner consolidation.

### Multi-Cloud Mesh & Production Ecosystem (v0.3.0 - Future Vision)
- [ ] **Multi-Region Workstation Mesh & Cluster Federation**: Distributed cluster management across hybrid on-premise and multi-cloud Kubernetes clusters with automatic service mesh routing.
- [ ] **Autonomous Self-Healing Agent Pipeline**: Closed-loop diagnostic engine capable of discovering cluster incidents, generating corrective patches, running CI gates, and executing rollback.
- [ ] **Cloud-Native Ephemeral Test Environment Provisioner (`devops env ephemeral up/down`)**: Automated provisioning of isolated namespace staging environments with seeded mock databases, synthetic datasets, and TLS ingresses on minikube or cloud clusters.
- [ ] **Zero-Trust Git Commit & Tag Cryptographic Verification (`devops release verify-signatures`)**: Automated verification of SSH/GPG and Sigstore keyless commit signatures across repository history and pull requests.
- [ ] **Distributed Multi-Cluster Telemetry & OTel Egress Mesh**: Global trace and metric federation across hybrid workstation topologies with automated anomaly alerting.
- [ ] **Distributed Cache & Shared Semantic Embeddings Sync (`devops ai cache sync`)**: S3 / OCI-backed shared LLM response and vector embedding cache for remote engineering teams.
- [ ] **JIT Python 3.14 Tail-Call & Bytecode Optimization Benchmarking**: Comprehensive runtime benchmarks utilizing Python 3.14+ specialization and JIT compiler tiers.

---

## Value vs. Effort Prioritization Matrix

> [!NOTE]
> This matrix tracks active, scheduled, and future roadmap deliverables across Value and Effort dimensions. Historical deliverables that have reached completion are archived in milestone changelogs and release notes to keep the prioritization backlog focused on in-flight and upcoming work.

| Priority Category | Feature / Focus | Primary Open Source Resource | Value | Effort | Target Release | Status |
|---|---|---|---|---|---|---|
| **Quick Wins** | Observability, Context Budgeting, Valkey Cache & Security Pre-Filters | Standard Library / PydanticAI / Valkey | High | Low | v0.2.x | ✅ Completed |
| **Major Projects** | Universal Stage Pipelines, Ephemeral Sandboxing & Dynamic Probing | Docker / K8s / Tree-Sitter | High | High | v0.2.x | ✅ Completed |
| **Fill-Ins** | Dynamic Schema Export, AST Memoization & Knowledge Base Linters | Click / Typer Introspection | Low | Low | v0.2.x | ✅ Completed |
| **Foundation** | DevContainer Lifecycle, PSA Enforcement & Invariant Gates | Linux / Docker / OTel | Low | High | v0.2.x | ✅ Completed |
|  | Zero-Trust Git Commit & Tag Signature Verifier | `git`, GPG, Sigstore | High | Low | v0.3.0 | 💡 Future Vision |
|  | JIT Python 3.14 Bytecode Optimization Benchmarking | `pytest-benchmark` / JIT | Medium | Low | v0.3.0 | 💡 Future Vision |
|  | Multi-Region Workstation Mesh & Cluster Federation | Kubernetes / Fleet | High | High | v0.3.0 | 💡 Future Vision |
|  | Autonomous Self-Healing Agent Pipeline | PydanticAI / Diagnostic | High | High | v0.3.0 | 💡 Future Vision |
|  | Cloud-Native Ephemeral Test Environment Engine | Minikube / Helm / Ingress | High | Medium | v0.3.0 | 💡 Future Vision |
|  | Distributed Multi-Cluster Telemetry & OTel Egress Mesh | OTel Collector / Prometheus | High | High | v0.3.0 | 💡 Future Vision |
|  | Distributed Cache & Shared Semantic Embeddings Sync | S3 / OCI / SQLite | High | Medium | v0.3.0 | 💡 Future Vision |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
|  | Heavyweight Monolithic Orchestrators | Full LangChain | Low | High | — | ❌ Rejected (FastMCP + PydanticAI) |
