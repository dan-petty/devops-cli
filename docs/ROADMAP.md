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

---

## Release Milestones (Chronological Order)

### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime, Packaging & Workstation Core**: Python 3.14+ runtime with `uv` virtual environment management, cross-platform DevContainer Python lifecycle hooks (`devops devcontainer run-lifecycle`), OS Keyring zero-plaintext secret storage, SIEM audit logging (`AuditLogger`), and automated GHCR DevContainer container publishing.
- [x] **Multi-Persona Code Review Engine**: Domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`), diff pagination, line-level GitHub PR inline comments, human invalidation feedback dataset exporter (`devops ai review export-feedback`), structured scratchpad reasoning buffer (`ScratchpadBuffer`), and XML prompt boundary isolation.
- [x] **Static SecOps & Kubernetes Auditing**: Static security scanner integrations (Aqua Trivy vulnerability & IaC scans, Red Hat Kube-linter manifest audits, Derailed Popeye cluster health sanitizer, Fairwinds Pluto API deprecations, and Kubernetes RBAC policy scanner).
- [x] **Local Kubernetes & Minikube Infrastructure**: Multi-cluster Kubeconfig context switching, automated Minikube NodePort endpoint discovery (`devops k8s configure-urls`), and multi-stack lifecycle (`infra`, `llm`, `all`).
- [x] **OpenTofu Multi-Cloud Infrastructure as Code**: Full IaC command suite (`devops tf`) with production OpenTofu modules for AWS (EKS), Azure (AKS), and GCP (GKE), and FastMCP IaC tools (`tf_plan`, `tf_apply`, `tf_output`).
- [x] **Automated Quality Gates & Dynamic Documentation**: 7-gate CI quality suite (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`), dynamic Click/Typer docs introspection engine (`CLI_REFERENCE.md`, `ENV_VARS.md`, `MCP_TOOLS.md`), and automated release management suite (`devops release`).

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

### Real-Time Agent Streaming & Diagram Generation (v0.2.4 - Completed)
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

### Enterprise Stability, Performance & Quality Hardening (v0.2.5 - Completed)
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

