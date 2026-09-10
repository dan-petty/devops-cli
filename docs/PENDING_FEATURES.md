# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.13` (Active Development)
1. **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)** *(Completed - PR #60 / Issue #53)*: Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive exploration and symbol searching to local open models (Granite, Qwen2.5-Coder) under a "Big decides, small types, big checks" synthesis protocol, achieving 85%+ token savings.
2. **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen responsive terminal dashboard powered by `Textual` providing real-time tabs for live Kubernetes pods, Minikube services, Docker container metrics, OpenTelemetry span waterfalls, active AI review findings, and Valkey cache metrics with keyboard navigation (`1-5`, `q`, `r`, `?`).
3. **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**: "Chaos Monkey for Models" validation framework deliberately degrading frontier connections, injecting latency, and enforcing local open model fallbacks to verify that automation tools pass CI quality gates without human coaching.
4. **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**: Centralized emergency control to cleanly suspend active agent loops, schedulers, and background cron jobs during upstream provider outages, with zero-state-loss failover to local endpoints.
5. **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**: Automated evaluation suite benchmarking candidate models against human-in-the-loop validated feedback datasets (`.data/feedback_dataset.jsonl`), calculating precision, recall, and hallucination scores.
6. **Parallel Async Multi-File Review Worker Pool & Streaming Diff Parser**: Concurrent async file review execution utilizing Python 3.14 `asyncio.TaskGroup` bounded by semaphores and token budgets, combined with streaming generator-based unified diff chunking reducing peak memory by 60% and cutting review runtimes by up to 70%.

### Previous Milestones
- **`v0.2.12` (Completed)**: Valkey Workstation Management & High-Performance Distributed Caching Tier, Zero C-Dependency RESP3 Protocol, Atomic Token Bucket Rate Limiter, Distributed AI Cache Tier, FastMCP Valkey Toolset (6 tools) & Status Resource, Runtime Duration Formatting, GitHub Projects v2 Automation.
- **`v0.2.11` (Completed)**: Workstation Infrastructure Valkey Migration, Codebase Stylistic & Invariant Enforcement, FastMCP Tool Parity, Declarative Submodule Boilerplate Consolidation, Declarative Security Framework Foundation, GitHub Management & Project Views, Token Optimization, DevSecOps Architectural Review & Zero-Trust Defense-in-Depth.
- **`v0.2.10` (Completed)**: Native Pydantic AI Framework Subsystem Adoption, Autonomous Common Hallucinations Registry & Hardened Matching Engine, Secret Sanitizer Regex Hardening, Codebase Hygiene & Zombie Code Elimination.
- **`v0.2.9` (Completed)**: Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`), Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`), Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`), Continuous IDE File Watcher (`devops ai review path --watch`), Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`), Isolated Dockerized Workload Sandbox (`devops docker sandbox`), Enterprise Vault & Cloud KMS Secret Broker (`devops vault`), Kubernetes Background Port-Forward Daemon (`devops k8s port-forward`).
- **`v0.2.8` (Completed)**: Output Subsystem Modularization (`src/devops_cli/output/formatters/`), Language Message Catalog & Badge Localization (`src/devops_cli/lang/en/messages.py`), Declarative Dispatch Registries, Zombie Code Elimination.
- **`v0.2.7` (Completed)**: Model Curation Pipeline & AI Bill of Materials (AIBOM) Generator (`devops scan aibom`), "Big Decides, Small Types, Big Checks" Synthesis Protocol, Zero-Allocation AST Stream Parser, Cross-Encoder Context Re-Ranker, Streaming Serializers, SSH Key Prefix Support.
- **`v0.2.6` (Completed)**: Static Code Complexity & Cyclomatic Depth Linter (`devops scan complexity`), Syft & Grype Automated SBOM Generator (`devops scan sbom`), Git-Diff Aware Test Selector (`devops test run --diff`), Real-Time Resource & State Watchers (`--watch`), Dynamic Multi-Axis Model Router (`devops_cli.ai.router`), In-Memory Embedding LRU Cache.

### Upcoming Milestones

