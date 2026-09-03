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
- [x] **Configuration & Constant Centralization**: Unified paths, timeouts, regex patterns, and user-facing messages in `config/` and `lang/en/`.

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

### Static IaC Compliance, Dynamic Routing & Metrics (v0.2.2 - Completed)
- [x] **Checkov IaC Static Policy & Compliance Engine (`checkov`)**: `devops scan iac` / `devops ci iac-security` automated compliance policy checks across Terraform, CloudFormation, Kubernetes, and Dockerfiles.
- [x] **TFLint Cloud Provider Linter (`tflint`)**: `devops tf lint` for deep Terraform/OpenTofu static validation against cloud provider rules.
- [x] **Dive Docker Layer Efficiency Analyzer (`dive`)**: `devops docker analyze-layers` for container image layer inspection and wasted space minimization.
- [x] **Kubeconform Fast OpenAPI Schema Validator (`kubeconform`)**: `devops k8s validate` validating manifests against OpenAPI schemas.
- [x] **Dynamic Cost- & Latency-Aware LLM Router (`devops_cli.ai.router`)**: Task complexity routing between local Ollama (`qwen2.5-coder`) and remote frontier models with cost, token, and latency tracking.
- [x] **Prometheus In-Memory Metrics Registry & Exporter Engine (`devops_cli.telemetry.metrics`)**: Dedicated metrics collector tracking command runtimes, LLM token throughput (tokens/sec), review accuracy rates, and AST cache hit ratios.
- [x] **AST Parsing Cache & Structural Memoization (`devops_cli.ai.analyze.cache`)**: Centralized content-hash-keyed AST cache eliminating redundant syntactic re-parsing across multi-persona review passes.
- [x] **Automated Workspace & Data Tier Cleanup Engine (`devops workspace clean`, `devops clean`)**: Housekeeping command pruning stale `.data/reviews/`, `.data/analysis/`, and temporary traces with configurable retention policies (`--older-than`, `--dry-run`).
- [x] **Knowledge Base & Documentation Freshness Linter (`devops docs lint`)**: Automated static validation ensuring 100% command and option parity across CLI entry points, Knowledge Base manuals (`src/devops_cli/ai/knowledge_base/`), and markdown references.

### Declarative Policy, Programmable CI & Resiliency (v0.2.3 - Completed)
- [x] **Kyverno & OPA Gatekeeper K8s Policy Validator (`kyverno-cli`, `opa`)**: `devops k8s validate-policy` for pre-deployment admission policy validation (`ClusterPolicy`, `ConstraintTemplate`) in CI and local workflows.
- [x] **Multi-Agent Adversarial Debate (MAD) Verification Stage**: Adversarial challenger persona eliminating hallucinated security alerts, false positives, and stylistic noise.
- [x] **Spec-Driven Architecture & Contract Verification (`devops ai spec`)**: Executable markdown specification contracts (`.devops/specs/*.spec.md`) verifying code against architectural invariants and API schemas.
- [x] **Stern Multi-Pod Live Log Streamer (`stern`)**: `devops k8s stream-logs` for regex-based live multi-container log streaming across replica sets.
- [x] **Helm Diff Deployment Impact Previewer (`helm-diff`)**: `devops k8s diff-helm` previewing manifest changes prior to Helm upgrades.
- [x] **Difftastic Structural Syntax-Aware AST Diff Provider (`difft`)**: Syntax-aware AST diffing feeding clean, whitespace-invariant diffs into LLM review stages.
- [x] **Dagger Programmable Python Pipeline Engine (`dagger-io`)**: `devops pipeline run` for containerized, reproducible Python-driven pipeline execution with built-in caching and isolated client execution.
- [x] **k6 Cloud-Native Load & Latency Tester (`k6`)**: `devops test load` executing developer-centric smoke, spike, and load tests against Kubernetes services and LLM inference endpoints.
- [x] **Chaos Engineering & Resilience Validator (`chaos`)**: `devops k8s chaos run` orchestrating pod disruption, network latency injection, and partition resilience experiments.
- [x] **Review Pipeline Modular Decomposition (`devops_cli.ai.review.stages`)**: Refactored monolithic pipeline into dedicated stage modules (`stage1_pre_analysis`, `stage2_static_scan`, `stage3_persona_review`, `stage4_verification`, `stage5_reranking`, `stage6_reporting`).
- [x] **OpenTelemetry Log Correlation Bridge (`opentelemetry-appender-logging`)**: Inject active `trace_id` and `span_id` context into standard library logging and JSON SIEM audit trails (`.data/logs/audit.jsonl`).
- [x] **Dead Code & Unused Symbol Pruning (`vulture` / AST Audit)**: Project-wide static dead code, orphaned import, and unused test fixture sweeps to maintain zero boilerplate.
- [x] **Toolchain & Lockfile Maintenance Review Gate (`devops ci maintain`)**: Automated weekly dependency freshness scans, lockfile synchronization, and devcontainer binary validation.