### Live State Watchers, Complexity Analysis & SBOM Generation (v0.2.6 - Completed)
- [x] **Static Code Complexity & Cyclomatic Depth Linter (`devops scan complexity`)**: Automated AST scanner calculating McCabe cyclomatic complexity and strict nesting depth to prevent code maintainability degradation.
- [x] **Syft & Grype Automated SBOM & Vulnerability Scanning (`syft`, `grype`)**: Automated Software Bill of Materials (SBOM) generation (`devops scan sbom`) in CycloneDX/SPDX formats and container runtime vulnerability auditing with configurable severity gates (`--fail-on high|critical`).
- [x] **Git-Diff Aware Test Selector (`devops test run --diff`)**: Targeted test selection discovering and running only test files impacted by active unstaged or branch-level git diffs, reducing inner-loop test cycle latency.
- [x] **Continuous Live Resource & State Watchers (`--watch` / `-w`)**: Real-time terminal auto-refresh and live event streaming across `devops k8s pods --watch`, `devops argo cd apps list --watch`, `devops docker stats --watch`, and `devops release status --watch` utilizing `rich.live.Live` with configurable refresh intervals (`--interval`).
- [x] **Adaptive Multi-Axis LLM & Freshness Router (`devops_cli.ai.router`)**: Dynamic task routing along Complexity (`LOW`, `MEDIUM`, `HIGH`, `FRONTIER`), Freshness (`STATIC_CONTEXT`, `LIVE_MCP_LOOKUP`, `EXTERNAL_WEB_SEARCH`), and Data Sensitivity (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL_AIRGAP`) axes, delivering up to 92% cost savings over uniform frontier calls while preventing proprietary code egress.
- [x] **In-Memory Embedding LRU Cache & Chunk Dedup (`devops_cli.ai.rag.embeddings`)**: In-memory SHA-256 keyed embedding cache eliminating redundant vector generation calls for identical code chunks across files and commits.
- [x] **DevContainer Path Modernization & Lifecycle Hook Migration**: Dynamic interpreter detection, system binary preservation, and native Python lifecycle hooks (`devops devcontainer run-lifecycle`) replacing fragile shell scripts.

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

### Universal Stage Pipelines, HTTP/2 Broker & K8s Chaos Runner (v0.2.9 - Completed)
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

### PydanticAI Native Framework & Hallucination Scrutiny Pipeline (v0.2.10 - Completed)
- [x] **PydanticAI Native Framework Subsystems**: Comprehensive adoption of native `pydantic_ai` modules (`toolsets`, `tools`, `template`, `settings`, `run`, `retries`, `result`, `profiles`, `providers`, `output`, `models.ollama`, `mcp`, `function_signature`, `format_prompt`, `exceptions`, `durable_exec`, `direct`, `concurrency`, `capabilities`, `common_tools`).
- [x] **Python 3.14 PEP 758 Bracketless Exception Compliance**: Elimination of legacy instructions demanding parenthesized tuples; standardizing modern `except Exc1, Exc2:` syntax recognition across review personas and verification gates.
- [x] **Common AI Hallucination Catalog & Autonomous Management (`devops_cli.ai.review.common_hallucinations`)**:
  - Centralized registry of recurring AI hallucinations (`CommonHallucinationEntry`), similarity matching (`find_similar_hallucinations`), and autonomous learning from invalidated findings (`auto_record_invalidated_finding`).
  - Native tracking of high-frequency false positives: PEP 758 bracketless exceptions, masked secret placeholders (`<masked-*>`), test fixtures, `httpx2` reputation, and documentation anti-pattern citations.
- [x] **Multi-Layer Verification Scrutiny for Common Hallucinations**:
  - Category-aligned similarity guards preventing syntax rules from over-matching security defects (path traversal, SSRF, injection).
  - Stop-words filtering in `_FORBIDDEN_COMMON_WORDS` to prevent generic words from contaminating signature keywords.
  - Ground-truth verification (`verify_ground_truth_hallucination`) before invalidating findings.
  - Persona and verification prompt tuning (`devsecops`, `architect`, `verify_finding_system.md`).
- [x] **Dedicated Agent Operational Task Tracking Tier (`docs/agent/`)**:
  - Canonical task status tracking under `docs/agent/task.md` with explicit lifecycle guidelines (`docs/agent/README.md`).

### Workstation Infrastructure, FastMCP 72 Tools & Quality Architecture (v0.2.11 - Completed)
- [x] **Workstation Infrastructure Valkey Migration**: Replaced Redis components with Valkey 8.0-alpine under BSD-3-Clause across ArgoCD and LLM cluster stacks.
- [x] **Codebase Stylistic Drift Remediation & Invariants**: Enforced strict nesting depth $\le 5$ (< 6 indentations), cyclomatic complexity $\le 10$, standardized domain exception taxonomy (`DevOpsCLIError`), and automated CI architectural invariant gates (`tests/test_architectural_invariants.py`).
- [x] **FastMCP Server Tool Parity Expansion (72 Tools)**: Expanded registered FastMCP tools from 53 to 72 tools covering security scans (Trivy, Gitleaks, Semgrep, Checkov, AIBOM, SBOM), Kubernetes operations (chaos, audit, lint, validate, diff), HashiCorp Vault (set, sync), benchmarking, and Git/PR governance.
- [x] **FastMCP Prompt Templates & Dynamic System Resources**: Implemented 4 prompt templates (`code_review_prompt`, `security_audit_prompt`, `k8s_diagnostics_prompt`, `architecture_analysis_prompt`) and 6 dynamic system resources (`resource://workspace/status`, `resource://config/active`, `resource://telemetry/status`, `resource://release/status`, `resource://vault/status`, `resource://mcp/tools`).
- [x] **FastMCP JSON Schema Exporter (`devops mcp export-schemas`)**: Built introspection CLI command exporting JSON tool schemas and markdown instructions, synchronizing with Antigravity IDE lazy tool loader.
- [x] **Enterprise SDLC Governance & Community Health**: Authored `docs/SDLC.md`, standardized `.github/pull_request_template.md`, issue forms, `CODEOWNERS`, `dependabot.yml`, `SECURITY.md`, and `CONTRIBUTING.md`.
- [x] **Review Findings Remediation & Invariant Hardening**: Remediated path traversal in repo listing and ArgoCD manifests, Vault percent-encoded traversal, tool argument validation, and AWS EKS public endpoint exposure.
- [x] **AI Review Report Executive Summary Statement**: Synthesized high-level overview statements, key good patterns, and dynamically categorized defect anti-patterns directly under report titles in markdown artifacts and console output.
- [x] **Autonomous Review Feedback & Self-Improvement Loop Hardening**: Grounded missing-symbol and masked-placeholder hallucination detection with AST export verification, word boundary lookaheads, and prompt guardrails.
- [x] **Submodule Boilerplate Consolidation & Usability Architecture (Phase 42)**:
  - **Declarative Dry-Run Execution (`@dry_run_command`)**: Implemented `@dry_run_command` in `devops_cli.dry_run.decorator` eliminating repetitive manual dry-run interception blocks and cyclomatic overhead across 35 command files.
  - **Universal CLI Error Boundary & Decorator (`@cli_command_handler`)**: Unified OpenTelemetry span tracing, command duration/counter metrics, clean error output, and standard `typer.Exit(code=exc.exit_code)` dispatch.
  - **Filesystem Subpath Containment & Traversal Defense (`safe_resolve_subpath`)**: Standardized secure path resolution in `devops_cli.core.paths` guarding against directory traversal, absolute path escapes, and symlink dereference attacks.
  - **Subprocess Execution with Structured JSON Extraction (`run_json_subprocess`)**: Automated JSON deserialization, error formatting, and type-safe domain exception handling in `devops_cli.core.process`, eliminating raw `subprocess.run` calls.
  - **External Binary Pre-flight Verification (`require_binary` / `check_binary`)**: Built dependency verification utilities in `devops_cli.core.binaries` raising strongly typed `DependencyError` with actionable installation hints.
  - **Universal Secret Masking & Credential Sanitizer (`devops_cli.security.sanitizer`)**: Centralized secret redaction (`mask_secrets`, `mask_dict_secrets`, `mask_uri_credentials`), eliminating 80 lines of duplicate pattern arrays.
  - **Markdown Codeblock JSON Deserializer (`extract_json_block`)**: Centralized markdown JSON parsing in `devops_cli.core.serialization` with `json_repair` fallback.
- [x] **Declarative Security Framework Foundation & AST Cache Tier (Phase 43)**:
  - **Declarative Security Scanner Framework (`BaseSecurityScanner`)**: Universal abstract base class in `devops_cli.security.base` standardizing scanner lifecycle, binary pre-flight checks, timeout execution, JSON extraction, and normalized `Finding` creation.
  - **Centralized Scanner Registry (`ScannerRegistry`)**: Dynamic scanner registry in `devops_cli.security.registry` providing introspection, capability filtering, and batch dispatch.
  - **In-Memory High-Performance AST Cache Tier (`ASTCache`)**: Thread-safe in-memory cache in `devops_cli.ai.ast_cache` keyed by `(filepath, st_mtime)` eliminating redundant AST parsing during multi-persona reviews.
  - **Declarative Rich Table Builder (`render_table`)**: Declarative table rendering helper in `devops_cli.output.table_builder` unifying table layouts, empty states, and JSON/YAML serialization.
- [x] **GitHub Management & Quality Automation (Phase 44)**:
  - **Declarative GitHub Taxonomy (`.github/labels.yml`)**: Standardized 29 labels across `type/*`, `scope/*`, `priority/*`, `status/*`, and `review/*`.
  - **GitHub Projects v2 Life Cycle Template (`.github/project-template.json`)**: Configured 4 standardized views (*Sprint Kanban*, *Roadmap Timeline*, *Triage & Quality Table*, *Value vs Effort Priority Matrix*).
  - **Native GitHub CLI Command Group (`devops gh`)**: Added `devops gh labels list|sync|audit`, `devops gh milestones list|sync|status`, `devops gh project status|sync|template`, and `devops gh views list|spec`.
  - **FastMCP GitHub Tools**: Added 6 FastMCP tools (`gh_label_list`, `gh_label_sync`, `gh_milestone_list`, `gh_milestone_sync`, `gh_project_status`, `gh_view_spec`).
  - **Task Manual 13**: Authored `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`.
- [x] **Documentation & AI Instruction Token Optimization (Phase 45)**:
  - **Root Agent Instructions Optimization (`AGENTS.md`)**: Reduced file size by 36% (10.5 KB saved) to eliminate assistant context truncation while preserving all architectural invariants and security mandates.
  - **Review Prompt Stack Deduplication (`src/devops_cli/ai/tasks/`)**: Deduplicated overlapping instructions across `review.md`, `guardrails_isolation.md`, and `verify_finding_system.md` saving 34% prompt tokens per segment.
  - **Dedicated Agent Data Isolation**: Cleanly separated workspace data root (`./.data`) from isolated agent task artifacts (`<data_dir>/agent`, e.g. `./.data/agent`).
- [x] **Principal DevSecOps Architectural Review & Threat Evaluation (Phase 47.1)**:
  - Comprehensive architectural review by Principal DevSecOps Engineer evaluating supply chain, process execution, container sandboxing, network perimeter/SSRF, secret management, Kubernetes posture, and AI/LLM safety.
  - Authored full evaluation report detailing 1 Critical, 4 High, and 4 Medium/Low findings with verified exploit scenarios and remediation specifications.
- [ ] **DevSecOps Architectural Hardening & Zero-Trust Defense-in-Depth (Phase 47.2)**:
  - **OpenAIProvider Authentication Header Injection**: Inject `Authorization: Bearer <token>` in `OpenAIProvider.generate()` leveraging `settings.ai.openai_api_key` or OS Keyring, eliminating 401 Unauthorized failures on authenticated OpenAI-compatible endpoints.
  - **Fail-Closed SSRF DNS Resolution Guard**: Harden `_enforce_non_private_ssrf` in `devops_cli.core.validation` to fail closed when `allow_private=False` upon DNS timeouts, `socket.gaierror`, or `OSError`, mitigating DNS rebinding and delayed resolution bypasses.
  - **Universal Secret Sanitizer Pattern Expansion**: Expand `_SECRET_PATTERNS` in `devops_cli.security.sanitizer` with Vault tokens (`hvs.*`, `s.*`), GitLab PATs (`glpat-*`), Slack/Discord webhooks, and HuggingFace API keys (`hf_*`).
  - **Docker Workload Sandbox Security Hardening**: Harden `WorkloadSandboxRunner` in `devops_cli.docker.sandbox` by enforcing `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `pids_limit=256`, default read-only volume mounting, and blocking sensitive host paths (`~/.ssh`, `~/.aws`, `~/.kube`, `.git`).
  - **Context-Aware Review Pre-Filter & Test Noise Reduction**: Scope Gitleaks scanner pre-filter to ignore test mock fixtures (`tests/test_*.py`) and documentation examples in compliance with `AGENTS.md` guidelines.

### Valkey Workstation Management & High-Performance Distributed Caching (v0.2.12 - Completed)
- [x] **Valkey Workstation CLI Subsystem (`devops valkey`)**: Dedicated command group providing `ping`, `info`, `stats`, `keys [pattern]`, `get <key>`, `set <key> <val> [--ttl <sec>]`, `flush [--all]`, `cli`, and snapshot `backup`/`restore` managing local and remote Valkey instances via lightweight RESP3 socket communication without C dependencies.
- [x] **Valkey High-Performance AI & Embedding Cache (`ai.cache.backend=valkey`)**: Distributed SHA-256 keyed embedding and review finding cache tier (`sha256(chunk + model + dim)`) slashing duplicate LLM inference by up to 85% across concurrent CLI runs, file watchers, and CI workers with configurable TTL and LRU memory management.
- [x] **Distributed LLM Token Bucket & Concurrency Rate Limiter**: Valkey-backed atomic sliding-window rate limiter powered by Lua scripts (`valkey_token_bucket.lua`) enforcing Requests-Per-Minute (RPM) and Tokens-Per-Minute (TPM) caps to eliminate local Ollama GPU VRAM thrashing and cloud API 429 throttling.
- [x] **FastMCP Valkey Toolset & Live System Resource**: 6 FastMCP tools (`valkey_ping`, `valkey_info`, `valkey_get`, `valkey_set`, `valkey_keys`, `valkey_flush`) and dynamic system resource `resource://valkey/status` reporting real-time memory usage, connected clients, and cache hit ratios.
- [x] **Ephemeral Testcontainers Valkey Testing Harness**: Rootless container fixture (`testcontainers-python` running `valkey/valkey:8.0-alpine`) for offline unit and integration test suites without requiring live Minikube cluster dependencies.
- [x] **Valkey IT Domain Knowledge Base Manual (`it_domains/tools/valkey.md`)**: Comprehensive technical guide covering Valkey 8.0 architecture, RESP3 wire protocol, memory optimization, eviction policies, and cluster topologies.
- [x] **Automated PR DevContainer Pruning & Package Lifecycle (Phase 47.4)**: Author automated GHCR cleanup workflow (`cleanup-devcontainer.yml`) pruning PR-specific devcontainer tags upon PR closure.
- [x] **Infrastructure Perimeter, Supply Chain & Workstation Zero-Trust (Phase 48)**:
  - [x] **Kubernetes Pod Security Admission (PSA) Enforcement**: Apply PSA enforcement and audit labels across all namespaces in `k8s/namespaces.yaml` and `k8s/llm/namespace.yaml`.
  - [x] **Cluster Default-Deny NetworkPolicies**: Author granular `NetworkPolicy` manifests for `k8s/monitoring/` and `k8s/argocd/` with explicit DNS and inter-service egress rules.
  - [x] **Subprocess Environment Isolation & Credential Boundary**: Restrict default environment inheritance in `run_subprocess` (`src/devops_cli/core/process.py`) to prevent ambient token leakage to untrusted child binaries.
  - [x] **Immutable GitHub Actions Commit SHA Pinning**: Pin all actions across `.github/workflows/ci.yml`, `codeql.yml`, and `release.yml` to immutable 40-character commit SHAs with inline version comments.
  - [x] **Qdrant Vector Database API Key Secret Protection**: Add optional API key authentication support and ClusterIP default configuration for production deployments in `k8s/llm/values-qdrant.yaml`.

### Advanced Agentic Harness, Sub-Agent Local Offloading & Terminal UX (v0.2.13 - Completed)
- [x] **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)**: Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive exploration and symbol searching to local open models (Granite, Qwen2.5-Coder) under a "Big decides, small types, big checks" synthesis protocol, achieving 85%+ token savings.
- [x] **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen responsive terminal dashboard powered by `Textual` providing real-time tabs for live Kubernetes pods, Minikube services, Docker container metrics, OpenTelemetry span waterfalls, active AI review findings, and Valkey cache metrics with keyboard navigation (`1-5`, `q`, `r`, `?`).
- [x] **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**: "Chaos Monkey for Models" validation framework deliberately degrading frontier connections, injecting latency, and enforcing local open model fallbacks to verify that automation tools pass CI quality gates without human coaching.
- [x] **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**: Centralized emergency control to cleanly suspend active agent loops, schedulers, and background cron jobs during upstream provider outages, with zero-state-loss failover to local endpoints.
- [x] **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**: Automated evaluation suite benchmarking candidate models against human-in-the-loop validated feedback datasets (`.data/feedback_dataset.jsonl`), calculating precision, recall, and hallucination scores.
- [x] **Parallel Async Multi-File Review Worker Pool & Streaming Diff Parser**: Concurrent async file review execution utilizing Python 3.14 `asyncio.TaskGroup` bounded by semaphores and token budgets, combined with streaming generator-based unified diff chunking reducing peak memory by 60% and cutting review runtimes by up to 70%.
- [x] **Logfire Structured AI Observability Bridge (`logfire`)**: Native Pydantic Logfire integration binding with OpenTelemetry distributed spans and Rich terminal formatters for live agent reasoning inspection, token throughput counters, and trace waterfalls.

