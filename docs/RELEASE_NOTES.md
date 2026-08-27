# Release Notes — devops-cli v0.2.5

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, vector embedding benchmarks, TLS certificate automation, OpenTelemetry observability, and multi-persona AI code reviews.

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