### Real-Time Agent Streaming & Diagram Generation (v0.2.4 - Current Release)
- [x] **Streaming SSE / WebSocket Agent Reasoning Feed (`devops serve /stream` & `/ws`)**: Server-Sent Events (SSE) and WebSocket streams delivering real-time LLM token generation, multi-agent reasoning steps, and scratchpad updates to IDE extensions and web UIs.
- [x] **Automated Unit Test Synthesizer & Execution Verifier (`devops ai test-gen`)**: Generates and executes isolated pytest test suites for uncommitted diffs to maximize branch coverage.
- [x] **Prompt Mutation Testing & Benchmark Guardrails (`devops ai prompt-eval`)**: Automated evaluation framework benchmarking persona prompt variations against verified feedback datasets.
- [x] **Aider-Style Tree-Sitter / AST Repository Map Generator (`devops ai repomap`)**: Compact whole-repo symbol and relationship map for global architecture context without prompt budget overflow.
- [x] **tfcmt Automated PR Plan Notifier (`devops tf notify-plan`)**: Post structured, collapsible OpenTofu/Terraform plan diffs directly to PRs.
- [x] **Architecture & Threat Modeling Diagram Synthesis (`devops ai diagram [arch|threat]`)**: `devops ai diagram [arch|threat]` generating visual architecture topology diagrams and threat flowcharts directly from AST and IaC manifests.
- [x] **Automated PR Remediation Branch Generator (`devops ai review auto-fix`)**: Autonomous generation of corrective topic branches (`fix/finding-<id>`) with verified unit tests and staged patches for reviewer-approved remediations.
- [x] **Hybrid Dense-Sparse RAG Tier (BM25 + Qdrant Hybrid Search)**: Reciprocal Rank Fusion (RRF) combining keyword BM25 search with dense vector embeddings for high-precision code retrieval across massive codebases.
- [x] **Async HTTP/2 Connection Pooling & Client Reuse (`httpx2.AsyncClient`)**: Refactored LLM and security scanner network layers to native async connection pooling, mitigating socket exhaustion and accelerating parallel reviews.
- [x] **Trace Waterfall Visualizer CLI (`devops telemetry profile`)**: Terminal-rendered waterfall breakdown and latency heatmap of OpenTelemetry spans for local performance profiling.
- [x] **FastMCP Tool Schema Contract Regression Suite**: Autonomous contract verification testing tool parameters, docstrings, and response formats across all registered FastMCP tools.
- [x] **Keyring Token Housekeeping & Secret Health Auditor (`devops config audit-keys`)**: Housekeeping utility auditing OS Keyring token expiry, permissions, and zero-plaintext leakage.

---

### Enterprise Stability, Performance & Quality Hardening (v0.2.5 - Current Release)
- [x] **Cold Import Latency Optimization & Lazy Loader Consolidation**: Defer heavy third-party dependencies (`kubernetes`, `fastmcp`, `boto3`, `trivy`) to command execution time to maintain sub-second CLI startup.
- [x] **AST Structural Standardization & Strict Indentation Budgeting**: Audited project-wide control flow to ensure zero functions exceed 5 levels of indentation, decomposing nested loops into standard library functional pipelines.
- [x] **Zero-Plaintext Invariant & Keyring Egress Security Audit**: Automated test scanner ensuring zero plaintext secrets, tokens, or credentials exist across `.data/`, `.devops/`, test fixtures, or docs.
- [x] **FastMCP Tool Schema Completeness & Strict Type Validation**: Ensure 100% parameter descriptions, strict type annotations, and structured JSON schemas across 40 FastMCP tools.
- [x] **Unified Domain Exception & POSIX Error Code Taxonomy**: Audit all error paths to ensure strongly typed domain exceptions inheriting from `DevOpsCLIError` with canonical error codes and masked paths.
- [x] **Universal Pydantic Resource Model Catalog**: Standardized request and result resource models (`*Request` / `*Result`) across all domain subsystems (`docker`, `k8s`, `security`, `tf`, `config`, `workspace`, `release`, `ci`, `git`, `ai`) with dynamic FastMCP resource endpoints (`resource://*`).
- [x] **Kubernetes Submodule Modular Decomposition**: Refactored monolithic `k8s.py` into a domain-driven `commands/k8s/` subpackage (`cluster_runtime`, `cluster_context`, `bootstrap`, `stack_lifecycle`, `networking`, `security_audit`, `tls_management`, `diagnostics`).
- [x] **AI Review Cache Invalidation & Warm Starting Point Refinement (`--append-cache`)**: Deterministic file mtime & SHA-256 content-hash cache invalidation with prompt baseline augmentation (`<starting_point>`) for continuous review refinement.
- [x] **Self-Healing Vector Dimension Adaptation & Embedding Chunking**: Auto-recovery on Qdrant collection vector dimension changes with adaptive batch chunking preventing Ollama embedding timeouts.
- [x] **Automated Review Feedback Dataset Continuous Learning (`devops ai review export-feedback`)**: Exporting verified and invalidated findings into structured benchmark datasets (`.data/feedback_dataset.jsonl`) for prompt tuning and fine-tuning.

