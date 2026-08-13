# Strategic Roadmap — devops-cli

High-density product roadmap for `devops-cli`.

## Core Vision & Design Principles
1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ and `uv`.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens (`github`, `grafana`, `argocd`, `ai`).
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).
4. **Auditable AI Code Reviews**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with static metadata extraction (`SegmentMeta`), prompt isolation guardrails, and finding verification loops.

---

## Phased Milestones

### Phase 1: Core Foundation & Modernization (Completed)
- [x] Python 3.14+ runtime with `uv` virtual environment management.
- [x] OS Keyring integration for zero-plaintext secret storage.
- [x] Multi-persona code review engine with diff pagination (`devops review branch|pr|path`).
- [x] Infrastructure subcommands: `repos`, `ssh`, `k8s`, `kustomize`, `argo`, `grafana`, `prometheus`, `docker`, `workspace`, `install-tools`, `config`, `ci`, `branches`, `devcontainer`, `uv`.
- [x] `devops ci` unified quality gate (pytest, ruff check, ruff format, strict mypy).

### Phase 2: Finding Verification, Metadata Analysis & Dry-Run Models (v0.1.0 - Completed)
- [x] Finding inspection & human invalidation CLI (`devops review findings`, `devops review verify`, `devops review stats`).
- [x] Codebase metadata analysis command (`devops ai analyze [path|branch|pr]`) producing `.data/analysis/*-metadata.json`.
- [x] Pydantic model response outputs for all `--dry-run` subcommands (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- [x] Modular `devops_cli.dry_run` submodule package (`state.py`, `models.py`).
- [x] Dependency vulnerability scanner (`devops ci audit` via `uv audit`) and `UV_MALWARE_CHECK=1` devcontainer integration.
- [x] Python 3.14 exception syntax standardization (`except (Err1, Err2):`) and centralized `LanguageCatalog` literal management.

### Phase 3: Line-Level PR Comments & Custom Personas (v0.1.1 - Completed)
- [x] **Line-Level GitHub PR Inline Comments**: Post persona review findings directly to PR diff line hunks via GitHub API (`create_pr_review_comment`).
- [x] **Human Invalidation Feedback Exporter**: Export invalidated findings (`status="INVALIDATED"`) as benchmark JSONL datasets for prompt tuning (`devops ai review export-feedback`).
- [x] **Custom Team Personas**: Repository-level `.devops/personas/<name>.md` prompt overrides allowing custom reviewer personas.
- [x] **Headless CI Keyring Fallback Auth**: Memory token loading (`devops config auth-headless`) for headless CI environments lacking DBus.
- [x] **v0.1.1 Feature Flags**: Config options (`FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, `FEATURE_HEADLESS_AUTH`).

### Phase 4: Kubeconfig Contexts & SIEM Audit Logging (v0.1.2 - Completed)
- [x] **Multi-Cluster Kubeconfig Management**: Context switching (`devops k8s switch-context <name>`) with namespace controls.
- [x] **SIEM Audit Trail Logging**: Execution logging (`AuditLogger`) streaming to `.data/logs/audit.jsonl` or Syslog.
- [x] **Automated Code Patch Application Prep**: Staging suggested LLM code fixes (`devops ai review apply-patch`).
- [x] **Expanded Subcommand Dry-Run Models**: Pydantic `CommandDryRunResult` models across `argo`, `grafana`, `prometheus`, `devcontainer`.

### Phase 6: Default AI Metadata Analysis & Submodule Scanners (v0.1.4 - Completed)
- [x] **Default Enhanced Analysis**: Default `--enhanced` metadata generation (pseudocode outlines, complexity, ISO `last_analyzed` timestamps).
- [x] **Incremental Analysis Caching**: Skip redundant LLM calls on unchanged files (`st_mtime <= last_analyzed`), with `--update-all` bypass flag.
- [x] **Submodule-Aware Dependency Scanner**: Preserve full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`).
- [x] **Clean Pseudocode Generation**: Eliminate canned template language and strictly exclude import statements from pseudocode outlines.

### Phase 5: Minikube Service Auto-Config, FastMCP Alignment & 7-Gate CI (v0.1.5 - Completed)
- [x] **Minikube Endpoint Auto-Detection**: `devops k8s configure-urls` auto-detecting NodePort endpoints for `argocd`, `grafana`, and `prometheus`.
- [x] **FastMCP Server Alignment**: 18 FastMCP tools registered, verified, and mapped (`repos_status`, `argo_list`, `argo_status`, `docker_stats`, `workspace_list`).
- [x] **7-Gate CI Quality Gate**: Unified CI pipeline enforcing 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- [x] **Python 3.14 Exception Standardization**: Refactored exception tuple syntax across all modules (`except (Err1, Err2):`).
- [x] **Active Model Display**: Transparent model backend and provider visibility for all file review requests.

### Phase 7: SecOps & K8s Security Integrations (v0.1.6 - Completed)
- [x] **Trivy Vulnerability & Misconfiguration Engine**: Embed Aqua Trivy scanning (`devops scan [repo|image|iac]`) to inject static CVEs & secrets into `devsecops` persona review payloads.
- [x] **Kube-linter Manifest Auditor**: Integrate Red Hat Kube-linter (`devops k8s lint`) to validate K8s YAML & Kustomize manifests against production security best practices.
- [x] **Popeye K8s Cluster Sanitizer**: `devops k8s audit` command scanning active Minikube/K8s clusters for dead resources, over-allocated pods, and misconfigured probes.
- [x] **Pluto Deprecated API Scanner**: `devops k8s check-deprecated` for detecting deprecated/removed Kubernetes API versions prior to cluster upgrades.

### Phase 8: Observability, Scratchpad & AI Pipeline Architecture (v0.1.7 - Completed)
- [x] **DevContainer Shell Script Replacement Engine**: Native Python CLI commands (`devops devcontainer run-lifecycle --post-create|--post-start`) replacing `.devcontainer/postCreate.sh` and `.devcontainer/postStart.sh` shell scripts.
- [x] **Kubernetes LLM & Inference Stack**: `devops k8s deploy-stack --stack llm` deploying Ollama, Open-WebUI, Qdrant vector database, and Valkey in-memory cache with automated URL detection and port forwarding.
- [x] **Enhanced AI/LLM Scratchpad Utilization**: Structured multi-turn reasoning scratchpad (`ScratchpadBuffer`) for agentic review personas and multi-agent pipeline handovers to prevent reasoning degradation on complex code diffs.
- [x] **AI/LLM Prompt Token & Responsiveness Optimization**: Compress system prompts, streamline context payloads, eliminate prompt redundancy, and tune prompt structure to reduce token usage and improve inference latency across local Ollama and remote LLM providers.
- [x] **Robust Worker Error Recovery**: Exception resilience in parallel review workers and top-level workspace `.data` directory persistence.

### Phase 9: Telemetry, Agent Benchmarking & Supply Chain (v0.1.8 - Scheduled)
- [ ] **AI Agent Pipeline Tooling Research & Benchmark**: Research and evaluate open-source AI agent frameworks & toolkits (LangChain/LangGraph, AutoGen, CrewAI, LlamaIndex, DSPy, Haystack) to enhance multi-agent pipeline orchestration in `devops-cli`.
- [ ] **OpenTelemetry Tracing**: Instrument CLI commands, multi-agent pipeline turns, and FastMCP tools with OpenTelemetry span tracing.
- [ ] **Prometheus Metrics Engine**: Export operational metrics (turn latency, LLM node throughput, finding counts, cache hit ratios) to Prometheus.
- [ ] **Grafana Telemetry Dashboards**: Pre-built Grafana dashboards for real-time monitoring of CLI workload performance and review accuracy.
- [ ] **Jaeger Distributed Tracing**: Jaeger collector and UI integration for end-to-end trace visualization of multi-persona agentic pipelines.
- [ ] **DevContainer Minikube K8s Integration**: Automated local Minikube K8s cluster bootstrapping within DevContainer for zero-friction telemetry stack deployment.
- [ ] **Cosign Keyless Signature Verification**: Sigstore Cosign integration (`devops docker sign|verify`) using OS Keyring keys for container provenance and image signing.
- [ ] **Infracost IaC FinOps Engine**: `devops iac cost` estimating cloud cost impacts on Terraform/K8s diffs to enrich `pm` and `architect` persona reviews.
- [ ] **Checkov Static Policy Guard**: `devops ci iac-security` automated compliance policy checks across Terraform, CloudFormation, and Dockerfiles.
- [ ] **Kyverno Admission Policy Validator**: `devops k8s validate-policy` for CLI validation of K8s Kyverno policies (`ClusterPolicy`).
- [ ] **k6 Load & Performance Tester**: `devops test load` executing developer-centric smoke tests against K8s endpoints and LLM node endpoints.
- [ ] **Dagger Programmable Pipeline Engine**: `devops pipeline run` for containerized, reproducible Python-driven pipeline execution.

---

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | Input Sanitization & Path Traversal Guards | High | Low | ✅ Completed |
| | Human Finding Verification CLI & Accuracy Stats | High | Low | ✅ Completed |
| | Deterministic Static Segment Metadata (`SegmentMeta`) | High | Low | ✅ Completed |
| | Prompt Isolation Guardrails & Tag Sanitization | High | Low | ✅ Completed |
| | `devops config output` Env Var Spec Command | High | Low | ✅ Completed |
| | Trivy Vulnerability & Misconfig Scanner Integration | High | Low | ✅ Completed (v0.1.6) |
| | Kube-linter K8s Manifest Auditor | High | Low | ✅ Completed (v0.1.6) |
| | Popeye K8s Cluster Sanitizer | High | Low | ✅ Completed (v0.1.6) |
| | Pluto K8s Deprecated API Scanner | High | Low | ✅ Completed (v0.1.6) |
| **Strategic Investments** | Minikube Service Auto-Config & 7-Gate CI | High | High | ✅ Completed (v0.1.5) |
| | DevContainer Shell Script Replacement Engine | High | Medium | ✅ Completed (v0.1.7) |
| | Enhanced AI/LLM Scratchpad Reasoning Buffer | High | Medium | ✅ Completed (v0.1.7) |
| | AI/LLM Prompt Token & Latency Optimization | High | Medium | ✅ Completed (v0.1.7) |
| | AI Agent Pipeline Framework Evaluation & Benchmark | High | Medium | 🔄 Scheduled (v0.1.7) |
| | OpenTelemetry, Prometheus, Grafana & Jaeger via Minikube | High | High | 🔄 Scheduled (v0.1.7) |
| | Cosign Container Signature Verification & Keyring Auth | High | Medium | 🔄 Scheduled (v0.1.8) |
| | Infracost IaC Cloud Cost Estimation | High | Medium | 🔄 Scheduled (v0.1.8) |
| | Line-Level GitHub PR Inline Comments | High | High | ✅ Completed (v0.1.1) |
| | Human Feedback Dataset Exporter | High | Medium | ✅ Completed (v0.1.1) |
| | Custom Team Persona Overrides (`.devops/personas/`) | High | Medium | ✅ Completed (v0.1.1) |
| **Fill-ins** | Checkov IaC Static Policy Engine | Medium | Low | 🔄 Scheduled (v0.1.8) |
| | Kyverno K8s Admission Policy Validator | Medium | Medium | 🔄 Scheduled (v0.1.8) |
| | k6 Performance & Latency Smoke Tester | Medium | Medium | 🔄 Scheduled (v0.1.8) |
| | Dagger Containerized Python Pipeline Engine | Medium | High | 🔄 Scheduled (v0.1.8) |
| | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Auth | Medium | Medium | ✅ Completed (v0.1.1) |
| **De-prioritized** | Bare-Metal OS Installers | Low | High | ❌ Rejected (Devcontainer native) |
