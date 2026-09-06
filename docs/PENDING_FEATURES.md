# Pending Features & Design Proposals — devops-cli

> [!NOTE]
> This document has been consolidated into the comprehensive [Strategic Roadmap (`docs/ROADMAP.md`)](ROADMAP.md).
> Please consult [`ROADMAP.md`](ROADMAP.md) for the active release roadmap, technical specifications, and ROI prioritization matrix.

---

## 🎯 Active Release Focus

### Current Milestone: `v0.2.11` (Active Development)
1. **Workstation Infrastructure Valkey Migration**: Replaced all Redis components in the Kubernetes stack (ArgoCD and LLM stack) with Valkey 8.0-alpine under the BSD-3-Clause open-source license.
2. **Codebase Stylistic & Structural Drift Remediation & Parameter Establishment**:
   - Zero functions exceeding nesting depth 5 (<6 indentations) project-wide across `src/devops_cli`.
   - Reduced cyclomatic complexity $\le 10$ across tool factory closures (`FileSystem.get_tools`).
   - Standardized domain exception taxonomy inheriting from `DevOpsCLIError`, completely eradicating bare `ValueError`/`RuntimeError` across domain logic.
   - Clean test collection hygiene (`__test__ = False` on mock models) and unawaited coroutine prevention.
   - Automated architectural invariant quality gates in CI (`tests/test_architectural_invariants.py`).
3. **FastMCP Server Tool Expansion & Antigravity Schema Integration**:
   - Expanded FastMCP server from 53 to 72 registered tools achieving 1:1 parity with CLI subcommands (Kubernetes chaos/audit/lint/validate/diff, Trivy, Gitleaks, Semgrep, Checkov, AIBOM, SBOM, Vault, benchmark, git branch/PR).
   - Introduced 4 FastMCP prompt templates and 6 dynamic system resources.
   - Added `devops mcp export-schemas` subcommand.
   - Synchronized lazy tool schemas directly to Antigravity IDE (`/home/vscode/.gemini/antigravity-ide/mcp/devops-cli/`).
4. **Submodule Boilerplate Consolidation & Usability Architecture (Phase 42)**:
   - Declarative `@dry_run_command` in `src/devops_cli/dry_run/decorator.py` eliminating repetitive manual dry run checking across command modules.
   - Universal CLI error boundary and execution decorator (`@cli_command_handler`) in `src/devops_cli/core/command_decorator.py`.
   - Pure domain filesystem containment helper `safe_resolve_subpath` in `src/devops_cli/core/paths.py`.
   - Structured subprocess execution and JSON deserializer `run_json_subprocess` in `src/devops_cli/core/process.py`.
   - Binary pre-flight checker `require_binary` / `check_binary` in `src/devops_cli/core/binaries.py`.
   - Centralized secret sanitizer `mask_secrets`, `mask_dict_secrets`, `mask_uri_credentials` in `src/devops_cli/security/sanitizer.py`.
   - Resilient markdown JSON block extractor `extract_json_block` in `src/devops_cli/core/serialization.py`.
5. **Declarative Security Framework Foundation & AST Cache Tier (Phase 43)**:
   - `BaseSecurityScanner` abstract base class standardizing execution lifecycle, pre-flight checks, timeouts, and normalized `Finding` models.
   - Dynamic `ScannerRegistry` for capability filtering and batch scan dispatch.
   - Thread-safe in-memory `ASTCache` keyed by `(filepath, st_mtime)` eliminating redundant AST parsing during multi-persona reviews.
   - Declarative `render_table` output helper in `src/devops_cli/output/table_builder.py` consolidating table layouts and JSON/YAML conversion.
6. **GitHub Management & Quality Automation (Phase 44)**:
   - Declarative GitHub label taxonomy (`.github/labels.yml`) and management CLI (`devops gh labels list|sync|audit`).
   - Roadmap milestone extraction and progress metrics (`devops gh milestones list|sync|status`).
   - GitHub Projects v2 lifecycle integration and 4 standardized views (`devops gh project status|sync|template`, `devops gh views list|spec`).
   - 6 FastMCP GitHub tools (`gh_label_list`, `gh_label_sync`, `gh_milestone_list`, `gh_milestone_sync`, `gh_project_status`, `gh_view_spec`).
   - Task Manual 13 in Knowledge Base (`tasks/github_project_management.md`).