### Live State Watchers, Continuous Automation & Declarative Command Pipeline (v0.2.6 - Scheduled)
- [x] **Continuous Live Resource & State Watchers (`--watch` / `-w`)**: Real-time terminal auto-refresh and live event streaming across `devops k8s pods --watch`, `devops argo status --watch`, `devops docker stats --watch`, and `devops release status --watch` utilizing `rich.live.Live` with configurable intervals (`--interval`).
- [x] **Adaptive Two-Axis LLM & Freshness Router (`devops_cli.ai.router`)**: Dynamic task routing along Complexity (Simple/Moderate/Complex/Frontier) and Freshness (live web/MCP search vs static context) axes, delivering up to 92% cost savings over uniform frontier calls.
- [ ] **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)**: Modular Harness Slots (Model, Skills, Tools, Sub-Agents) offloading token-intensive exploration and symbol searching to local open models (Granite, Qwen, DeepSeek), achieving 87% input token savings while retaining frontier models for architectural planning.
- [ ] **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**: "Chaos Monkey for Models" validation framework deliberately degrading frontier connections to verify that fallback/local models can pilot tools and pass CI quality gates without human coaching.
- [ ] **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**: Centralized emergency control to cleanly suspend active agent loops, schedulers, and background cron jobs during upstream provider outages or model cutovers.
- [ ] **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen terminal dashboard powered by `Textual` providing responsive tabs for live Kubernetes pods, Minikube services, Docker container metrics, OpenTelemetry span waterfalls, and active AI review findings with keyboard navigation (`1-5`, `q`, `r`).
- [ ] **Continuous IDE File Watcher & Instant AI Review (`devops ai review path --watch`)**: Inotify/watchdog-backed background listener executing automated incremental multi-persona reviews on active file changes with configurable debounce windows (`--debounce-ms`).
- [ ] **Declarative CLI Command Dispatch & Output Presenter Engine (`@cli_command_handler`)**: Universal decorator eliminating boilerplate formatting, dry-run routing, OpenTelemetry span creation, and multi-format serialization (`json|yaml|table|markdown`) across all 30+ Typer subcommands.
- [ ] **Universal Subprocess Execution & SIEM Audit Pipeline (`ProcessExecutionPipeline`)**: Centralized command runner enforcing strict argument list sanitization, bounded timeouts, non-root safety, traceparent propagation, and structured audit trail recording (`.data/logs/audit.jsonl`).
- [ ] **Parallel Async Multi-File Review Pipeline Pool (`devops ai review path`)**: Concurrent async file processing with semaphore bounding (`asyncio.Semaphore`) and token budgeting, cutting multi-file directory review runtimes by up to 70%.
- [ ] **Deterministic Mock LLM Test Isolation & Test Suite Acceleration (< 60s)**: Strict offline mock isolation for LLM/Ollama and Qdrant network calls across test files (`test_ai_cmd`, `test_review_repos`, `test_analyze`), accelerating full test suite execution from 39 minutes to under 60 seconds.
- [x] **In-Memory Embedding LRU Cache & Chunk Dedup (`ai.rag.embeddings`)**: In-memory SHA-256 keyed embedding cache eliminating redundant vector generation calls for identical code chunks across files and commits.
- [x] **Adaptive Test Sharding & Fast Path Test Selector (`devops test run --diff`)**: Git diff-aware test selection executing only impacted test files during local iterations, reducing developer test loop latency from minutes to seconds.
- [x] **Static Code Complexity & Cyclomatic Depth Linter (`devops scan complexity`)**: Automated AST scanner enforcing maximum cyclomatic complexity (< 10) and strict nesting limits across the codebase.
- [ ] **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`)**: Memory leak detection and async socket lifecycle validation across background daemons and MCP workers using `asyncio` and `tracemalloc`.
- [ ] **Autonomous RAG Index Drift Detection & Auto-Reindexing**: Scheduled background verification of vector store sync against workspace git tracking branches.
- [ ] **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**: Automated evaluation suite testing model responses against human-in-the-loop validated feedback datasets.
- [ ] **Sigstore Cosign Container Provenance (`cosign`)**: Keyless container image and manifest signing (`devops docker sign|verify`) integrating with OS Keyring and OIDC tokens for verifiable supply-chain provenance.
- [x] **Syft & Grype Automated SBOM & Vulnerability Scanning (`syft`, `grype`)**: Automated Software Bill of Materials (SBOM) generation (`devops scan sbom`) in CycloneDX/SPDX formats and Grype container runtime vulnerability auditing with configurable severity thresholds (`--fail-on high|critical`).
- [ ] **Infracost FinOps Cloud Cost Engine (`infracost`)**: `devops tf cost` integrating Infracost CLI to evaluate cloud financial impacts on Terraform/OpenTofu diffs, enriching `pm` & `architect` review personas with monthly cost deltas.
- [ ] **Falco eBPF Runtime Security & Anomaly Streamer (`devops k8s security-stream`)**: Real-time streaming kernel anomaly and container syscall events via eBPF probes.
- [ ] **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`)**: Advanced canary and blue-green rollout management with Prometheus metric-based rollback gates.
- [ ] **Local GitOps Project Orchestration Pipeline (`devops argo cd apps bootstrap-gitops`)**: End-to-end declarative reconciliation connecting local background Git daemon (`git://host.minikube.internal:9418/k8s`), ArgoCD Root Application ("App of Apps" pattern), and multi-stack lifecycle (`infra`, `llm`).
- [ ] **Automated GitOps Drift Detection & Webhook Synchronization (`devops argo gitops watch`)**: Real-time git commit and inotify/watchdog triggers automatically signaling ArgoCD applications to reconcile local workspace modifications.
- [ ] **PydanticAI Native Tool Call & Streaming Reasoning Protocol (`pydantic-ai`)**: Deepen native PydanticAI patterns across all AI subcommands with typed dependency injection (`RunContext[DevOpsAgentContext]`), automatic model retry backoff (`@agent.tool(retries=3)`), structured output validation (`result_type=ReviewResult`), and thinking token extraction.
- [ ] **Logfire Structured AI Observability Bridge (`logfire`)**: Native Pydantic Logfire integration binding with OpenTelemetry distributed spans and Rich terminal formatters for live agent reasoning inspection, token throughput counters, and trace waterfalls.
- [ ] **Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (`tree-sitter`)**: Incremental multi-language syntax tree parsing across Python, TypeScript, Go, Rust, Java, and HCL for whole-repository symbol navigation, call-graph synthesis, and structural diff analysis.
- [ ] **Testcontainers Ephemeral Workstation Testing Sandbox (`testcontainers`)**: Isolated Dockerized container fixtures (`testcontainers-python`) spinning up ephemeral Qdrant vector stores, Valkey caches, and Minikube test harnesses during automated unit and integration tests.
- [ ] **Core Dependency Ecosystem Alignment (`pyproject.toml`)**: Routine version upgrades and compatibility validation across runtime and development dependencies:
  - `click` (`8.4.2` → `8.5.0`) & `typer` (`0.27.1` → `0.27.2`)
  - `pydantic` (`2.13.4` → `2.13.5`) & `pydantic-ai` (`2.35.0` → `2.35.3`)
  - `gitpython` (`3.1.60` → `3.1.61`) & `httpx2` (`2.9.0` → `2.12.0`)
  - `ruff` (`0.16.4` → `0.16.5`) & sub-dependencies (`anthropic v1.2.0`, `grpcio v1.83.1`, `platformdirs v4.11.5`)

