# Release Notes — devops-cli v0.2.9

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, vector embedding benchmarks, TLS certificate automation, OpenTelemetry observability, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.2.9

### 🔄 Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`)
- **Strongly-Typed Stage Pipelines**: Introduced generic `StagePipeline[ContextT, ResultT]` and `PipelineStage` framework supporting sequential and DAG-based stage execution with scratchpad context passing.
- **Granular Telemetry & Isolation**: Built-in `@trace_span` waterfalls, error containment, execution metrics (`pipeline_runs_total`, `pipeline_run_duration_seconds`), and fail-fast controls.

### 🌐 Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`)
- **Shared Connection Pooling**: Thread-safe `HttpClientBroker` managing shared `httpx2` client connection pools with HTTP/2 multiplexing and persistent keepalive.
- **SSRF Defense & Traceparent Propagation**: Integrated destination validation against private network egress and automatic W3C traceparent context header injection.

### 💥 Local Kubernetes Chaos & Fault Injection Runner (`src/devops_cli/k8s/chaos_runner.py`)
- **Declarative Chaos Experiments**: Introduced `ChaosFaultRunner` supporting declarative pod disruptions, recovery time observation, and automatic rollback handling.

### 👁️ Continuous IDE File Watcher & Instant Review (`devops ai review path --watch`)
- **Automated Incremental Reviews**: Integrated `--watch` / `-w` and `--debounce-ms` into `devops review path` leveraging `DebouncedFileWatcher` to trigger instant multi-persona reviews upon local file modifications.

### 🔑 Automated Kubernetes Stack Credential Synchronization (`devops k8s sync-secrets`)
- **Zero-Plaintext Secret Extraction**: Automated discovery and retrieval of ArgoCD and Grafana admin passwords from Kubernetes cluster secrets directly into OS Keyring (`argocd_password`, `grafana_password`).
- **Seamless Stack Deployment**: Auto-synchronizes admin credentials on `devops k8s deploy-stack` and `devops k8s sync-secrets`.

---

## 🚀 Highlights of v0.2.8

### 🎨 Output Subsystem Modularization & Formatting Engine Deconstruction (`src/devops_cli/output/formatters/`)
- **Deconstructed Formatter Hub**: Modularized monolithic formatting logic into dedicated, cohesive submodules under `src/devops_cli/output/formatters/`:
  - `scalars.py`: Primitive conversions, byte formatting, relative duration/age stamps, code spans, links, and status/severity badges.
  - `tables.py`: Polymorphic table rendering and domain payload builders across Kubernetes, Docker, ArgoCD, Terraform, Benchmarks, and Reviews.
  - `panels.py`: Rich finding panels, AI review summaries, and ArgoCD application detail views.
- **Zero-Boilerplate Public Formatting API**: Enforced public methods in `devops_cli.output` project-wide so CLI commands never build Rich tables, columns, or format strings inline.

### 🌐 Complete Language Localization & Centralized Message Catalog (`src/devops_cli/lang/en/messages.py`)
- **Centralized Language Catalog Expansion**: Added `BadgeMessages` and `OutputMessages` to ensure 100% of terminal badges, finding headers, labels, ArgoCD status indicators, and Kubernetes node states are sourced from `MESSAGES`.
- **Zero Hardcoded Display Strings**: Replaced ad-hoc inline text with localized catalog keys across formatting and command layers.

### ⚡ Declarative Dispatch Tables & Cyclomatic Complexity Elimination
- **Table-Driven AST Streaming (`src/devops_cli/ai/ast_stream.py`)**: Replaced node type `if/elif` ladders with a declarative node handler registry (`_NODE_HANDLERS`) and concise decorator extractors.
- **Native Tool & Capability Registries (`src/devops_cli/ai/agents/capabilities.py`, `workflow.py`)**: Replaced tool `isinstance` branches with declarative configuration and prompt builders (`_NATIVE_TOOL_SETTINGS_BUILDERS`), unified local tool extraction (`_extract_local_tools`), and decoupled async agent invocation (`_invoke_agent_callable`).
- **Declarative Truncation & Compaction Handlers (`src/devops_cli/ai/harness/compaction.py`)**: Implemented `_TRUNCATION_FORMATTERS` and `_apply_compactor` for cascading compaction passes.
- **Type Coercion Extraction (`src/devops_cli/config/settings.py`)**: Extracted `_coerce_setting_value` to simplify dotted-path settings mutation.