7. **Documentation & AI Instruction Token Optimization (Phase 45)**:
   - Root `AGENTS.md` instructions optimized by 36% (10.5 KB reduction), eliminating context window truncation.
   - Review prompt stack deduplication across `review.md`, `guardrails_isolation.md`, and `verify_finding_system.md` saving 34% tokens.
   - Dedicated agent data directory isolation under `./.data/agent`.
8. **DevSecOps Architectural Review & Zero-Trust Defense-in-Depth (Phase 47)**:
   - Comprehensive architectural security review ([`devsecops_architectural_review.md`](../.gemini/antigravity-ide/brain/eca133d3-ba90-4e2d-a22d-06052bbec047/devsecops_architectural_review.md)) detailing 1 Critical, 4 High, and 4 Medium/Low findings.
   - `OpenAIProvider` Authentication Header Injection: Inject `Authorization: Bearer <token>` in `OpenAIProvider.generate()` leveraging `settings.ai.openai_api_key` or OS Keyring.
   - Fail-Closed SSRF DNS Resolution Guard: Harden `_enforce_non_private_ssrf` in `devops_cli.core.validation` to fail closed when `allow_private=False` upon DNS timeouts, `socket.gaierror`, or `OSError`.
   - Universal Secret Sanitizer Pattern Expansion: Expand `_SECRET_PATTERNS` in `devops_cli.security.sanitizer` with Vault tokens (`hvs.*`, `s.*`), GitLab PATs (`glpat-*`), Slack/Discord webhooks, and HuggingFace API keys (`hf_*`).
   - Docker Workload Sandbox Security Hardening: Harden `WorkloadSandboxRunner` in `devops_cli.docker.sandbox` by enforcing `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `pids_limit=256`, default read-only volume mounting, and blocking sensitive host paths (`~/.ssh`, `~/.aws`, `~/.kube`, `.git`).
   - Context-Aware Review Pre-Filter & Test Noise Reduction: Scope Gitleaks scanner pre-filter to ignore test mock fixtures (`tests/test_*.py`) and documentation examples in compliance with `AGENTS.md` guidelines.

### Previous Milestones
- **`v0.2.10` (Completed)**: Native Pydantic AI Framework Subsystem Adoption, Autonomous Common Hallucinations Registry & Hardened Matching Engine, Secret Sanitizer Regex Hardening, Codebase Hygiene & Zombie Code Elimination.
- **`v0.2.9` (Completed)**: Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`), Unified Async HTTP/2 Connection Broker (`src/devops_cli/http/broker.py`), Local Kubernetes Chaos & Fault Injection Engine (`src/devops_cli/k8s/chaos_runner.py`), Continuous IDE File Watcher (`devops ai review path --watch`), Automated Dependency Vulnerability Remediation PR Engine (`devops scan fix`), Isolated Dockerized Workload Sandbox (`devops docker sandbox`), Enterprise Vault & Cloud KMS Secret Broker (`devops vault`), Kubernetes Background Port-Forward Daemon (`devops k8s port-forward`).
- **`v0.2.8` (Completed)**: Output Subsystem Modularization (`src/devops_cli/output/formatters/`), Language Message Catalog & Badge Localization (`src/devops_cli/lang/en/messages.py`), Declarative Dispatch Registries, Zombie Code Elimination.
- **`v0.2.7` (Completed)**: Model Curation Pipeline & AI Bill of Materials (AIBOM) Generator (`devops scan aibom`), "Big Decides, Small Types, Big Checks" Synthesis Protocol, Zero-Allocation AST Stream Parser, Cross-Encoder Context Re-Ranker, Streaming Serializers, SSH Key Prefix Support.
- **`v0.2.6` (Completed)**: Static Code Complexity & Cyclomatic Depth Linter (`devops scan complexity`), Syft & Grype Automated SBOM Generator (`devops scan sbom`), Git-Diff Aware Test Selector (`devops test run --diff`), Real-Time Resource & State Watchers (`--watch`), Dynamic Multi-Axis Model Router (`devops_cli.ai.router`), In-Memory Embedding LRU Cache.

### Upcoming Milestones