### Model Curation, AST Streaming & Synthesis Protocol (v0.2.7 - Completed)
- [x] **Model Curation Pipeline & AI Bill of Materials (AIBOM) Generator (`devops scan aibom`)**: Automated supply-chain governance pre-screening model weights with Semgrep/Bandit to block `trust_remote_code=True`, computing RAM/VRAM/MoE sizing heuristics, and compiling verifiable CycloneDX 1.5 AIBOM documents (licenses, security findings, quant benchmarks, runnable manifests).
- [x] **"Big Decides, Small Types, Big Checks" Multi-Tier Code Synthesis Protocol (`devops_cli.ai.agents.synthesis_protocol`)**: Orchestrated multi-tier workflow where frontier models architect specifications, local open-weight models generate concrete implementation diffs, and frontier models verify correctness and approve merge.
- [x] **Zero-Allocation AST Symbol & Token Stream Parser (`devops_cli.ai.ast_stream`)**: Zero-copy tokenizer and AST stream processing yielding classes, functions, async methods, decorators, and imports on demand without allocating intermediate full-tree objects.
- [x] **Cross-Encoder Context Re-Ranker & Deep Semantic RAG Optimization (`devops_cli.ai.rag.reranker`)**: Two-stage dense-sparse retrieval with local cross-encoder re-ranking evaluating query-chunk cross-token interaction density and reciprocal positional discounting.
- [x] **Streaming JSON/YAML Serializers for High-Volume Data Streams (`devops_cli.output.streaming_serializer`)**: Zero-copy, low-overhead streaming serializers for JSON arrays (`stream_json_array`), line-delimited JSON (`stream_jsonl`), and multi-document YAML (`stream_yaml_docs`).
- [x] **SSH Key Prefix Configuration & Options Across Subcommands (`devops ssh`)**: Comprehensive key prefix support across `devops ssh register`, `rotate`, `status`, and `list` honoring configured `settings.ssh.key_prefix`.