### 🧹 Ruthless Zombie Code & Shim Removal
- **Deleted Obsolete Shims**: Removed legacy re-export shims `src/devops_cli/ai/review/rendering.py`, `src/devops_cli/models/dry_run.py`, and `src/devops_cli/core/dry_run.py`.
- **Consolidated Models**: Merged `SSHKeyInfo` into `src/devops_cli/models/ssh.py` and deleted redundant `src/devops_cli/models/github.py`.
- **Clean Re-Exports**: Cleaned `src/devops_cli/output/__init__.py::__all__` duplicates and rewired imports directly to authoritative modules.

### 📚 Documentation Alignment & DevContainer Standardization
- **DevContainer Image Reference Standardization**: Pinned container tag examples in `docs/DEVCONTAINER_USAGE.md` to current release (`v0.2.8`).
- **Milestone v0.2.8 Specifications**: Aligned `docs/ROADMAP.md` and `docs/PENDING_FEATURES.md` reflecting completed v0.2.8 architecture milestones.

---

## 🚀 Highlights of v0.2.7

### 🛡️ AI Bill of Materials (AIBOM) Generator (`devops scan aibom`)
- **CycloneDX 1.5 AIBOM Manifests**: Generates machine-readable AI model supply-chain records capturing model identities, parameter counts, weights hashes (SHA-256), and licensing categorizations (Permissive, Open-Source, Capped, RAIL, Proprietary).
- **Static Model Security Gating**: Inspects custom code repositories and `config.json` for `trust_remote_code=True` and unverified remote execution scripts before compute allocation.
- **Hardware Sizing Heuristics**: Dynamically estimates serving VRAM, system RAM, and disk storage requirements for dense and Mixture-of-Experts (MoE) models across quantization bit depths.

### ⚡ Zero-Allocation AST & Token Stream Parser (`devops_cli.ai.ast_stream`)
- **Generator-Based AST Streaming**: Yields code symbols (classes, functions, async methods, imports, decorators) on demand with zero intermediate full-tree allocations, speeding up large-scale codebase mapping.
- **Token Line Streaming**: Evaluates line-level token depths, comments, and string literal boundaries for fast AST inspection.

### 🔍 Cross-Encoder Context Re-Ranker & Deep Semantic RAG (`devops_cli.ai.rag.reranker`)
- **Cross-Token Relevance Re-Ranking**: Evaluates query-chunk semantic overlap, cross-token coverage density, and reciprocal positional discounting to prioritize the most relevant chunks before context assembly.

### 🤖 "Big Decides, Small Types, Big Checks" Synthesis Protocol (`devops_cli.ai.agents.synthesis_protocol`)
- **Three-Stage Multi-Agent Orchestration**: Decouples complex AI workflows into frontier planning (Big Decides), local fast implementation drafting (Small Types), and frontier auditor verification (Big Checks).

### 📦 High-Performance Streaming Serializers (`devops_cli.output.streaming_serializer`)
- **Low-Memory Dataset Streaming**: Formats and streams large JSON arrays, line-delimited JSON (JSONL), and multi-document YAML with minimal memory footprint.

### 🔑 SSH Key Prefix Configuration & Discovery
- **Comprehensive Key Prefix Support Across Subcommands**: `devops ssh register`, `devops ssh rotate`, `devops ssh status`, and `devops ssh list` now fully honor the `ssh.key_prefix` setting as well as optional CLI `--prefix` / `-p` flags.
- **Prefix-Aware Discovery & Registration**: `find_newest_key()`, `list_managed_keys()`, and `list_managed_keys_info()` filter managed keys by prefix with automatic fallback, and generate clean GitHub registration titles without redundant date suffixes.

