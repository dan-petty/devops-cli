# Strategic Roadmap — devops-cli

High-density product roadmap and open-source integration strategy for `devops-cli`.

## Core Vision & Design Principles
1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ and `uv`.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens (`github`, `grafana`, `argocd`, `ai`).
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).
4. **Auditable AI Code Reviews**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with static metadata extraction (`SegmentMeta`), prompt isolation guardrails, and finding verification loops.

---

## Release Milestones (Chronological Order)

### Core Foundation & Modernization (v0.0.1 - Completed)
- [x] Python 3.14+ runtime with `uv` virtual environment management.
- [x] OS Keyring integration for zero-plaintext secret storage.
- [x] Multi-persona code review engine with diff pagination (`devops ai review branch|pr|path`).
- [x] Infrastructure subcommands: `repos`, `ssh`, `k8s`, `kustomize`, `argo`, `grafana`, `prometheus`, `docker`, `workspace`, `install-tools`, `config`, `ci`, `branches`, `devcontainer`, `uv`.
- [x] `devops ci` unified quality gate (pytest, ruff check, ruff format, strict mypy).

### Finding Verification, Metadata Analysis & Dry-Run Models (v0.1.0 - Completed)
- [x] **Finding Inspection & Human Invalidation CLI**: Structured JSON finding viewer and human override loop (`devops ai review findings`, `devops ai review verify`, `devops ai review stats`).
- [x] **Codebase Metadata Analysis Command**: Extract project structure and dependencies (`devops ai analyze [path|branch|pr]`) producing `.data/analysis/*-metadata.json`.
- [x] **Pydantic Model Response Outputs**: Standardized Pydantic models for all `--dry-run` subcommands (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- [x] **Modular Dry-Run Package**: Modular `devops_cli.dry_run` package (`state.py`, `models.py`).
- [x] **Dependency Vulnerability Scanner**: Automated package auditing (`devops ci audit` via `uv audit`) and `UV_MALWARE_CHECK=1` devcontainer integration.
- [x] **Python 3.14 Exception Standardization**: Enforced parenthesized tuples (`except (Err1, Err2):`) and centralized `LanguageCatalog` literal management.

### Line-Level PR Comments & Custom Personas (v0.1.1 - Completed)
- [x] **Line-Level GitHub PR Inline Comments**: Post persona review findings directly to PR diff line hunks via GitHub API (`create_pr_review_comment`).
- [x] **Human Invalidation Feedback Exporter**: Export invalidated findings (`status="INVALIDATED"`) as benchmark JSONL datasets for prompt tuning (`devops ai review export-feedback`).
- [x] **Custom Team Personas**: Repository-level `.devops/personas/<name>.md` prompt overrides allowing custom reviewer personas.
- [x] **Headless CI Keyring Fallback Auth**: Memory token loading (`devops config auth-headless`) for headless CI environments lacking DBus.
- [x] **v0.1.1 Feature Flags**: Config options (`FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, `FEATURE_HEADLESS_AUTH`).

### Kubeconfig Contexts & SIEM Audit Logging (v0.1.2 - Completed)
- [x] **Multi-Cluster Kubeconfig Management**: Context switching (`devops k8s switch-context <name>`) with namespace controls.
- [x] **SIEM Audit Trail Logging**: Execution logging (`AuditLogger`) streaming to `.data/logs/audit.jsonl` or Syslog.
- [x] **Automated Code Patch Application Prep**: Staging suggested LLM code fixes (`devops ai review apply-patch`).
- [x] **Expanded Subcommand Dry-Run Models**: Pydantic `CommandDryRunResult` models across `argo`, `grafana`, `prometheus`, `devcontainer`.

### Interactive Patch Staging & Air-Gapped Bundler (v0.1.3 - Completed)
- [x] **Interactive Patch Staging (`devops ai review apply-patch --interactive`)**: Interactive unified diff rendering and confirmation before applying suggested LLM fixes.
- [x] **Air-Gapped Ollama Model Bundler (`devops ai bundle-models`)**: Export and package local Ollama model weight manifests for air-gapped DevContainer environments.
- [x] **Kubernetes RBAC Audit Policy Scanner (`devops k8s rbac-audit`)**: Security audit scanner evaluating RoleBindings and ServiceAccount privileges across namespaces.
- [x] **SIEM Live Audit Streamer (`devops config audit-stream`)**: Streaming structured JSON audit trail records to Syslog or HTTP collectors.

### Default AI Metadata Analysis & Submodule Scanners (v0.1.4 - Completed)
- [x] **Default Enhanced Analysis**: Default `--enhanced` metadata generation (pseudocode outlines, complexity, ISO `last_analyzed` timestamps).
- [x] **Incremental Analysis Caching**: Skip redundant LLM calls on unchanged files (`st_mtime <= last_analyzed`), with `--update-all` bypass flag.
- [x] **Submodule-Aware Dependency Scanner**: Preserve full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`).
- [x] **Clean Pseudocode Generation**: Eliminate canned template language and strictly exclude import statements from pseudocode outlines.

### Minikube Service Auto-Config, FastMCP Alignment & 7-Gate CI (v0.1.5 - Completed)
- [x] **Minikube Endpoint Auto-Detection**: `devops k8s configure-urls` auto-detecting NodePort endpoints for `argocd`, `grafana`, and `prometheus`.
- [x] **FastMCP Server Alignment**: 18 FastMCP tools registered, verified, and mapped (`repos_status`, `argo_list`, `argo_status`, `docker_stats`, `workspace_list`).
- [x] **7-Gate CI Quality Gate**: Unified CI pipeline enforcing 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- [x] **Active Model Display**: Transparent model backend and provider visibility for all file review requests.

### SecOps & K8s Security Integrations (v0.1.6 - Completed)
- [x] **Trivy Vulnerability & Misconfiguration Engine**: Embed Aqua Trivy scanning (`devops scan [repo|image|iac]`) to inject static CVEs & secrets into `devsecops` persona review payloads.
- [x] **Kube-linter Manifest Auditor**: Integrate Red Hat Kube-linter (`devops k8s lint`) to validate K8s YAML & Kustomize manifests against production security best practices.
- [x] **Popeye K8s Cluster Sanitizer**: `devops k8s audit` command scanning active Minikube/K8s clusters for dead resources, over-allocated pods, and misconfigured probes.
- [x] **Pluto Deprecated API Scanner**: `devops k8s check-deprecated` for detecting deprecated/removed Kubernetes API versions prior to cluster upgrades.

### Observability, Scratchpad & AI Pipeline Architecture (v0.1.7 - Completed)
- [x] **DevContainer Shell Script Replacement Engine**: Native Python CLI commands (`devops devcontainer run-lifecycle --post-create|--post-start`) replacing `.devcontainer/postCreate.sh` and `.devcontainer/postStart.sh` shell scripts.
- [x] **Kubernetes LLM & Inference Stack**: `devops k8s deploy-stack --stack llm` deploying Ollama, Open-WebUI, Qdrant vector database, and Valkey in-memory cache with automated URL detection and port forwarding.
- [x] **Enhanced AI/LLM Scratchpad Utilization**: Structured multi-turn reasoning scratchpad (`ScratchpadBuffer`) for agentic review personas and multi-agent pipeline handovers to prevent reasoning degradation on complex code diffs.
- [x] **AI/LLM Prompt Token & Responsiveness Optimization**: Compress system prompts, streamline context payloads, eliminate prompt redundancy, and tune prompt structure to reduce token usage and improve inference latency across local Ollama and remote LLM providers.
- [x] **Robust Worker Error Recovery**: Exception resilience in parallel review workers and top-level workspace `.data` directory persistence.

### Automated Release Suite, Docs Engine & SRE Elevation (v0.1.8 - Completed)
- [x] **Automated Release Cycle Suite (`devops release`)**: Native release subcommands (`status`, `prepare`, `check`, `notes`, `tag`) automating semver bumping, changelog maintenance, and pre-release gates.
- [x] **FastMCP Server Release Integration**: Added `release_status` MCP tool for AI agents to query version consistency, git tags, and documentation freshness.
- [x] **Dynamic Documentation Engine (`devops docs`)**: Dynamic Typer/Click introspection system generating markdown reference manuals and synchronizing the `README.md` Command Matrix.
- [x] **Principal SRE Architecture & Governance Blueprint**: Authored enterprise [`ARCHITECTURE.md`](../ARCHITECTURE.md), MIT [`LICENSE`](../LICENSE), enterprise [`SECURITY.md`](../SECURITY.md), and SRE [`CONTRIBUTING.md`](../CONTRIBUTING.md).
- [x] **CI/CD Quality Gates & Release Automation**: Production-grade GitHub Actions workflows (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- [x] **Configuration & Constant Centralization**: Unified paths, timeouts, regex patterns, and user-facing messages in `config/` and `lang/en.py`.

### OpenTofu Multi-Cloud IaC, DevContainer Packaging & Tool Parity (v0.1.9 - Completed)
- [x] **OpenTofu CLI Integration (`devops tofu` / `devops tf`)**: Native CLI commands for managing OpenTofu IaC lifecycle (`init`, `plan`, `apply`, `destroy`, `output`, `validate`, `fmt`, `status`, `deploy-cloud`) with dynamic executable detection (`tofu` / `terraform`).
- [x] **Multi-Cloud Kubernetes Infrastructure Modules (`tf/`)**: Production OpenTofu manifests for provisioning Kubernetes clusters and VPC networking across AWS (EKS), Azure (AKS), and Google Cloud (GKE) tailored for deploying project `k8s/` resources.
- [x] **Reusable Docker Dev Container Package (GHCR Image)**: Integrated `devcontainers/ci@v0.3` and `docker/login-action@v3` into release workflow publishing pre-built workstation containers to `ghcr.io/dan-petty/devops-cli/devcontainer:<version>` and `latest`.
- [x] **OpenTofu FastMCP Tools (`tf_plan`, `tf_apply`, `tf_output`)**: Model Context Protocol bridge and agent tools for autonomous infrastructure operations.
- [x] **AI Review Feedback & Verification Remediation**: Standardized Python 3 exception tuples, Pydantic `Field(default_factory=...)` mutable defaults, and verified finding invalidation benchmark exports (`.data/feedback_dataset.jsonl`).

### Distributed Observability, Tracing & Telemetry (v0.2.0 - Completed)
- [x] **FastAPI REST & OpenAPI Service Engine (`devops serve`)**: Native asynchronous FastAPI HTTP service (`uvicorn` / `fastapi`) exposing REST endpoints for remote CLI invocation, AI review triggers, workspace status queries, and health probes with auto-generated OpenAPI documentation and Swagger UI.
- [x] **OpenTelemetry Python SDK Instrumentation (`opentelemetry-sdk`, `opentelemetry-exporter-otlp`)**: Instrument CLI commands, multi-agent pipeline turns, subprocess executions, and FastMCP tools with distributed span tracing exported to OTLP collectors.
- [x] **Prometheus Client Metrics Engine (`prometheus-client`)**: In-memory metrics tracking turn latency, LLM throughput (tokens/sec), review accuracy rates, and cache hit ratios.
- [x] **Grafana Workstation Telemetry Dashboards**: Pre-provisioned Grafana dashboards in `k8s/` monitoring workstation load, Docker containers, and AI reviewer performance in real time.
- [x] **Jaeger Distributed Trace Visualization**: Jaeger collector and UI integration for end-to-end trace waterfalls of multi-persona agentic reasoning.

### Next-Gen Agentic Architecture & Context Optimization (v0.2.1 - Completed)
- [x] **PydanticAI Standardized Agent Framework (`pydantic-ai`)**: Modernized multi-agent review and reasoning pipelines using PydanticAI to eliminate boilerplate tool routing, validate structured LLM responses, and simplify multi-turn handoffs.
- [x] **Local Context Budgeting & Token Counting (`tiktoken`)**: Client-side BPE tokenizer budgeting and diff chunking before LLM dispatch, preventing context overflows and minimizing inference latency.
- [x] **Semgrep Static AST Pattern Matcher (`semgrep`)**: Embedded Semgrep CLI for sub-second multilingual AST pattern matching, pre-filtering static bugs and injecting deterministic findings into `devsecops` and `qa` review stages.
- [x] **Gitleaks Sub-Millisecond Secret Pre-Filter (`gitleaks`)**: Native pre-review secret scanner hook catching uncommitted credentials prior to diff analysis.
- [x] **CodeQL Security Hardening**: Remediated stack trace exposure on telemetry endpoints and hardened file creation modes for clear-text storage mitigation.

---

### Supply Chain Security, SBOM & Cloud Cost Governance (v0.2.2 - In Progress / Up Next)
- [ ] **Sigstore Cosign Container Provenance (`cosign`)**: Keyless container image and manifest signing (`devops docker sign|verify`) integrating with OS Keyring and OIDC tokens for verifiable supply-chain provenance.
- [ ] **Syft & Grype Automated SBOM & Vulnerability Scanning (`syft`, `grype`)**: Automated Software Bill of Materials (SBOM) generation (`devops scan sbom`) in CycloneDX/SPDX formats and Grype container runtime vulnerability auditing.
- [ ] **Infracost FinOps Cloud Cost Engine (`infracost`)**: `devops tf cost` integrating Infracost CLI to evaluate cloud financial impacts on Terraform/OpenTofu diffs, enriching `pm` & `architect` review personas with monthly cost deltas.
- [ ] **Checkov IaC Static Policy & Compliance Engine (`checkov`)**: `devops scan iac` / `devops ci iac-security` automated compliance policy checks across Terraform, CloudFormation, Kubernetes, and Dockerfiles.

### Declarative Policy, Programmable CI & Resiliency (v0.2.3 - Scheduled)
- [ ] **Kyverno & OPA Gatekeeper K8s Policy Validator (`kyverno-cli`, `opa`)**: `devops k8s validate-policy` for pre-deployment admission policy validation (`ClusterPolicy`, `ConstraintTemplate`) in CI and local workflows.
- [ ] **Dagger Programmable Python Pipeline Engine (`dagger-io`)**: `devops pipeline run` for containerized, reproducible Python-driven pipeline execution with built-in caching and isolated client execution.
- [ ] **k6 Cloud-Native Load & Latency Tester (`k6`)**: `devops test load` executing developer-centric smoke, spike, and load tests against Kubernetes services and LLM inference endpoints.
- [ ] **Chaos Engineering & Resilience Validator (`chaos`)**: `devops k8s chaos run` orchestrating pod disruption, network latency injection, and partition resilience experiments.

### Real-Time Agent Streaming & Diagram Generation (v0.2.4 - Scheduled)
- [ ] **Streaming SSE / WebSocket Agent Reasoning Feed (`devops serve /stream`)**: Server-Sent Events (SSE) and WebSocket streams delivering real-time LLM token generation, multi-agent reasoning steps, and scratchpad updates to IDE extensions and web UIs.
- [ ] **Architecture & Threat Modeling Diagram Synthesis (`diagrams`, `mermaid-cli`)**: `devops ai diagram [arch|threat]` generating visual architecture topology diagrams and threat flowcharts directly from AST and IaC manifests.
- [ ] **Automated PR Remediation Branch Generator (`devops ai review auto-fix`)**: Autonomous generation of corrective topic branches (`fix/finding-<id>`) with verified unit tests and staged patches for reviewer-approved remediations.
- [ ] **Hybrid Dense-Sparse RAG Tier (BM25 + Qdrant Hybrid Search)**: Reciprocal Rank Fusion (RRF) combining keyword BM25 search with dense vector embeddings for high-precision code retrieval across massive codebases.

### Enterprise Fleet Orchestration & Multi-Cluster Mesh (v0.3.0 - Future Vision)
- [ ] **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`argo-rollouts`)**: Advanced canary and blue-green rollout management with automated Prometheus metric-based rollback gates.
- [ ] **Vault & Cloud KMS Enterprise Secret Broker (`hvac`, `aws-kms`, `gcp-kms`)**: Dynamic secret leases, key rotation, and envelope encryption for enterprise teams beyond OS Keyring.
- [ ] **Trace-Driven Automated Performance Regression Detection**: Continuous performance baseline tracking comparing OTel spans across PRs to flag latency regressions before production merges.

---

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Primary Open Source Resource | Value | Effort | Target Release | Status |
|---|---|---|---|---|---|---|
| **Quick Wins** | Input Sanitization & Path Traversal Guards | Standard Library (`pathlib`) | High | Low | v0.0.1 | ✅ Completed |
| | Human Finding Verification CLI & Accuracy Stats | Rich / Pydantic | High | Low | v0.1.0 | ✅ Completed |
| | Deterministic Static Segment Metadata (`SegmentMeta`) | Python AST / `ast` | High | Low | v0.1.0 | ✅ Completed |
| | Prompt Isolation Guardrails & Tag Sanitization | Regex / HTML Escaping | High | Low | v0.1.0 | ✅ Completed |
| | `devops config output` Env Var Spec Command | Rich Table / Pydantic | High | Low | v0.1.0 | ✅ Completed |
| | Trivy Vulnerability & Misconfig Scanner Integration | Aqua Security Trivy | High | Low | v0.1.6 | ✅ Completed |
| | Kube-linter K8s Manifest Auditor | Red Hat Kube-linter | High | Low | v0.1.6 | ✅ Completed |
| | Popeye K8s Cluster Sanitizer | Popeye CLI | High | Low | v0.1.6 | ✅ Completed |
| | Pluto K8s Deprecated API Scanner | Fairwinds Pluto | High | Low | v0.1.6 | ✅ Completed |
| | Reusable DevContainer Package on Release | `devcontainers/ci`, GHCR | High | Low | v0.1.9 | ✅ Completed |
| | Local Context Budgeting & Token Counting | `tiktoken` | High | Low | v0.2.1 | ✅ Completed |
| | Gitleaks Secret Pre-Filter | `gitleaks` CLI | High | Low | v0.2.1 | ✅ Completed |
| | Checkov IaC Static Policy & Compliance | `checkov` CLI | High | Low | v0.2.2 | 🔄 Up Next |
| **Strategic Investments** | OpenTofu Multi-Cloud IaC Modules (`tf/`) | OpenTofu / AWS / Azure / GCP | High | High | v0.1.9 | ✅ Completed |
| | Minikube Service Auto-Config & 7-Gate CI | Minikube / GitHub Actions | High | High | v0.1.5 | ✅ Completed |
| | DevContainer Shell Script Replacement Engine | Python Subprocess / Typer | High | Medium | v0.1.7 | ✅ Completed |
| | Enhanced AI/LLM Scratchpad Reasoning Buffer | Pydantic / Rich | High | Medium | v0.1.7 | ✅ Completed |
| | FastAPI REST & OpenAPI Service Engine (`devops serve`) | FastAPI / Uvicorn | High | Medium | v0.2.0 | ✅ Completed |
| | OpenTelemetry Distributed Tracing & Metrics | OpenTelemetry SDK / Prometheus | High | Medium | v0.2.0 | ✅ Completed |
| | PydanticAI Multi-Agent Pipeline Orchestration | `pydantic-ai`, `fastmcp` | High | Medium | v0.2.1 | ✅ Completed |
| | Semgrep AST Pattern Matcher | `semgrep` CLI | High | Medium | v0.2.1 | ✅ Completed |
| | Sigstore Cosign Container Provenance | `cosign` CLI / OS Keyring | High | Medium | v0.2.2 | 🔄 Up Next |
| | Infracost FinOps Cloud Cost Estimation | `infracost` CLI | High | Medium | v0.2.2 | 🔄 Up Next |
| | Syft & Grype SBOM & Container Scanning | `syft`, `grype` | High | Medium | v0.2.2 | 🔄 Up Next |
| | Streaming SSE / WebSocket Agent Reasoning Feed | FastAPI SSE / WebSockets | High | Medium | v0.2.4 | 📋 Scheduled |
| | Hybrid Dense-Sparse RAG Search (BM25 + Qdrant) | Qdrant / Rank-BM25 | High | Medium | v0.2.4 | 📋 Scheduled |
| | Multi-Cluster ArgoCD Fleet Sync & Rollouts | Argo Rollouts / Prometheus | High | High | v0.3.0 | 💡 Future Vision |
| **Tactical Additions** | Line-Level GitHub PR Inline Comments | PyGithub / GitHub REST API | High | High | v0.1.1 | ✅ Completed |
| | Human Feedback Dataset Exporter | JSONL / Pydantic | High | Medium | v0.1.1 | ✅ Completed |
| | Custom Team Persona Overrides (`.devops/personas/`) | Jinja2 / Markdown | High | Medium | v0.1.1 | ✅ Completed |
| | Kyverno & OPA Gatekeeper Admission Validator | `kyverno-cli`, `opa` | Medium | Medium | v0.2.3 | 📋 Scheduled |
| | k6 Performance & Latency Smoke Tester | `k6` CLI | Medium | Medium | v0.2.3 | 📋 Scheduled |
| | Dagger Containerized Python Pipeline Engine | `dagger-io` SDK | Medium | High | v0.2.3 | 📋 Scheduled |
| | Architecture & Threat Diagram Synthesis | `diagrams`, `mermaid-cli` | Medium | Medium | v0.2.4 | 📋 Scheduled |
| | Automated PR Remediation Branch Generator | Git / GitHub API | Medium | Medium | v0.2.4 | 📋 Scheduled |
| | Enterprise Vault & KMS Secret Broker | `hvac`, Cloud KMS SDKs | Medium | High | v0.3.0 | 💡 Future Vision |
| | Ephemeral Headless Keyring Auth | `keyring.backends` | Medium | Medium | v0.1.1 | ✅ Completed |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
| | Heavyweight Monolithic Orchestrators | Full LangChain | Low | High | — | ❌ Rejected (FastMCP + PydanticAI) |