### Output Subsystem Modularization, Language Localization & Declarative Dispatch (v0.2.8 - Completed)
- [x] **Modular Output Formatter Engine (`devops_cli.output.formatters`)**: Monolithic formatting deconstruction into `scalars.py`, `tables.py`, and `panels.py` with zero inline table/column formatting across commands.
- [x] **Centralized Language Messages & Terminal Badges (`devops_cli.lang.en.messages`)**: Full localization of terminal badges, finding headers, status indicators, and Kubernetes node states.
- [x] **Declarative Dispatch Tables & Cyclomatic Complexity Elimination**: Replaced procedural `if/elif` branching across AST streaming, AI capabilities, compaction passes, and configuration coercion with declarative registries.
- [x] **Zombie Code & Legacy Shim Removal**: Eliminated obsolete shims (`ai/review/rendering.py`, `models/dry_run.py`, `core/dry_run.py`, `models/github.py`).

### Universal Stage Pipelines, HTTP/2 Broker & K8s Chaos Runner (v0.2.9 - Active Release)
- [x] **Universal Multi-Stage Workflow Orchestration Protocol (`src/devops_cli/pipeline/`)**:
  - Generic, strongly typed stage pipeline abstraction (`StagePipeline[ContextT, ResultT]`, `PipelineStage`) unifying sequential and DAG-based stage execution.
  - Granular `@trace_span` telemetry waterfalls, error isolation, and metrics collection.
- [x] **Unified Async HTTP/2 Connection & Security Broker (`HttpClientBroker`, `devops_cli.http.broker`)**:
  - Centralized connection pool manager providing persistent keepalive, HTTP/2 multiplexing, Server-Side Request Forgery (SSRF) private network isolation, and distributed traceparent propagation.
- [x] **Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`)**:
  - Declarative chaos engineering runner injecting pod disruptions and validating cluster recovery.
- [x] **Continuous IDE File Watcher & Instant AI Review (`devops ai review path --watch`)**:
  - Watchdog-backed background listener executing automated incremental multi-persona reviews on active file changes with configurable debounce windows (`--debounce-ms`).
- [x] **Enterprise Vault & Cloud KMS Secret Broker (`devops config vault`, `devops vault`)**:
  - HashiCorp Vault REST API and Cloud KMS integrations with KV-v2 engine support, zero-plaintext storage, and seamless OS Keyring fallback.
- [x] **Isolated Dockerized Workload Sandbox Environment (`devops test sandbox` / `devops docker sandbox`)**:
  - Ephemeral, rootless container test harness and isolated execution sandbox for multi-container integration tests with memory, cpu, and network constraints.
- [x] **Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`)**:
  - AST- and lockfile-aware autonomous patching engine resolving CVEs via lockfile updates (`uv lock --upgrade-package`), dry-run summaries, and git topic branch staging.
- [x] **Kubernetes Background Port-Forward Daemon Management (`devops k8s port-forward --daemon|status|stop`)**:
  - Background process lifecycle tracking with managed PID state (`.data/k8s/port_forwards.json`), status inspection, and graceful termination.