#### Milestone: `v0.2.13` (Scheduled - P0)
1. **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)** *(Completed - PR #60 / Issue #53)*: Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive exploration and symbol searching to local open models (Granite, Qwen2.5-Coder) under a "Big decides, small types, big checks" synthesis protocol, achieving 85%+ token savings.
2. **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen responsive terminal dashboard powered by `Textual` providing real-time tabs for live Kubernetes pods, Minikube services, Docker container metrics, OpenTelemetry span waterfalls, active AI review findings, and Valkey cache metrics with keyboard navigation (`1-5`, `q`, `r`, `?`).
3. **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**: "Chaos Monkey for Models" validation framework deliberately degrading frontier connections, injecting latency, and enforcing local open model fallbacks to verify that automation tools pass CI quality gates without human coaching.
4. **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**: Centralized emergency control to cleanly suspend active agent loops, schedulers, and background cron jobs during upstream provider outages, with zero-state-loss failover to local endpoints.
5. **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**: Automated evaluation suite benchmarking candidate models against human-in-the-loop validated feedback datasets (`.data/feedback_dataset.jsonl`), calculating precision, recall, and hallucination scores.
6. **Parallel Async Multi-File Review Worker Pool & Streaming Diff Parser**: Concurrent async file review execution utilizing Python 3.14 `asyncio.TaskGroup` bounded by semaphores and token budgets, combined with streaming generator-based unified diff chunking reducing peak memory by 60% and cutting review runtimes by up to 70%.
7. **Logfire Structured AI Observability Bridge (`logfire`)**: Native Pydantic Logfire integration binding with OpenTelemetry distributed spans and Rich terminal formatters for live agent reasoning inspection, token throughput counters, and trace waterfalls.

#### Milestone: `v0.2.14` (Scheduled - P1)
1. **Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (`tree-sitter`)**: Incremental multi-language syntax tree parsing across Python, TypeScript, Go, Rust, Java, and HCL for whole-repository symbol navigation, call-graph synthesis, and structural diff analysis.
2. **Dynamic Package Introspection & Type Stub Parser (`devops ai ingest library`)**: Automated AST and type stub (`.pyi`) extractor indexing installed library classes, method signatures, parameter types, defaults, and docstrings into a structured contract store.
3. **Multi-Source Documentation & Standards Ingester (`devops ai ingest docs`)**: SSRF-guarded crawler ingesting local and remote documentation sets (Sphinx, MkDocs, DevDocs, PEPs, CIS benchmarks) into clean, chunked markdown reference collections.
4. **Dedicated Library Vector Tier (`devops_libraries`) & Valkey Symbol Store**: Segregated Qdrant collection and Valkey cache tier providing sub-millisecond API signature lookups and hybrid dense-sparse search.
5. **Import-Driven AST Prompt Grounding & Contract Injection**: Automatic detection of third-party imports across review diffs and on-the-fly injection of verified library API contracts into LLM prompts, eliminating 99% of third-party API hallucinations.
6. **Library API Drift & Deprecation Auditor (`devops ai audit-library-usage`)**: Static AST analyzer comparing workspace calls against library contracts to detect deprecated parameters, removed APIs, and signature drift prior to library upgrades.
7. **FastMCP Library Tools & Dynamic System Resource**: Exposing `ai_ingest_library`, `ai_query_library`, `ai_inspect_symbol`, and dynamic resource `resource://libraries/indexed` to IDE AI coding assistants.
8. **Autonomous RAG Index Drift Detection & Auto-Reindexing**: Scheduled background verification of vector store sync against workspace git tracking branches.

#### Milestone: `v0.2.15` (Scheduled - P1)
1. **Complete Security Scanner Migration to `BaseSecurityScanner` & `ScannerRegistry`**: Complete migration of all 11 scanner modules (`bandit`, `checkov`, `dive`, `gitleaks`, `kubeconform`, `kubelinter`, `pluto`, `popeye`, `semgrep`, `tflint`, `trivy`) to inherit from `BaseSecurityScanner`, standardizing execution, timeouts, JSON parsing, and normalized `Finding` models.
2. **Infracost FinOps Cloud Cost Engine (`devops tf cost`)**: Integrated Infracost CLI evaluating financial impacts of Terraform/OpenTofu diffs, enriching `pm` & `architect` review personas with monthly cost deltas.
3. **Centralized Kubernetes Logging Stack & LogQL CLI Integration (`devops k8s logs` / `devops logs`)**: Declarative Loki & Fluent Bit / Vector aggregation stack (`k8s/logging/`, `devops k8s deploy-stack --stack logging`), pre-configured Grafana data source with `trace_id` distributed trace correlation, native LogQL terminal querying (`query`, `tail`, `stream`), FastMCP incident diagnosis tools (`k8s_logs_query`, `k8s_logs_tail`), and interactive Terminal UI (`devops dashboard`) logs view.
4. **Falco eBPF Runtime Security & Anomaly Streamer (`devops k8s security-stream`)**: Real-time streaming kernel anomaly and container syscall events via eBPF probes with automated severity threshold filtering.
5. **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`)**: Advanced canary and blue-green rollout management across multi-cluster fleets with Prometheus metric-based rollback gates.
6. **Automated GitOps Drift Detection & Webhook Synchronization (`devops argo gitops watch`)**: Real-time git commit and inotify/watchdog triggers automatically signaling ArgoCD applications to reconcile local workspace modifications.
7. **Local GitOps Project Orchestration Pipeline (`devops argo cd apps bootstrap-gitops`)**: End-to-end declarative reconciliation connecting local background Git daemon (`git://host.minikube.internal:9418/k8s`), ArgoCD Root Application ("App of Apps" pattern), and multi-stack lifecycle (`infra`, `llm`).
8. **Sigstore Cosign Container Provenance & Image Signing (`devops docker sign|verify`)**: Keyless container image and manifest signing integrating with OS Keyring and OIDC tokens for verifiable supply-chain provenance.
9. **Extended GitHub Enterprise Automation (`devops gh issues`, `branch-protection`, `secrets`)**: Automated issue triage/dedup, declarative branch protection policy enforcement, and libsodium workstation-to-GitHub secret sync.
10. **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`)**: Memory leak detection and async socket lifecycle validation across background daemons and MCP workers using `asyncio` and `tracemalloc`.
11. **Core Dependency Ecosystem Alignment (`pyproject.toml`)**: Routine version upgrades and compatibility validation across runtime and development dependencies (`click`, `typer`, `pydantic`, `pydantic-ai`, `gitpython`, `httpx2`, `ruff`).

#### Milestone: `v0.2.16` (Scheduled - P1)
1. **Long-Running Workload Sandbox Lifecycle Engine (`devops sandbox deploy|status|stop|exec`)**: Rootless container and ephemeral Kubernetes namespace (`sandbox-<app>-<timestamp>`) lifecycle orchestration, dynamic host port binding (`10000-60000`), Service mapping, strict cgroup v2 resource limits (`cpu_limit`, `memory_limit`, `pids_limit=256`), read-only root filesystems, `/tmp` tmpfs, `cap_drop=["ALL"]`, and state tracking in `.data/sandbox/instances.json`.
2. **Comprehensive Endpoint, Readiness & Health Probing Subsystem (`devops sandbox probe`)**: Non-blocking TCP socket reachability, HTTP/REST readiness/liveness checks (`/healthz`, `/health`, `/ready`, `/live`, `/`), OpenAPI schema-driven route crawling (`/openapi.json`), gRPC health protocol (`grpc.health.v1.Health/Check`) and reflection probing, with strongly typed `SandboxProbeReport` Pydantic models.
3. **Cgroup Metrics, Prometheus Scraping & Real-Time Telemetry (`devops sandbox metrics`)**: Container-level cgroup v2 metric harvesting (CPU % utilization, memory RSS, page faults, open file descriptors, network RX/TX bytes), automated Prometheus `/metrics` scraping (request counters, 5xx error rates, latency histograms), and threshold alerts.
4. **Traceparent Propagation & Distributed Trace Correlation (`devops sandbox traces`)**: W3C Trace Context injection (`traceparent`, `tracestate`) on synthetic probes and tests, cross-referencing with application spans in local OpenTelemetry Collector (`http://localhost:4318`), Jaeger, and Logfire, rendering interactive terminal trace waterfalls.
5. **Streaming Diagnostic Log Aggregator & Panic Detector (`devops sandbox logs`)**: Real-time multiplexed stdout/stderr log tailing (`--follow`), automated regex parsing for Python tracebacks, Go panics, Java stacktraces, Rust panics, and segmentation faults, with diagnostic incident capture in `.data/sandbox/incidents/<incident_id>.json`.

#### Milestone: `v0.2.17` (Scheduled - P1)
1. **OpenAPI & Schema-Driven Dynamic API Fuzzing Engine (`devops sandbox fuzz`)**: Mutational and grammar-aware payload generation based on OpenAPI 3.x / REST schemas, boundary and type confusion testing (null bytes, extreme string lengths, integer wraps, NaN), security injection test suite (SQLi, command injection, path traversal, XXE, SSRF), stateful API sequence chaos, and minimal reproduction case generator (`.data/sandbox/repros/<fuzz_id>.json`).
2. **Dynamic Application Security Testing (DAST) & Egress Scanner (`devops sandbox scan`)**: Automated OWASP ZAP baseline scans and Nuclei templates targeting sandbox ports, container filesystem mutation auditing (`docker diff` verifying zero unauthorized mutations outside `/tmp`), network egress anomaly detection (blocking private IP and metadata probing), and runtime privilege verification.
3. **Chaos Fault & Resource Exhaustion Injection (`devops sandbox chaos`)**: Dynamic CPU throttling, memory ballooning (OOM testing), disk fill simulations, network latency and packet drop injection (`tc`), and process signal resilience testing (`SIGTERM`, `SIGHUP`, `SIGKILL`).
4. **Autonomous Closed-Loop Debugging & Iterative Code Patch Engine (`devops sandbox iterate`)**: End-to-end iteration pipeline (`deploy` $\to$ `probe` $\to$ `monitor` $\to$ `fuzz` $\to$ `scan` $\to$ `diagnose` $\to$ `patch` $\to$ `re-verify`), mapping stacktraces to source AST nodes, multi-persona AI remediation (`devsecops`, `qa`, `architect`), automated patch re-verification in the sandbox, and continuous hot-reload watch mode (`--watch`).
5. **FastMCP Sandbox Tools & Dynamic System Resources**: 6 FastMCP tools (`sandbox_deploy`, `sandbox_probe`, `sandbox_metrics`, `sandbox_fuzz`, `sandbox_scan`, `sandbox_iterate`) and dynamic resources (`resource://sandbox/status`, `resource://sandbox/metrics`, `resource://sandbox/incidents`).

#### Milestone: `v0.3.0` (Future Vision - P2)
1. **Multi-Region Workstation Mesh & Cluster Federation**: Cross-cluster service discovery and state sync.
2. **Autonomous Self-Healing Agent Pipeline**: Self-diagnostic remediation loops.
3. **Cloud-Native Ephemeral Test Environment Engine**: Dynamic Minikube/Helm ephemeral environments.
4. **Zero-Trust Git Commit & Tag Cryptographic Verification**: Automated verification of SSH/GPG and Sigstore keyless commit signatures.
5. **Distributed Multi-Cluster Telemetry & OTel Egress Mesh**: Global trace and metric federation.
6. **Distributed Cache & Shared Semantic Embeddings Sync**: S3 / OCI-backed shared LLM response and vector embedding cache.

---

## 📖 Related Strategic Documents
- **Master Strategic Roadmap**: [`docs/ROADMAP.md`](ROADMAP.md)
- **Active Working Log**: [`docs/LOG.md`](LOG.md)
- **System Architecture**: [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Knowledge Base Task Manuals**: [`src/devops_cli/ai/knowledge_base/`](../src/devops_cli/ai/knowledge_base/README.md)