### Multilingual Code Intelligence & Library Ingestion Engine (v0.2.14 - Current Release / Active Development)
- [x] **Dynamic Package Introspection & Type Stub Parser (`devops ai ingest library`)**: Automated AST and type stub (`.pyi`) extractor indexing installed library classes, method signatures, parameter types, defaults, and docstrings into structured Pydantic v2 contracts (`.data/libraries/<pkg>-contract.json`). (PR #82)
- [x] **Multi-Source Documentation & Standards Ingester (`devops ai ingest docs`)**: SSRF-guarded crawler ingesting local and remote documentation sets (Sphinx, MkDocs, DevDocs, PEPs, CIS benchmarks) into clean, chunked markdown reference collections with breadcrumb metadata. (PR #82)
- [x] **Dedicated Library Vector Tier (`devops_libraries`) & Valkey Symbol Store**: Segregated Qdrant collection and Valkey L1 cache tier (`symbol:<qualname>`) providing sub-millisecond API signature lookups and hybrid dense-sparse search. (PR #83)
- [x] **GitHub Pages, Issues, Projects & Views Integration with FastMCP**: Complete management subsystem: `devops gh pages [status|builds|build|verify]`, `devops gh issues [list|create|triage|status]`, `devops gh project [list|audit]`, and `devops gh views audit`; 10 new FastMCP tools and 4 dynamic system resources (`resource://gh/*`). (PR #83)
- [x] **Import-Driven AST Prompt Grounding & Contract Invalidation (P0 - Critical, Issue #78)**:
  - *Context & Rationale*: Eliminates AI third-party API hallucinations by extracting imported symbols from review diffs via AST, fetching verified signatures from `devops_libraries` / Valkey, and injecting concrete contracts into review prompts.
  - *CLI & Architecture*: Integrated into `Stage1PreAnalysis` and `Stage3PersonaReview` with `--ground-contracts` flag; falls back gracefully to offline JSON contracts.
  - *Acceptance Criteria*: Measured reduction of third-party API hallucination rate to <1% across benchmark datasets; AST symbol extraction overhead <10ms per file.
- [x] **FastMCP Library Intelligence Tools & Dynamic System Resources (P0 - Critical, Issue #80)**:
  - *Context & Rationale*: Exposes library intelligence directly to IDE-hosted AI coding assistants through native FastMCP tools and dynamic resources.
  - *Tools & Resources*: FastMCP tools `ai_ingest_library(package)`, `ai_query_library(query, package, exact)`, `ai_inspect_symbol(symbol, package)`; dynamic system resource `resource://libraries/indexed` reporting indexed libraries, symbol counts, and vector point health.
  - *Acceptance Criteria*: 100% typed parameters, comprehensive docstrings, auto-exported schemas via `devops mcp export-schemas`, and contract test verification in `tests/test_fastmcp_contracts.py`.
- [x] **Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (P1 - High, Issue #74)**:
  - *Context & Rationale*: Extends code intelligence beyond Python to polyglot ecosystems (TypeScript, Go, Rust, Java, HCL). Tree-sitter provides incremental concrete syntax trees with concrete token spans, resilient error recovery, and lightning-fast queries via S-expressions.
  - *CLI & Architecture*: `devops ai ast parse <file> [--query <s-expr>]` and `devops ai repomap --multilingual`; language grammars packaged without requiring host C compiler toolchains.
  - *Acceptance Criteria*: Sub-5ms query resolution per file; automated fallback to Python standard `ast` when tree-sitter grammars are uninstalled.
- [x] **Library API Drift & Deprecation Usage Auditor (`devops ai audit-library-usage`) (P1 - High, Issue #79)**:
  - *Context & Rationale*: Proactively flags breaking changes prior to dependency upgrades by comparing workspace AST call sites against indexed library contracts.
  - *CLI & Output*: `devops ai audit-library-usage [--package <pkg>] [--fail-on-breaking]` emitting Rich tables and `.data/analysis/api_drift_report.json`.
  - *Acceptance Criteria*: 100% recall of deprecated parameter names and removed methods in test fixtures; cyclomatic complexity $\le 10$.
- [ ] **AI Context Packing & Symbol-Pruned Prompt Synthesizer (P2 - Medium, Issue #81)**:
  - *Context & Rationale*: Maximizes prompt token efficiency by ranking imported symbols by usage density, stripping unreferenced private methods/docstrings, and compressing type annotations.
  - *Architecture*: Integrated into `devops_cli.ai.context_packer`; cuts context token overhead by 40-60% while preserving strict type fidelity.
- [ ] **Autonomous RAG Index Drift Detection & Auto-Reindexing (P2 - Medium)**:
  - *Context & Rationale*: Maintains vector index freshness across git branch transitions. A lightweight watcher compares vector commit metadata against `HEAD` and automatically re-indexes modified files.
  - *CLI*: `devops ai index status` and `devops ai index reindex [--changed-only]`.

### GitOps Fleet, FinOps, Centralized Logging & Production Security Mesh (v0.2.15 - Scheduled)
- [ ] **Complete Security Scanner Migration to `BaseSecurityScanner` & `ScannerRegistry` (P0 - Critical)**:
  - *Context & Rationale*: Standardizes all 11 scanner modules (`bandit`, `checkov`, `dive`, `gitleaks`, `kubeconform`, `kubelinter`, `pluto`, `popeye`, `semgrep`, `tflint`, `trivy`) to inherit from `BaseSecurityScanner`. Eliminates duplicate subprocess boilerplate, enforces pre-flight binary verification (`require_binary`), guarantees bounded timeouts, and produces normalized `Finding` objects.
  - *Acceptance Criteria*: 100% scanner registration in `ScannerRegistry`; zero ad-hoc subprocess calls; cyclomatic complexity $\le 10$ and nesting depth $\le 5$ across all scanner adapters.
- [ ] **Centralized Kubernetes Logging Stack & LogQL Integration (`devops k8s logs` / `devops logs`) (P0 - Critical)**:
  - *Context & Rationale*: Establishes enterprise log aggregation in Minikube/Kubernetes, providing the logging backbone for both incident triage and future sandboxed application observability (v0.2.16).
  - *Architecture & Components*:
    - **Declarative Loki & Fluent Bit Stack (`k8s/logging/`, `devops k8s deploy-stack --stack logging`)**: Multi-tenant, lightweight log aggregation running in dedicated namespace `logging` with PSA enforcement and restrictive NetworkPolicy.
    - **Trace-to-Log Correlation**: Automatic correlation linking OpenTelemetry `trace_id` from Jaeger distributed traces with Loki log streams in Grafana.
    - **Native LogQL Query & Stream Engine (`devops k8s logs query|tail|stream`)**: Rich terminal log inspection powered by LogQL parser pipelines (`| json`, `| logfmt`), regex filters (`|=`, `!~`), label selectors, and WebSocket follow mode (`-f`).
    - **FastMCP Log Tools & System Resource**: Exposing `k8s_logs_query`, `k8s_logs_tail`, and dynamic resource `resource://k8s/logs/recent` for autonomous AI incident diagnosis.
    - **Interactive TUI Logs Tab (`devops dashboard`)**: Real-time log streaming tab in the Textual TUI with syntax-highlighted search and pause/resume controls.
- [ ] **Infracost FinOps Cloud Cost Engine (`devops tf cost`) (P1 - High)**:
  - *Context & Rationale*: Evaluates financial impacts of OpenTofu/Terraform diffs, calculating monthly cloud spend deltas and enriching `pm` and `architect` reviewer personas with FinOps guardrails.
  - *CLI & Integration*: `devops tf cost [--diff] [--currency USD] [--format table|json]`; automatically embeds cost summaries into `devops tf notify-plan` PR comments.
- [ ] **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`) (P1 - High)**:
  - *Context & Rationale*: Multi-cluster GitOps orchestration coordinating synchronized deployments across development, staging, and production clusters with Argo Rollouts (canary/blue-green) and automated metric-driven rollback gates.
- [ ] **Automated GitOps Drift Detection & Webhook Synchronization (`devops argo gitops watch`) (P1 - High)**:
  - *Context & Rationale*: Eliminates polling delays by triggering instant ArgoCD app reconciliations upon local git commits or inotify filesystem changes.
- [ ] **Local GitOps Project Orchestration Pipeline (`devops argo cd apps bootstrap-gitops`) (P1 - High)**:
  - *Context & Rationale*: One-click bootstrap configuring the local background Git daemon (`git://host.minikube.internal:9418/k8s`), ArgoCD Root Application ("App of Apps"), and multi-stack lifecycle (`infra`, `llm`, `logging`).
- [ ] **Sigstore Cosign Container Provenance & Image Signing (`devops docker sign|verify`) (P1 - High)**:
  - *Context & Rationale*: Keyless cryptographic container image and manifest signing integrating with OS Keyring and OIDC tokens for verifiable supply-chain provenance.
- [ ] **Falco eBPF Runtime Security & Anomaly Streamer (`devops k8s security-stream`) (P2 - Medium)**:
  - *Context & Rationale*: Real-time kernel-level syscall anomaly streaming via eBPF probes, detecting unauthorized container privilege escalation, sensitive file reads, and unexpected network egress.
- [ ] **GitHub Enterprise Automation Phase 2 (`devops gh branch-protection`, `secrets`) (P2 - Medium)**:
  - *Context & Rationale*: Declarative branch protection policy enforcement and libsodium-encrypted secret synchronization from OS Keyring/Vault to GitHub repository secrets.
- [ ] **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`) (P2 - Medium)**:
  - *Context & Rationale*: Diagnostic tool leveraging Python `tracemalloc` to validate socket lifecycles and catch memory leaks across background daemons and FastMCP workers.
- [ ] **Core Dependency Ecosystem Alignment (`pyproject.toml`) (P2 - Medium)**:
  - *Context & Rationale*: Scheduled compatibility validation and lockfile updates across `typer`, `pydantic-ai`, `httpx2`, `ruff`, and `anthropic`.

### Ephemeral Workload Sandboxing, Dynamic Probing & Runtime Observability (v0.2.16 - Scheduled)
- [ ] **Long-Running Workload Sandbox Lifecycle Engine (`devops sandbox deploy|status|stop|exec`) (P0 - Critical)**:
  - *Context & Rationale*: Foundational execution tier orchestrating rootless Docker containers or ephemeral Kubernetes namespaces (`sandbox-<app>-<timestamp>`) for testing active builds in total isolation.
  - *Security & Resource Isolation*: Dynamic host port allocation (`10000-60000`), cgroup v2 resource limits (`pids_limit=256`, `cpu_limit`, `memory_limit`), read-only root filesystems, `/tmp` tmpfs, and `cap_drop=["ALL"]`.
  - *State Management*: Managed daemon tracking in `.data/sandbox/instances.json` recording instance ID, container ID, assigned ports, and uptime.
  - *Acceptance Criteria*: 100% clean process teardown on stop or SIGINT; zero host port conflicts; strict containment preventing host root or `.git` escapes.
- [ ] **Comprehensive Endpoint, Readiness & Health Probing Subsystem (`devops sandbox probe`) (P0 - Critical)**:
  - *Context & Rationale*: Protocol-agnostic probing engine evaluating application health before initiating integration workflows or fuzz testing.
  - *Probe Modules*:
    - **Socket Reachability**: Non-blocking TCP connection verification asserting port listener readiness.
    - **HTTP/REST Probing**: Structured requests to `/healthz`, `/health`, `/ready`, `/live` asserting HTTP status codes, latency SLAs, and regex response matching.
    - **OpenAPI Schema Crawler**: Automatic discovery and parsing of `/openapi.json` executing safe schema-validated GET probes.
    - **gRPC Probing**: Health check execution via standard `grpc.health.v1.Health/Check` and reflection exploration without requiring pre-compiled `.proto` stubs.
  - *Pydantic Models*: Typed `SandboxProbeReport` and `EndpointProbeResult` with Rich terminal formatting and JSON export.
- [ ] **Cgroup Metrics, Prometheus Scraping & Real-Time Telemetry (`devops sandbox metrics`) (P1 - High)**:
  - *Context & Rationale*: Real-time container telemetry capturing cgroup v2 metrics (CPU utilization %, memory RSS, page faults, open file descriptors, network RX/TX bytes) and scraping application `/metrics` endpoints for error rates and latency histograms. Emits automated threshold warnings for memory leak trajectories.
- [ ] **Traceparent Propagation & Distributed Trace Correlation (`devops sandbox traces`) (P1 - High)**:
  - *Context & Rationale*: Automatic W3C Trace Context (`traceparent`, `tracestate`) header injection into synthetic probes, linking test executions directly with internal application spans received by local OpenTelemetry Collector, Jaeger, and Logfire. Provides terminal waterfall visualization of cross-service latencies.
- [ ] **Streaming Diagnostic Log Aggregator & Panic Detector (`devops sandbox logs`) (P1 - High)**:
  - *Context & Rationale*: Multiplexed stdout/stderr log streaming with follow mode (`-f`), buffer management, and automated regex panic detection (Python tracebacks, Go panics, Java stacktraces, Rust panics, segfaults), archiving structured incident records in `.data/sandbox/incidents/<id>.json`.

### Dynamic API Fuzzing, Runtime Security DAST & Autonomous Remediation Iteration (v0.2.17 - Scheduled)
- [ ] **OpenAPI & Schema-Driven Dynamic API Fuzzing Engine (`devops sandbox fuzz`) (P0 - Critical)**:
  - *Context & Rationale*: Systematic security and robustness fuzzer generating mutational, boundary, and injection payloads derived directly from OpenAPI schemas.
  - *Payload Generators*: Boundary values (null bytes, extreme string lengths 10KB-10MB, integer overflows, format strings), security injections (SQLi, command injection, path traversal, XXE, SSRF), and stateful CRUD sequence chaos.
  - *Minimal Repro Generator*: Isolates failing payloads into standalone `curl` scripts and machine-readable reproduction files (`.data/sandbox/repros/<fuzz_id>.json`).
- [ ] **Autonomous Closed-Loop Debugging & Iterative Code Patch Engine (`devops sandbox iterate`) (P0 - Critical)**:
  - *Context & Rationale*: Unified closed-loop workflow: `deploy` $\to$ `probe` $\to$ `fuzz` $\to$ `diagnose` $\to$ `synthesize patch` $\to$ `re-deploy` $\to$ `verify green`. Connects fuzzing crashes back to workspace AST locations, invokes `devsecops`/`qa` personas to author drop-in code fixes, and asserts zero regressions.
  - *Watch Mode*: `devops sandbox iterate --watch` continuously validates and patches code as local files are modified.
- [ ] **Dynamic Application Security Testing (DAST) & Egress Scanner (`devops sandbox scan`) (P1 - High)**:
  - *Context & Rationale*: Evaluates runtime perimeter defenses using OWASP ZAP and Nuclei templates against sandbox endpoints; audits container filesystem mutations via `docker diff`; monitors socket egress for unauthorized outbound connections or SSRF attempts; verifies process privilege boundaries.
- [ ] **Chaos Fault & Resource Exhaustion Injection (`devops sandbox chaos`) (P1 - High)**:
  - *Context & Rationale*: Stress-tests application resilience under hostile conditions: memory ballooning to verify OOM behavior, CPU throttling, network latency/packet drop injection via `tc`, and graceful signal handling (`SIGTERM`, `SIGHUP`).
- [ ] **FastMCP Sandbox Tools & Dynamic System Resources (P1 - High)**:
  - *Context & Rationale*: Exposes 6 FastMCP tools (`sandbox_deploy`, `sandbox_probe`, `sandbox_metrics`, `sandbox_fuzz`, `sandbox_scan`, `sandbox_iterate`) and 3 dynamic system resources (`resource://sandbox/status`, `resource://sandbox/metrics`, `resource://sandbox/incidents`) enabling AI assistants to operate and heal sandbox workloads autonomously.

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
| **Quick Wins** | Foundation, Finding Verification, Prompt Guards & SecOps Scanners | Standard Library / Trivy / Pluto / GHCR | High | Low | v0.1.x | ✅ Completed |
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
| | Static Code Complexity & Cyclomatic Depth Linter | AST / McCabe | High | Low | v0.2.6 | ✅ Completed |
| | In-Memory Embedding LRU Cache & Chunk Dedup | `functools` / Hash | High | Low | v0.2.6 | ✅ Completed |
| | Adaptive Test Sharding & Fast Path Test Selector | Pytest / Git | High | Low | v0.2.6 | ✅ Completed |
| | Streaming JSON/YAML Serializer for Large Reviews | `orjson` / Pydantic | High | Low | v0.2.7 | ✅ Completed |
| | Zero-Allocation Tokenizer & AST Stream Parser | `tokenize` / Generator | High | Low | v0.2.7 | ✅ Completed |
| | Declarative Dry-Run Execution (`@dry_run_command`) | Python Decorator / Pydantic | High | Low | v0.2.11 | ✅ Completed |
| | Declarative Rich Table Builder (`render_table`) | Rich / Pydantic | High | Low | v0.2.11 | ✅ Completed |
| | High-Performance In-Memory AST Caching Tier (`ASTCache`) | AST / `mtime` Cache | High | Low | v0.2.11 | ✅ Completed |
| | Universal Binary Pre-Flight Verification (`require_binary`) | `core/binaries.py` | High | Low | v0.2.11 | ✅ Completed |
| | Subpath Containment & Traversal Defense (`safe_resolve_subpath`) | `core/paths.py` | High | Low | v0.2.11 | ✅ Completed |
| | Declarative GitHub Label Schema & CLI (`devops gh labels`) | YAML / GitHub REST API | High | Low | v0.2.11 | ✅ Completed |
| | Roadmap Milestone Sync & Metrics (`devops gh milestones`) | Markdown AST / GitHub API | High | Low | v0.2.11 | ✅ Completed |
| | GitHub Projects v2 Task Item Parser (`devops gh project`) | Markdown / Pydantic | High | Low | v0.2.11 | ✅ Completed |
| | Documentation & Prompt Token Optimization | Markdown / System Prompts | High | Low | v0.2.11 | ✅ Completed |
| | Principal DevSecOps Architectural Review | Threat Modeling / Scanners | High | Low | v0.2.11 | ✅ Completed |
| | Fail-Closed SSRF DNS Resolution Guard | `core/validation.py` | High | Low | v0.2.11 | ✅ Completed |
| | Universal Secret Sanitizer Pattern Expansion | `security/sanitizer.py` | High | Low | v0.2.11 | ✅ Completed |
| | OpenAIProvider Bearer Header & Keyring Injection | `ai/providers/openai.py` | High | Low | v0.2.11 | ✅ Completed |
| | Review Gitleaks Test Scoping & Noise Elimination | Gitleaks / Test Scope | Medium | Low | v0.2.11 | ✅ Completed |
| | Kubernetes Pod Security Admission (PSA) Labels | `k8s/namespaces.yaml` | High | Low | v0.2.11 | ✅ Completed |
| | Automated PR DevContainer Pruning Workflow | `.github/workflows/` | High | Low | v0.2.12 | ✅ Completed |
| | Immutable GitHub Actions Commit SHA Pinning | `.github/workflows/` | High | Low | v0.2.12 | ✅ Completed |
| | Valkey Workstation Management CLI (`devops valkey`) | `valkey-py` / Socket | High | Low | v0.2.12 | ✅ Completed |
| | FastMCP Valkey Toolset & Live System Resource | FastMCP / Valkey | High | Low | v0.2.12 | ✅ Completed |
| | Valkey IT Domain Knowledge Base Manual | Markdown / Docs | Medium | Low | v0.2.12 | ✅ Completed |
| | Agent Constellation Quiesce & Failover Controller | Asyncio / State Machine | High | Low | v0.2.13 | ✅ Completed |
| | Deterministic Mock LLM Test Isolation (< 60s CI) | `unittest.mock` / Pytest | High | Low | v0.2.13 | ✅ Completed |
| | Dedicated Library Vector Tier (`devops_libraries`) | Qdrant / Valkey | High | Low | v0.2.14 | ✅ Completed |
| | GitHub Pages Publishing & Deployment Verification CLI (`devops gh pages`) | Python / Jekyll / GitHub REST | High | Low | v0.2.14 | ✅ Completed |
| | FastMCP GitHub Pages, Issues & Views Tools (10 Tools) | FastMCP / Pydantic | High | Low | v0.2.14 | ✅ Completed |
| | FastMCP Library Tools & Indexed Resource | FastMCP / Qdrant | High | Low | v0.2.14 | ✅ Completed |
| | Declarative Branch Protection Auditor (`devops gh branch-protection`) | GitHub REST / Policy | High | Low | v0.2.15 | 📋 Scheduled (P2) |
| | Workstation Secret to GitHub Secret Sync (`devops gh secrets`) | `PyNaCl` / Keyring / Vault | High | Low | v0.2.15 | 📋 Scheduled (P2) |
| | Deterministic Async Memory & Pool Profiler | `asyncio` / `tracemalloc` | Medium | Low | v0.2.15 | 📋 Scheduled (P2) |
| | Endpoint & Readiness Probing Subsystem (`devops sandbox probe`) | Standard Library (`http.client`, `socket`) | High | Low | v0.2.16 | 📋 Scheduled (P0) |
| | Minimal Fuzzing Repro Case Generator (`.data/sandbox/repros/`) | Standard Library (`json`, `pathlib`) | High | Low | v0.2.17 | 📋 Scheduled (P0) |
| | Container Filesystem Mutation Auditor (`docker diff`) | Docker CLI / Subprocess | High | Low | v0.2.17 | 📋 Scheduled (P1) |
| | Zero-Trust Git Commit & Tag Signature Verifier | `git`, GPG, Sigstore | High | Low | v0.3.0 | 💡 Future Vision |
| | JIT Python 3.14 Bytecode Optimization Benchmarking | `pytest-benchmark` / JIT | Medium | Low | v0.3.0 | 💡 Future Vision |
| **Strategic Investments** | OpenTofu Multi-Cloud IaC, Minikube Auto-Config & DevContainer Lifecycle | OpenTofu / Minikube / Python Lifecycle | High | High | v0.1.x | ✅ Completed |
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
| | Continuous Live Resource & State Watchers (`--watch`) | `rich.live.Live` | High | Medium | v0.2.6 | ✅ Completed |
| | Syft & Grype Automated SBOM & Vulnerability Scanning | `syft`, `grype` | High | Medium | v0.2.6 | ✅ Completed |
| | Model Curation Pipeline & AIBOM Generator | Semgrep / AST / CycloneDX | High | Medium | v0.2.7 | ✅ Completed |
| | "Big Decides, Small Types, Big Checks" Synthesis Protocol | Multi-Agent / PydanticAI | High | Medium | v0.2.7 | ✅ Completed |
| | Cross-Encoder Context Re-Ranker & Deep Semantic RAG | Cross-Encoder / Qdrant | High | Medium | v0.2.7 | ✅ Completed |
| | Output Subsystem Modularization & Formatter Engine | Python Subpackage Architecture | High | Medium | v0.2.8 | ✅ Completed |
| | Centralized Language Message Catalog & Badges | `messages.py` / Localization | High | Medium | v0.2.8 | ✅ Completed |
| | Universal Multi-Stage Workflow Orchestration Protocol | Python Generics / Pydantic | High | Medium | v0.2.9 | ✅ Completed |
| | Unified Async HTTP/2 Connection Broker | `httpx2` / SSRF Guard | High | Medium | v0.2.9 | ✅ Completed |
| | Local Kubernetes Chaos & Fault Injection Engine | `chaos-mesh` / `tc` | High | Medium | v0.2.9 | ✅ Completed |
| | Continuous IDE File Watcher & Instant AI Review | `watchdog` / AST | High | Medium | v0.2.9 | ✅ Completed |
| | Automated Vulnerability Remediation PR Engine | AST / Pytest / Git | High | Medium | v0.2.9 | ✅ Completed |
| | Enterprise Vault & KMS Secret Broker | `hvac`, Cloud KMS SDKs | Medium | High | v0.2.9 | ✅ Completed |
| | Isolated Dockerized Workload Sandbox Environment | Docker / Rootless Sandbox | High | Medium | v0.2.9 | ✅ Completed |
| | Native Pydantic AI Framework Subsystems | PydanticAI / FastMCP | High | Medium | v0.2.10 | ✅ Completed |
| | Common AI Hallucination Scrutiny Pipeline | Pydantic / AST / Verification | High | Medium | v0.2.10 | ✅ Completed |
| | Workstation Infrastructure Valkey Migration | Valkey / Helm / ArgoCD | High | Medium | v0.2.11 | ✅ Completed |
| | Codebase Stylistic Drift Remediation & Invariants | AST / McCabe / DevOpsCLIError | High | Medium | v0.2.11 | ✅ Completed |
| | FastMCP Server Tool Parity (72 Tools) | FastMCP / PydanticAI / Toolset | High | Medium | v0.2.11 | ✅ Completed |
| | Declarative CLI Command Dispatch & Universal Error Boundary | Typer / Python Decorators | High | Medium | v0.2.11 | ✅ Completed |
| | Subprocess Execution & JSON Deserializer | Python Subprocess / Pydantic | High | Medium | v0.2.11 | ✅ Completed |
| | Declarative Security Scanner Framework Foundation | Python ABC / Registry | High | Medium | v0.2.11 | ✅ Completed |
| | GitHub Views & Standardized Projects v2 Lifecycle | GitHub API / Views Template | High | Medium | v0.2.11 | ✅ Completed |
| | Docker Workload Sandbox Security Hardening | Docker SDK / Capabilities | High | Medium | v0.2.11 | ✅ Completed |
| | Cluster Default-Deny NetworkPolicies | K8s NetworkPolicy | High | Medium | v0.2.12 | ✅ Completed |
| | Subprocess Environment Isolation & Credential Boundary | `core/process.py` | High | Medium | v0.2.12 | ✅ Completed |
| | Qdrant Vector DB API Key Secret Protection | Helm / Secret Store | High | Medium | v0.2.12 | ✅ Completed |
| | Valkey High-Performance Distributed AI Cache Tier | Valkey / Pydantic | High | Medium | v0.2.12 | ✅ Completed |
| | Ephemeral Testcontainers Valkey Testing Harness | `testcontainers-python` | High | Medium | v0.2.12 | ✅ Completed |
| | Sub-Agent Local Offloading Engine & Harness Slots | PydanticAI / Ollama / vLLM | High | Medium | v0.2.13 | ✅ Completed |
| | Interactive Terminal UI Dashboard (`devops dashboard`) | `textual` TUI | High | Medium | v0.2.13 | ✅ Completed |
| | Model Dependency Chaos Engineering Suite (`devops ai chaos-model`) | Pytest / Fallback Routing | High | Medium | v0.2.13 | ✅ Completed |
| | Multi-Model LLM Benchmark Evaluation Harness | Pytest / Feedback Dataset | High | Low | v0.2.13 | ✅ Completed |
| | Parallel Async Multi-File Review Worker Pool & Streaming Diff | Python 3.14 TaskGroup / Generator | High | Medium | v0.2.13 | ✅ Completed |
| | Dynamic Package Introspection & Type Stub Parser (`devops ai ingest library`) | `ast` / `pkgutil` / `inspect` | High | Medium | v0.2.14 | ✅ Completed |
| | Multi-Source Documentation & Standards Ingester (`devops ai ingest docs`) | `httpx2` / `pathspec` | High | Medium | v0.2.14 | ✅ Completed |
| | GitHub Issue Triage & Management Engine (`devops gh issues`) | GitHub API / `httpx2` | High | Medium | v0.2.14 | ✅ Completed |
| | Import-Driven AST Prompt Grounding & Contract Injection | AST / PydanticAI | High | Medium | v0.2.14 | ✅ Completed |
| | Tree-Sitter Multilingual AST Graph & Code Intelligence Engine | `tree-sitter` / Multi-Language | High | Medium | v0.2.14 | ✅ Completed |
| | Library API Drift & Deprecation Auditor | AST / McCabe | High | Medium | v0.2.14 | ✅ Completed |
| | AI Context Packing & Symbol-Pruned Prompt Synthesizer | `devops_cli.ai.context_packer` | High | Medium | v0.2.14 | 📋 Scheduled (P2) |
| | Complete Security Scanner Migration to `BaseSecurityScanner` & `ScannerRegistry` | Python ABC / Subprocess | High | Medium | v0.2.15 | 📋 Scheduled (P0) |
| | Centralized K8s Logging Stack & LogQL CLI (`devops k8s logs`) | Grafana Loki / Fluent Bit / LogQL | High | Medium | v0.2.15 | 📋 Scheduled (P0) |
| | Infracost FinOps Cloud Cost Engine (`devops tf cost`) | `infracost` CLI | High | Medium | v0.2.15 | 📋 Scheduled (P1) |
| | Multi-Cluster ArgoCD Fleet Sync & Rollouts | Argo Rollouts / Prometheus | High | High | v0.2.15 | 📋 Scheduled (P1) |
| | Automated GitOps Drift Detection & Webhook Sync | Watchdog / ArgoCD REST | High | Medium | v0.2.15 | 📋 Scheduled (P1) |
| | Sigstore Cosign Container Provenance (`devops docker sign|verify`) | `cosign` CLI / OS Keyring | High | Medium | v0.2.15 | 📋 Scheduled (P1) |
| | Falco eBPF Runtime Security & Anomaly Streamer | `falco` / eBPF | High | Medium | v0.2.15 | 📋 Scheduled (P2) |
| | Ephemeral Workload Sandbox Lifecycle Engine (`devops sandbox`) | Docker SDK / Rootless Containers | High | Medium | v0.2.16 | 📋 Scheduled (P0) |
| | Cgroup Metrics & Prometheus Scraping Subsystem | `prometheus-client` / cgroups | High | Medium | v0.2.16 | 📋 Scheduled (P1) |
| | W3C Traceparent Propagation & Distributed Trace Correlation | OpenTelemetry SDK / Jaeger | High | Medium | v0.2.16 | 📋 Scheduled (P1) |
| | OpenAPI & Schema-Driven Dynamic API Fuzzer (`devops sandbox fuzz`) | `hypothesis` / OpenAPI / Mutators | High | Medium | v0.2.17 | 📋 Scheduled (P0) |
| | Autonomous Closed-Loop Debugging & Iterative Patch Engine | PydanticAI / AST / Subprocess | High | High | v0.2.17 | 📋 Scheduled (P0) |
| | Dynamic Application Security Testing (DAST) & Egress Scanner | OWASP ZAP / Nuclei / Subprocess | High | Medium | v0.2.17 | 📋 Scheduled (P1) |
| | Multi-Region Workstation Mesh & Cluster Federation | Kubernetes / Fleet | High | High | v0.3.0 | 💡 Future Vision |
| | Autonomous Self-Healing Agent Pipeline | PydanticAI / Diagnostic | High | High | v0.3.0 | 💡 Future Vision |
| | Cloud-Native Ephemeral Test Environment Engine | Minikube / Helm / Ingress | High | Medium | v0.3.0 | 💡 Future Vision |
| | Distributed Multi-Cluster Telemetry & OTel Egress Mesh | OTel Collector / Prometheus | High | High | v0.3.0 | 💡 Future Vision |
| | Distributed Cache & Shared Semantic Embeddings Sync | S3 / OCI / SQLite | High | Medium | v0.3.0 | 💡 Future Vision |
| **Tactical Additions** | Line-Level PR Comments, Dataset Exporter, Custom Personas & Headless Auth | GitHub API / JSONL / Keyring | High | Medium | v0.1.x | ✅ Completed |
| | Kyverno & OPA Gatekeeper Admission Validator | `kyverno-cli`, `opa` | Medium | Medium | v0.2.3 | ✅ Completed |
| | k6 Performance & Latency Smoke Tester | `k6` CLI | Medium | Medium | v0.2.3 | ✅ Completed |
| | Dagger Containerized Python Pipeline Engine | `dagger-io` SDK | Medium | High | v0.2.3 | ✅ Completed |
| | Architecture & Threat Diagram Synthesis | `diagrams`, `mermaid-cli` | Medium | Medium | v0.2.4 | ✅ Completed |
| | Automated PR Remediation Branch Generator | Git / GitHub API | Medium | Medium | v0.2.4 | ✅ Completed |
| | FastMCP JSON Schema Exporter CLI (`devops mcp export-schemas`) | FastMCP / Introspection | Medium | Low | v0.2.11 | ✅ Completed |
| | Executive Summary & Good/Bad Pattern Report Generation | Markdown / Rich Panels | Medium | Low | v0.2.11 | ✅ Completed |
| | Logfire Structured AI Observability Bridge | `logfire` SDK / OTel | Medium | Medium | v0.2.13 | ✅ Completed |
| | Autonomous RAG Index Drift Detection & Auto-Reindexing | Git / Qdrant Sync | Medium | Low | v0.2.14 | 📋 Scheduled (P2) |
| | FastMCP K8s Centralized Log Tools (`k8s_logs_query`, `k8s_logs_tail`) | FastMCP / Loki REST API | High | Low | v0.2.15 | 📋 Scheduled (P0) |
| | Local GitOps Project Orchestration Pipeline | Git Daemon / ArgoCD App-of-Apps | High | Medium | v0.2.15 | 📋 Scheduled (P1) |
| | Core Dependency Ecosystem Alignment | `uv lock --upgrade` / PyPI | Medium | Low | v0.2.15 | 📋 Scheduled (P2) |
| | Streaming Diagnostic Log Aggregator & Stacktrace Detector | `rich.live` / Regex | Medium | Low | v0.2.16 | 📋 Scheduled (P1) |
| | Sandbox Chaos Fault & Resource Exhaustion Injection | `tc` / cgroups / Signals | Medium | Medium | v0.2.17 | 📋 Scheduled (P1) |
| | FastMCP Sandbox Tools & Dynamic System Resources | FastMCP / PydanticAI | High | Low | v0.2.17 | 📋 Scheduled (P1) |
| **De-prioritized** | Bare-Metal OS Installers | Shell scripts | Low | High | — | ❌ Rejected (DevContainer native) |
| | Heavyweight Monolithic Orchestrators | Full LangChain | Low | High | — | ❌ Rejected (FastMCP + PydanticAI) |