### Multi-Cloud Mesh & Production Ecosystem (v0.3.0 - Future Vision)
- [ ] **Multi-Region Workstation Mesh & Cluster Federation**: Distributed cluster management across hybrid on-prem homelab and multi-cloud Kubernetes clusters with automatic service mesh routing.
- [ ] **Autonomous Self-Healing Agent Pipeline**: Closed-loop diagnostic engine capable of discovering cluster incidents, generating corrective patches, running CI gates, and executing rollback.
- [ ] **Cloud-Native Ephemeral Test Environment Provisioner (`devops env ephemeral up/down`)**: Automated provisioning of isolated namespace staging environments with seeded mock databases, synthetic datasets, and TLS ingresses on minikube or cloud clusters.
- [ ] **Zero-Trust Git Commit & Tag Cryptographic Verification (`devops release verify-signatures`)**: Automated verification of SSH/GPG and Sigstore keyless commit signatures across repository history and pull requests.
- [ ] **Distributed Multi-Cluster Telemetry & OTel Egress Mesh**: Global trace and metric federation across hybrid workstation topologies with automated anomaly alerting.
- [ ] **Distributed Cache & Shared Semantic Embeddings Sync (`devops ai cache sync`)**: S3 / OCI-backed shared LLM response and vector embedding cache for remote engineering teams.
- [ ] **JIT Python 3.14 Tail-Call & Bytecode Optimization Benchmarking**: Comprehensive runtime benchmarks utilizing Python 3.14+ specialization and JIT compiler tiers.

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
| | Checkov IaC Static Policy & Compliance | `checkov` CLI | High | Low | v0.2.2 | ✅ Completed |
| | TFLint Cloud Provider Linter | `tflint` CLI | High | Low | v0.2.2 | ✅ Completed |
| | Dive Docker Layer Efficiency Analyzer | `dive` CLI | High | Low | v0.2.2 | ✅ Completed |
| | Kubeconform Fast OpenAPI Schema Validator | `kubeconform` CLI | High | Low | v0.2.2 | ✅ Completed |
| | Dynamic Cost- & Latency-Aware LLM Router | RouteLLM / Pydantic | High | Low | v0.2.2 | ✅ Completed |
| | Prometheus In-Memory Metrics Registry & Exporter | `prometheus-client` | High | Low | v0.2.2 | ✅ Completed |
| | AST Parsing Cache & Structural Memoization | `ast` / LRU Cache | High | Low | v0.2.2 | ✅ Completed |
| | Automated Workspace & Data Tier Cleanup | Standard Library (`pathlib`, `shutil`) | High | Low | v0.2.2 | ✅ Completed |
| | Knowledge Base Documentation Freshness Linter | Click/Typer Introspection | High | Low | v0.2.2 | ✅ Completed |
| | Stern Multi-Pod Live Log Streamer | `stern` CLI | High | Low | v0.2.3 | ✅ Completed |
| | Helm Diff Deployment Impact Previewer | `helm-diff` plugin | High | Low | v0.2.3 | ✅ Completed |
| | Difftastic Structural Syntax-Aware AST Diff Provider | `difft` CLI | High | Low | v0.2.3 | ✅ Completed |
| | Spec-Driven Architecture & Contract Verification | Markdown Specs / Pydantic | High | Low | v0.2.3 | ✅ Completed |
| | OpenTelemetry Log Correlation Bridge | `opentelemetry-appender-logging` | High | Low | v0.2.3 | ✅ Completed |
| | Dead Code & Unused Symbol Pruning | `vulture` / `ruff` | High | Low | v0.2.3 | ✅ Completed |
| | Toolchain & Lockfile Maintenance Review Gate | `uv` / GitHub Actions | High | Low | v0.2.3 | ✅ Completed |
| | Prompt Mutation Testing & Benchmark Guardrails | Pytest / Feedback Dataset | High | Low | v0.2.4 | ✅ Completed |
| | tfcmt Automated PR Plan Notifier | `tfcmt` CLI | High | Low | v0.2.4 | ✅ Completed |
| | Trace Waterfall Visualizer CLI (`devops telemetry profile`) | Rich / OTel Spans | Medium | Low | v0.2.4 | ✅ Completed |
| | FastMCP Tool Schema Contract Regression Suite | FastMCP / Pytest | High | Low | v0.2.4 | ✅ Completed |
| | Keyring Token Housekeeping & Secret Health Audit | `keyring` / Pydantic | Medium | Low | v0.2.4 | ✅ Completed |
| | Cold Import Latency Optimization & Lazy Loader | Python Importlib | High | Low | v0.2.5 | ✅ Completed |
| | AST Structural Standardization & Indentation Budget | AST / Functional | High | Low | v0.2.5 | ✅ Completed |
| | Zero-Plaintext Invariant & Keyring Egress Audit | Keyring / Pytest | High | Low | v0.2.5 | ✅ Completed |
| | FastMCP Tool Schema Completeness & Strict Types | FastMCP / Typing | High | Low | v0.2.5 | ✅ Completed |
| | Unified Domain Exception Taxonomy | DevOpsCLIError / POSIX | High | Low | v0.2.5 | ✅ Completed |
| | Universal Pydantic Resource Model Catalog | Pydantic v2 / FastMCP | High | Low | v0.2.5 | ✅ Completed |
| | Kubernetes Submodule Modular Decomposition | Python Package Architecture | High | Low | v0.2.5 | ✅ Completed |
| | AI Review Cache Invalidation & `--append-cache` | SHA-256 / Prompt Augmentation | High | Low | v0.2.5 | ✅ Completed |
| | Self-Healing Vector Dimension & Embedding Chunking | Qdrant / Ollama | High | Low | v0.2.5 | ✅ Completed |
| | Automated Review Feedback Dataset Learning | Dataset Export / Fine-Tuning | High | Low | v0.2.5 | ✅ Completed |
| | Model Dependency Chaos Engineering Suite | Pytest / Fallback Routing | High | Low | v0.2.6 | 📋 Scheduled |
| | Agent Constellation Quiesce & Failover Controller | Asyncio / State Machine | High | Low | v0.2.6 | 📋 Scheduled |
| | Static Code Complexity & Cyclomatic Depth Linter | AST / Standard Library | High | Low | v0.2.6 | 📋 Scheduled |
| | Deterministic Mock LLM Test Isolation (< 60s CI) | `unittest.mock` / Pytest | High | Low | v0.2.6 | 📋 Scheduled |
| | In-Memory Embedding LRU Cache & Chunk Dedup | `functools` / Hash | High | Low | v0.2.6 | 📋 Scheduled |
| | Adaptive Test Sharding & Fast Path Test Selector | Pytest / Git | High | Low | v0.2.6 | 📋 Scheduled |
| | Autonomous RAG Index Drift Detection & Auto-Reindex | Git / Qdrant Sync | High | Low | v0.2.6 | 📋 Scheduled |
| | Multi-Model LLM Benchmark Evaluation Harness | Pytest / Feedback Dataset | High | Low | v0.2.6 | 📋 Scheduled |
| | Deterministic Async Memory & Pool Profiler | `asyncio` / `tracemalloc` | Medium | Low | v0.2.6 | 📋 Scheduled |
| | Streaming JSON/YAML Serializer for Large Reviews | `orjson` / Pydantic | High | Low | v0.2.7 | ✅ Completed |
| | Zero-Allocation Tokenizer & AST Stream Parser | `tokenize` / Generator | High | Low | v0.2.7 | ✅ Completed |
| | Zero-Trust Git Commit & Tag Signature Verifier | `git`, GPG, Sigstore | High | Low | v0.3.0 | 💡 Future Vision |
| | JIT Python 3.14 Bytecode Optimization Benchmarking | `pytest-benchmark` / JIT | Medium | Low | v0.3.0 | 💡 Future Vision |
| **Strategic Investments** | OpenTofu Multi-Cloud IaC Modules (`tf/`) | OpenTofu / AWS / Azure / GCP | High | High | v0.1.9 | ✅ Completed |
| | Minikube Service Auto-Config & 7-Gate CI | Minikube / GitHub Actions | High | High | v0.1.5 | ✅ Completed |
| | DevContainer Shell Script Replacement Engine | Python Subprocess / Typer | High | Medium | v0.1.7 | ✅ Completed |
| | Enhanced AI/LLM Scratchpad Reasoning Buffer | Pydantic / Rich | High | Medium | v0.1.7 | ✅ Completed |
| | FastAPI REST & OpenAPI Service Engine (`devops serve`) | FastAPI / Uvicorn | High | Medium | v0.2.0 | ✅ Completed |
| | OpenTelemetry Distributed Tracing & Metrics | OpenTelemetry SDK / Prometheus | High | Medium | v0.2.0 | ✅ Completed |
| | PydanticAI Multi-Agent Pipeline Orchestration | `pydantic-ai`, `fastmcp` | High | Medium | v0.2.1 | ✅ Completed |
| | Semgrep AST Pattern Matcher | `semgrep` CLI | High | Medium | v0.2.1 | ✅ Completed |
| | Multi-Agent Adversarial Debate (MAD) Verification | PydanticAI / Multi-Agent | High | Medium | v0.2.3 | ✅ Completed |
| | Review Pipeline Modular Decomposition | Python Package Refactoring | High | Medium | v0.2.3 | ✅ Completed |
| | Automated Unit Test Synthesizer & Execution | Pytest / AST / LLM | High | Medium | v0.2.4 | ✅ Completed |
| | Async HTTP/2 Connection Pooling & Client Reuse | `httpx2.AsyncClient` | High | Medium | v0.2.4 | ✅ Completed |
| | Streaming SSE / WebSocket Agent Reasoning Feed | FastAPI SSE / WebSockets | High | Medium | v0.2.4 | ✅ Completed |
| | Aider-Style Tree-Sitter / AST Repository Map Generator | AST / Pydantic | High | Medium | v0.2.4 | ✅ Completed |
| | Hybrid Dense-Sparse RAG Search (BM25 + Qdrant) | Qdrant / RRF | High | Medium | v0.2.4 | ✅ Completed |
| | Adaptive Two-Axis LLM & Freshness Router | RouteLLM / Pydantic | High | Medium | v0.2.6 | ✅ Completed |
| | Sub-Agent Local Offloading Engine & Harness Slots | PydanticAI / Ollama / vLLM | High | Medium | v0.2.8 | 📋 Scheduled |
| | Continuous Live Resource & State Watchers (`--watch`) | `rich.live.Live` | High | Medium | v0.2.6 | ✅ Completed |
| | Interactive Terminal UI Dashboard (`devops dashboard`) | `textual` TUI | High | Medium | v0.2.8 | 📋 Scheduled |
| | Continuous IDE File Watcher & Instant AI Review | `watchdog` / AST | High | Medium | v0.2.8 | 📋 Scheduled |
| | Parallel Async Multi-File Review Pipeline Pool | `asyncio` / Typer | High | Medium | v0.2.8 | 📋 Scheduled |
| | Declarative CLI Command Dispatch Engine | Typer / Python Decorators | High | Medium | v0.2.8 | 📋 Scheduled |
| | Universal Subprocess Execution Pipeline | Python Subprocess / OTel | High | Medium | v0.2.8 | 📋 Scheduled |
| | Sigstore Cosign Container Provenance | `cosign` CLI / OS Keyring | High | Medium | v0.2.8 | 📋 Scheduled |
| | Syft & Grype Automated SBOM & Vulnerability Scanning | `syft`, `grype` | High | Medium | v0.2.6 | ✅ Completed |
| | Infracost FinOps Cloud Cost Engine | `infracost` CLI | High | Medium | v0.2.8 | 📋 Scheduled |
| | Multi-Cluster ArgoCD Fleet Sync & Rollouts | Argo Rollouts / Prometheus | High | High | v0.2.8 | 📋 Scheduled |
| | Local GitOps Project Orchestration Pipeline | Git Daemon / ArgoCD App-of-Apps | High | Medium | v0.2.8 | 📋 Scheduled |
| | Automated GitOps Drift Detection & Webhook Sync | Watchdog / ArgoCD REST | High | Medium | v0.2.8 | 📋 Scheduled |
| | Core Dependency Ecosystem Alignment | `uv lock --upgrade` / PyPI | Medium | Low | v0.2.8 | 📋 Scheduled |
| | Falco eBPF Runtime Security & Anomaly Streamer | `falco` / eBPF | High | Medium | v0.2.8 | 📋 Scheduled |
| | Model Curation Pipeline & AIBOM Generator | Semgrep / AST / CycloneDX | High | Medium | v0.2.7 | ✅ Completed |
| | "Big Decides, Small Types, Big Checks" Synthesis Protocol | Multi-Agent / PydanticAI | High | Medium | v0.2.7 | ✅ Completed |
| | Universal Multi-Stage Workflow Orchestration Protocol | Python Generics / Pydantic | High | Medium | v0.2.8 | 📋 Scheduled |
| | Unified Async HTTP/2 Connection & Security Broker | `httpx2` / SSRF Guard | High | Medium | v0.2.8 | 📋 Scheduled |
| | Automated Vulnerability Remediation PR Engine | AST / Pytest / Git | High | Medium | v0.2.8 | 📋 Scheduled |
| | Cross-Encoder Context Re-Ranker & Deep Semantic RAG | Cross-Encoder / Qdrant | High | Medium | v0.2.7 | ✅ Completed |
| | Local Kubernetes Chaos & Fault Injection Engine | `chaos-mesh` / `tc` | High | Medium | v0.2.8 | 📋 Scheduled |
| | Enterprise Vault & KMS Secret Broker | `hvac`, Cloud KMS SDKs | Medium | High | v0.2.8 | 📋 Scheduled |
| | Trace-Driven Automated Performance Regression Detection | OTel / Prometheus | High | Medium | v0.2.8 | 📋 Scheduled |
| | Isolated Dockerized Workload Sandbox Environment | Docker / Testcontainers / Dagger | High | Medium | v0.2.8 | 📋 Scheduled |
| | Automated Vector Storage Compaction & Pruning | Qdrant Client / SQLite | Medium | Medium | v0.2.8 | 📋 Scheduled |
| | Multi-Region Workstation Mesh & Cluster Federation | Kubernetes / Fleet | High | High | v0.3.0 | 💡 Future Vision |
| | Autonomous Self-Healing Agent Pipeline | PydanticAI / Diagnostic | High | High | v0.3.0 | 💡 Future Vision |
| | Cloud-Native Ephemeral Test Environment Engine | Minikube / Helm / Ingress | High | Medium | v0.3.0 | 💡 Future Vision |
| | Distributed Multi-Cluster Telemetry & OTel Egress Mesh | OTel Collector / Prometheus | High | High | v0.3.0 | 💡 Future Vision |
| | Distributed Cache & Shared Semantic Embeddings Sync | S3 / OCI / SQLite | High | Medium | v0.3.0 | 💡 Future Vision |
| **Tactical Additions** | Line-Level GitHub PR Inline Comments | PyGithub / GitHub REST API | High | High | v0.1.1 | ✅ Completed |
| | Human Feedback Dataset Exporter | JSONL / Pydantic | High | Medium | v0.1.1 | ✅ Completed |
| | Custom Team Persona Overrides (`.devops/personas/`) | Jinja2 / Markdown | High | Medium | v0.1.1 | ✅ Completed |
| | Kyverno & OPA Gatekeeper Admission Validator | `kyverno-cli`, `opa` | Medium | Medium | v0.2.3 | ✅ Completed |
| | k6 Performance & Latency Smoke Tester | `k6` CLI | Medium | Medium | v0.2.3 | ✅ Completed |
| | Dagger Containerized Python Pipeline Engine | `dagger-io` SDK | Medium | High | v0.2.3 | ✅ Completed |
| | Architecture & Threat Diagram Synthesis | `diagrams`, `mermaid-cli` | Medium | Medium | v0.2.4 | ✅ Completed |
| | Automated PR Remediation Branch Generator | Git / GitHub API | Medium | Medium | v0.2.4 | ✅ Completed |
| | Ephemeral Headless Keyring Auth | `keyring.backends` | Medium | Medium | v0.1.1 | ✅ Completed |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
| | Heavyweight Monolithic Orchestrators | Full LangChain | Low | High | — | ❌ Rejected (FastMCP + PydanticAI) |