---

## 🚀 Highlights of v0.2.6

### 🧠 Multi-Dimensional AI Model Routing & Governance
- **Dynamic Multi-Axis Model Router (`devops_cli.ai.router.LLMRouter`)**: Dynamically routes LLM tasks across two decision axes (Task Complexity: `LOW`, `MEDIUM`, `HIGH`, `FRONTIER` and Task Freshness: `STATIC_CONTEXT`, `LIVE_MCP_LOOKUP`, `EXTERNAL_WEB_SEARCH`) and Data Sensitivity (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL_AIRGAP`).
- **Air-Gap Data Egress Enforcement**: Automatically redirects confidential workloads to local air-gapped models (`ollama`) and provisions tailored local fallback chains, preventing proprietary code egress to third-party cloud LLMs.
- **Cost & Latency Tier Forecasting**: Estimates dollar costs and categorizes expected latency tiers (`sub-second`, `fast-interactive`, `multi-second`, `deep-reasoning`) for every AI execution plan.

### 🔍 AST Code Complexity & SBOM Generator (`devops scan`)
- **AST Cyclomatic Complexity Analyzer (`devops scan complexity`)**: Computes per-function and per-module cyclomatic complexity scores and identifies high-risk nested branching across Python codebases.
- **Software Bill of Materials Generator (`devops scan sbom`)**: Generates CycloneDX and SPDX-compliant SBOM documents from active lockfiles and installed packages.

### 🧪 Git-Diff Aware Test Selector (`devops test run --diff`)
- **Targeted Test Execution**: Discovers and runs only the test files affected by unstaged or branch-level git diffs, dramatically speeding up inner dev loops.

### ⏱️ Real-Time Resource & State Watchers (`--watch` / `-w`)
- **Live Terminal Refresh Across Subsystems**: Added `--watch` / `-w` and `--interval` support powered by `rich.live.Live` across `devops k8s pods --watch`, `devops docker stats --watch`, `devops argo cd apps list --watch`, and `devops release status --watch`.
- **Live Docker Metrics**: Real-time CPU%, memory net usage/limit, and network RX/TX I/O statistics table with color-coded utilization thresholds.
- **Live Pod Health Monitoring**: Real-time pod phase, ready container counts, restart metrics, and human-readable age reporting with label selector filtering.

### ⚡ In-Memory SHA-256 Embedding LRU Cache (`ai.rag.embeddings`)
- **Vector Deduplication Acceleration**: Thread-safe in-memory LRU cache (`_EmbeddingLRUCache`) keyed by SHA-256 hash of text and model identifier, eliminating redundant vector generation calls across RAG queries and indexing operations.
- **Prometheus Metric Instrumentation**: Continuous monitoring of cache hits, misses, and active size via `GLOBAL_METRICS`.

### 📦 DevContainer Standalone Binary Isolation
- **System-Wide Binary Integrity**: Preserves the native `/usr/local/bin/devops` installation in pre-built images without overwriting it with fragile workspace symlinks.
- **Cross-Platform SSH Mount Support**: Harmonized `${localEnv:HOME}${localEnv:USERPROFILE}/.ssh` mounting across Linux, macOS, and Windows workstation environments.

---

## 🚀 Highlights of v0.2.5

### 🔒 Zero-Plaintext Invariant & Secret Compliance
- **Continuous Secret Regression Audit (`tests/test_zero_plaintext_invariants.py`)**: Automated verification ensuring zero plaintext tokens, passwords, or credentials exist across `.data/`, `.devops/`, config files, test fixtures, or docs.
- **Unified Domain Exception Taxonomy (`devops_cli.exceptions`)**: Standardized strongly typed exceptions (`InsecureConfigError`, `KeyringUnavailableError`, `SSRFBlockedError`) with explicit POSIX exit codes, canonical machine-readable codes, and sanitized target paths.

### ⚡ Code Structure Standardization & Indentation Limits
- **Strict AST Indentation Budgeting**: Audited and refactored project-wide control flow to ensure **0** functions exceed 5 levels of indentation, decomposing nested loops into standard library functional pipelines.
- **Cold Import Optimization**: Verified sub-second CLI entry overhead with lazy loading of all heavy third-party packages (`kubernetes`, `fastmcp`, `boto3`, `trivy`).

### 🛠️ FastMCP Toolset Expansion & Resource Schemas (40 Tools)
- **Universal Pydantic Resource Catalog (`devops_cli.models`)**: Comprehensive request/result models (`*Request` / `*Result`) across all subsystems (`docker`, `k8s`, `security`, `tf`, `config`, `workspace`, `release`, `ci`, `git`, `ai`).
- **Dynamic FastMCP System State Resources**: Direct integration for `resource://workspace/status`, `resource://config/active`, `resource://telemetry/status`, and `resource://release/status`.
- **FastMCP Schema Completeness**: 100% parameter descriptions, strict type annotations, structured JSON schemas, and flag injection defenses across 40 registered tools.
- **New Tools Registered**: `ai_repomap`, `ai_diagram`, `ai_test_gen`, `config_audit_keys`, `telemetry_profile`, and `tf_notify_plan`.

### 📦 DevContainer Workspace Cache Volumes & Storage Isolation
- **Dedicated Volume Mount Optimization**: Added dedicated Docker named volumes for `.uv`, `.venv`, `.mypy_cache`, `.pytest_cache`, and `.ruff_cache` to bypass host-OS translation latency and achieve native Linux `ext4` I/O speeds on Windows development machines.
- **Automated Lifecycle Permission Enforcement**: Hardened `devops devcontainer post-create` and `post-start` lifecycle hooks to ensure all workspace volumes and cache directories are created with `0755` permissions and owned by `vscode`.
- **Workspace Data Tier Standardization**: Centralized all exploratory and scratch scripts into `.data/scratch/`, isolating temporary data artifacts cleanly within the `.data/` tier.
- **Team IDE Configuration Sharing**: Updated `.gitignore` to allow tracking of shared `.vscode/` team configurations (including `.vscode/mcp.json`) while filtering local user overrides.

### 🛡️ AI Review Security Hardening & Closed-Loop Feedback
- **Structural Diff Path Containment (`devops_cli.ai.diff.difftastic`)**: Enforced strict boundary containment with `resolve_safe_subpath`, preventing arbitrary file reading and secret leakage outside repository boundaries (CWE-200 / CWE-284).
- **Absolute Target Path Resolution (`devops_cli.commands.review`, `devops_cli.ai.review.pipeline`)**: Enforced canonical absolute path resolution across review and pre-analysis commands, eliminating relative `.` path ambiguity and path segment duplication in finding locations.
- **Closed-Loop Feedback Dataset Export (`devops ai review export-feedback`)**: Exported verified security findings into `.data/feedback_dataset.jsonl` to ground LLM reasoning and reinforce the self-improvement training loop.

---

## 🚀 Highlights of v0.2.4

### 📊 Trace Waterfall Visualizer CLI (`devops telemetry profile`)
- **Visual Span Waterfall**: Interactive terminal waterfall timeline with latency heatmaps and status badges.
- **Granular Command Profiling**: Inspect span trees by `--trace-id`, inspect `--last` trace, or profile arbitrary subcommands directly.

### 🔒 Keyring Secret Health Auditor (`devops config audit-keys`)
- **Zero-Plaintext Validation**: Audits OS Keyring backend health and scans project configuration files for accidental plaintext token leaks.

### 🤖 AI Developer Tooling & Real-Time Streams
- **AST Repository Map Generator (`devops ai repomap`)**: Whole-repo symbol hierarchy extraction for compact LLM context without token overflow.
- **Architecture & Threat Modeling Diagrams (`devops ai diagram`)**: Generates visual Mermaid architecture and STRIDE threat flowcharts.
- **Streaming SSE & WebSocket Feeds (`devops serve /stream` & `/ws`)**: Live Server-Sent Events and duplex WebSocket feeds delivering real-time agent token and reasoning traces.
- **Prompt Mutation Benchmarks (`devops ai prompt-eval`)**: Automated evaluation framework benchmarking persona prompt variations against ground truth feedback datasets.
- **Automated Unit Test Synthesizer (`devops ai test-gen`)**: Generates isolated pytest suites for active file diffs.
- **PR Remediation Branch Generator (`devops ai review auto-fix`)**: Autonomous creation of `fix/finding-<id>` topic branches with staged patches.

### ⚡ Infrastructure, Semantic RAG & HTTP/2
- **tfcmt PR Plan Notifier (`devops tf notify-plan`)**: Posts structured, collapsible OpenTofu/Terraform plan diff summaries to pull requests.
- **Hybrid Dense-Sparse RAG Tier**: Reciprocal Rank Fusion (BM25 + Qdrant RRF) for high-precision code retrieval.
- **Async HTTP/2 Connection Pooling**: Native async client reuse mitigating socket exhaustion.

---

## 🚀 Highlights of v0.1.13

### ⚡ Embedding Model Benchmark Suite (`devops ai benchmark --type embedding`)
- **Vector Embedding Model Evaluation**: Dedicated benchmark runner for dense vector embedding models (`qwen3-embedding`, `nomic-embed-text`, `all-minilm`, `bge-*`, `text-embedding-3-*`).
- **Semantic Retrieval Quality & Accuracy**: Evaluates Recall@1, Recall@3, Mean Reciprocal Rank (MRR), and Cosine Margin against a domain-specific evaluation corpus of 15 DevOps query-passage pairs and 10 distractors across Security, Kubernetes, Architecture, CI/CD, and Infrastructure.
- **Latency & Throughput**: Benchmarks single-query p50/p95 latency (ms) and batch throughput (items/sec and chars/sec).
- **Auto-Detection & Multi-Server Routing**: Automatically routes embedding models to vector evaluation and supports parallel multi-server Ollama distribution.

### 🔒 Local & Homelab TLS Certificate Automation (`devops tls`, `devops cert`)
- **X.509 Certificate Generation**: Native CA and TLS server/client certificate issuance with SAN extensions for IP addresses, hostnames, localhost, homelab `.lan`/`.local` domains, and Kubernetes service FQDNs.
- **Kubernetes Secret Provisioning**: Automated secret injection (`devops tls inject-k8s-secret`, `devops k8s enable-tls`) and cert-manager ClusterIssuer integration.

### 📊 End-to-End OpenTelemetry Observability (`devops telemetry`, `devops otel`)
- **OTLP Trace Export**: Distributed tracing across all CLI commands and AI multi-agent pipeline stages.
- **Observability Stack**: OTLP endpoint configuration and Jaeger deployment manifests (`k8s/otel/jaeger.yaml`).

### 🧼 Standard Library Code Hygiene & AST Tokenization
- **Standard Library Parsing**: Replaced ad-hoc keyword lists and regex string matching in `reference_extractor.py` with standard `ast`, `tokenize`, `packaging.requirements.Requirement`, `tomllib`, `json`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, and `tldextract`.
- **PEP 508 & PEP 621 Support**: Standard requirement parsing for dependencies, optional groups, and PEP 735 dependency groups.
- **Review Pipeline Optimization**: Filtered universal standard library imports to eliminate graph explosion in individual file review JSONs.

---


## 🚀 Highlights of v0.1.8

### 🔄 Automated Release Cycle Suite (`devops release`)
- **Native Release Management**: Implemented `devops release status`, `devops release prepare`, `devops release check`, `devops release notes`, and `devops release tag` automating version bumping, changelog updates, docs synchronization, and pre-release quality validation.
- **FastMCP Server Release Tools**: Added `release_status` MCP tool allowing autonomous AI agents to query version consistency, git tags, and documentation freshness directly over Model Context Protocol.

### 📚 Dynamic Documentation Engine & Auto-Sync
- **`devops docs` Engine**: Added dynamic Click/Typer introspection engine generating markdown reference manuals (`CLI_REFERENCE.md`, `MCP_TOOLS.md`, `ENV_VARS.md`) and synchronizing the `README.md` Command Matrix.
- **Continuous Documentation Gate**: Integrated `devops docs check` directly into `devops ci run` ensuring stale documentation automatically fails CI validation.

### 🏛️ System Architecture Blueprint & SRE Governance
- **Enterprise Design Blueprint**: Published [`ARCHITECTURE.md`](../ARCHITECTURE.md) detailing multi-agent pipeline topology, FastMCP bridges, DevContainer lifecycle hooks, and SSRF security perimeters.
- **Open-Source Governance & CI/CD**: Added standard MIT [`LICENSE`](../LICENSE), enterprise [`SECURITY.md`](../SECURITY.md), SRE [`CONTRIBUTING.md`](../CONTRIBUTING.md), and GitHub Actions CI/CD workflows (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).

---

## 🚀 Highlights of v0.1.7


### 🐍 Native DevContainer Lifecycle Engine
- **`devops devcontainer run-lifecycle`**: Implemented type-safe, cross-platform Python lifecycle hooks (`--post-create`, `--post-start`, `--all`) replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Complete Environment Bootstrap**: Automated persistent shell history (`~/.bash_history`), completion aliases, SSH key permission hardening (`chmod 0600`), Git SSH commit signing setup, and MCP configuration synchronization.

### 🧠 Enhanced AI Reasoning Scratchpad Buffer
- **`ScratchpadBuffer` Reasoning Context**: Preserves intermediate chain-of-thought, persona analysis notes, and verification hypotheses across multi-agent review stages.
- **Context Degradation Prevention**: Maintains high review fidelity across large multi-file diffs and multi-turn pipeline handovers.

### ⚡ Prompt Token & Latency Optimization
- **Compact Serialization**: Enforced compact JSON serialization (`separators=(",", ":")`) across prompt templates and schemas.
- **Context Streamlining**: Reduced token overhead and improved LLM inference responsiveness for local Ollama nodes and remote API providers.

### 🛡️ Exception Resilience & Storage Standardization
- **Worker Error Recovery**: Robust error handling in parallel review worker pipelines, preventing crashes on isolated file parsing anomalies.
- **Top-Level Storage Persistence**: Standardized all analysis and review metadata persistence under `.data/` at the repository root.

---

## 🚀 Highlights of v0.1.6

### 🛡️ Static SecOps & K8s Security Integrations
- **Aqua Trivy Scanning (`devops scan [repo|image|iac]`)**: Comprehensive vulnerability and secret scanning with automated finding injection into `devsecops` persona reviews.
- **Red Hat Kube-linter (`devops k8s lint`)**: Static analysis of Kubernetes manifests and Helm charts against production security best practices.
- **Derailed Popeye (`devops k8s audit`)**: Live Minikube and Kubernetes cluster health sanitizer checking resource limits, pods, and misconfigurations.
- **Fairwinds Pluto (`devops k8s check-deprecated`)**: Deprecated and removed Kubernetes API version detector.

---

## 🚀 Highlights of v0.1.5

### ☸️ Minikube Infrastructure & Target Service Auto-Configuration
- **`devops k8s configure-urls`**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `argocd.url`, `grafana.url`, and `prometheus.url` in `config.yaml`.
- **Automated `deploy-stack` Integration**: `devops k8s deploy-stack` automatically triggers service URL detection upon completing Helm release deployments.

### ⚡ FastMCP Server Tool Alignment
- **Verified 18 FastMCP Tools**: Fixed CLI subcommand mappings in `src/devops_cli/mcp.py` for `repos_status`, `argo_list`, `argo_status`, `docker_stats`, and `workspace_list`.

### 🛡️ 7-Gate CI Quality Gate
- **Expanded Quality Gate**: Added `devops ci coverage` (`pytest-cov`) and `devops ci security` (`bandit`), expanding the automated CI check to 7 sequential gates (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`, `trivy`, `kube-linter`, `popeye`, `pluto`