#### Milestone: `v0.2.12` (Scheduled - P0)
1. **Valkey Workstation CLI Subsystem (`devops valkey`)**: Dedicated command group providing `ping`, `info`, `stats`, `keys [pattern]`, `get <key>`, `set <key> <val> [--ttl <sec>]`, `flush [--all]`, `cli`, and snapshot `backup`/`restore` managing local and remote Valkey instances via lightweight RESP3 socket communication without C dependencies.
2. **Valkey High-Performance Distributed AI & Embedding Cache (`ai.cache.backend=valkey`)**: Distributed SHA-256 keyed embedding and review finding cache tier (`sha256(chunk + model + dim)`) slashing duplicate LLM inference by up to 85% across concurrent CLI runs, file watchers, and CI workers with configurable TTL and LRU memory management.
3. **Distributed LLM Token Bucket & Concurrency Rate Limiter**: Valkey-backed atomic sliding-window rate limiter powered by Lua scripts (`valkey_token_bucket.lua`) enforcing Requests-Per-Minute (RPM) and Tokens-Per-Minute (TPM) caps to eliminate local Ollama GPU VRAM thrashing and cloud API 429 throttling.
4. **FastMCP Valkey Toolset & Live System Resource**: 6 FastMCP tools (`valkey_ping`, `valkey_info`, `valkey_get`, `valkey_set`, `valkey_keys`, `valkey_flush`) and dynamic system resource `resource://valkey/status` reporting real-time memory usage, connected clients, and cache hit ratios.
5. **Ephemeral Testcontainers Valkey Testing Harness**: Rootless container fixture (`testcontainers-python` running `valkey/valkey:8.0-alpine`) for offline unit and integration test suites without requiring live Minikube cluster dependencies.
6. **Valkey IT Domain Knowledge Base Manual (`it_domains/tools/valkey.md`)**: Comprehensive technical guide covering Valkey 8.0 architecture, RESP3 wire protocol, memory optimization, eviction policies, and cluster topologies (completed).
7. **Infrastructure Perimeter, Supply Chain & Workstation Zero-Trust (Phase 48)**:
   - Kubernetes Pod Security Admission (PSA) enforcement labels (`pod-security.kubernetes.io/enforce: restricted`, `pod-security.kubernetes.io/warn: restricted`) across all namespaces in `k8s/namespaces.yaml`.
   - Cluster Default-Deny NetworkPolicies: Author granular `NetworkPolicy` manifests for `k8s/llm/`, `k8s/monitoring/`, and `k8s/argocd/` with explicit DNS and inter-service egress rules.
   - Subprocess Environment Isolation & Credential Boundary: Restrict default environment inheritance in `run_subprocess` (`src/devops_cli/core/process.py`) to prevent ambient token leakage to untrusted child binaries.
   - Immutable GitHub Actions Commit SHA Pinning: Pin all actions across `.github/workflows/ci.yml` and `release.yml` to immutable 40-character commit SHAs with inline version comments.
   - Qdrant Vector Database API Key Secret Protection: Add optional API key authentication support and ClusterIP default configuration for production deployments in `k8s/llm/values-qdrant.yaml`.

#### Milestone: `v0.2.13` (Scheduled - P0)
1. **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)**: Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive exploration and symbol searching to local open models (Granite, Qwen2.5-Coder) under a "Big decides, small types, big checks" synthesis protocol, achieving 85%+ token savings.
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
3. **Falco eBPF Runtime Security & Anomaly Streamer (`devops k8s security-stream`)**: Real-time streaming kernel anomaly and container syscall events via eBPF probes with automated severity threshold filtering.
4. **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`)**: Advanced canary and blue-green rollout management across multi-cluster fleets with Prometheus metric-based rollback gates.
5. **Automated GitOps Drift Detection & Webhook Synchronization (`devops argo gitops watch`)**: Real-time git commit and inotify/watchdog triggers automatically signaling ArgoCD applications to reconcile local workspace modifications.
6. **Local GitOps Project Orchestration Pipeline (`devops argo cd apps bootstrap-gitops`)**: End-to-end declarative reconciliation connecting local background Git daemon (`git://host.minikube.internal:9418/k8s`), ArgoCD Root Application ("App of Apps" pattern), and multi-stack lifecycle (`infra`, `llm`).
7. **Sigstore Cosign Container Provenance & Image Signing (`devops docker sign|verify`)**: Keyless container image and manifest signing integrating with OS Keyring and OIDC tokens for verifiable supply-chain provenance.
8. **GitHub Enterprise Automation Phase 2 (`devops gh issues`, `branch-protection`, `secrets`)**: Automated issue triage/dedup, declarative branch protection policy enforcement, and libsodium workstation-to-GitHub secret sync.
9. **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`)**: Memory leak detection and async socket lifecycle validation across background daemons and MCP workers using `asyncio` and `tracemalloc`.
10. **Core Dependency Ecosystem Alignment (`pyproject.toml`)**: Routine version upgrades and compatibility validation across runtime and development dependencies (`click`, `typer`, `pydantic`, `pydantic-ai`, `gitpython`, `httpx2`, `ruff`).

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
