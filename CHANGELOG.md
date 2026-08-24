# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

### Added

### Changed

### Fixed

## [0.1.13] - 2026-08-24

### Added
- **Embedding Model Benchmark Suite (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark`)**:
  - Dedicated vector embedding benchmark engine (`EmbeddingBenchmarkRunner`, `EmbeddingBenchmarkResult`, `EmbeddingBenchmarkReport`) evaluating dense vector embedding models (`qwen3-embedding`, `nomic-embed-text`, `all-minilm`, `bge-*`, `text-embedding-3-*`).
  - Automatic model classification and CLI routing in `devops ai benchmark` when embedding models are provided.
  - Evaluation corpus of 15 domain-specific query-passage pairs across 5 DevOps domains (Security, Kubernetes, Architecture, CI/CD, Infrastructure) and 10 distractor passages.
  - Evaluates semantic retrieval quality (Recall@1, Recall@3, Mean Reciprocal Rank (MRR), and Cosine Margin), single-query latency (p50/p95 ms), batch throughput (items/sec and chars/sec), and vector health ($L_2$ norm and dimension verification).
  - Rich interactive terminal leaderboard tables, JSON export to `.data/benchmarks/`, and Markdown summary rendering.
- **Local & Homelab TLS Certificate Management (`devops tls`, `devops cert`, `devops_cli.crypto`)**:
  - X.509 Certificate Authority and TLS server/client certificate generation using `cryptography.x509`.
  - Subject Alternative Name (SAN) auto-generation supporting IP addresses, hostnames, localhost, homelab `.lan` / `.local` domains, and Kubernetes service FQDNs.
  - Automated Kubernetes TLS secret provisioning (`devops tls inject-k8s-secret`, `devops k8s enable-tls`) and cert-manager ClusterIssuer integration for homelab/k3s/minikube environments.
- **Universal OpenTelemetry Integration (`devops telemetry`, `devops otel`, `devops_cli.telemetry`)**:
  - End-to-end telemetry configuration, status inspection, and OTLP trace export across all CLI operations and AI multi-agent pipelines.
  - Jaeger Query UI and OTLP collector deployment configurations in `k8s/otel/jaeger.yaml`.

- **OpenTelemetry Universal Command Tracing & Span Instrumentation (`devops_cli.telemetry.tracer`)**:
  - Full end-to-end command tracing spanning CLI subcommands (`branches`, `devcontainer`, `docker`, `github`, `install_tools`, `k8s`, `kustomize`, `mcp`, `pr`, `release`, `scan`, `tf`, `tls`, `tofu`, `uv`, `workspace`).
  - Trace span lifecycle attributes, sanitized arguments, duration tracking, error status recording, and custom OTLP header authentication support.

### Changed
- **Review Schema & Finding Deduplication Hardening (`devops_cli.ai.review_schema`)**:
  - Eliminated fragile literal collections, ad-hoc string lists, and keyword regex heuristics in favor of clean structural schema validation and standard path parsing.
  - Robust set-based token similarity with universal token length filtering and configurable line-range overlap tolerance for duplicate finding consolidation.
  - Hardened location parser handling POSIX URIs, GitHub-style anchors (`#L10-L20`), line ranges (`:10-20`), and Windows path conventions.
- **Standard Library & PEP 508 Code Hygiene Refactoring (`devops_cli.security.reference_extractor`)**:
  - Eliminated ad-hoc keyword lists and custom regex string splitting in favor of standard libraries (`ast`, `tokenize`, `packaging.requirements.Requirement`, `tomllib`, `json`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, `tldextract`).
  - Implemented PEP 508 requirement parsing for PyPI dependencies, PEP 621 `pyproject.toml` dependencies, optional dependency groups, and PEP 735 dependency groups.
  - Implemented AST string literal and comment tokenization for Python source code to eliminate false-positive domain matches on function calls, attributes, and variables.
  - Implemented RFC 2606 reserved domain exclusions (`.example`, `.test`, `.invalid`, `.localhost`) and strict public IP routability checks via `ipaddress.ip_address.is_global`.
- **Review Pipeline Linked File Context Optimization (`devops_cli.ai.review.pipeline`)**:
  - Added universal standard library filtering (`_UNIVERSAL_MODULES`) to prevent connecting all repository files via universal imports like `typing` or `pathlib`.
  - Bounded linked dependency files context to the top 10 relevant modules.
- **AI Review Tasks & Finding Verification Prompt Hardening**:
  - Hardened `src/devops_cli/ai/tasks/review.md` and `verify_finding.md` to prevent false positive detections and enforce actionable verification criteria.


## [0.1.12] - 2026-08-20

### Added
- **Universal Retrieval-Augmented Generation (RAG) Architecture (`devops ai rag`, `devops_cli.ai.rag`)**:
  - Polyglot syntax-aware AST chunker for Python, Go, Rust, TypeScript, JavaScript, Java, C/C++, Terraform/HCL, SQL, and Kubernetes YAML manifests.
  - Hierarchical technical documentation chunker preserving Markdown, AsciiDoc, and RST heading depth with breadcrumb hierarchy tracking.
  - Multi-project workspace autodetection (`Cargo.toml`, `go.mod`, `package.json`, `pyproject.toml`) and faceted semantic filtering (`--project`, `--language`, `--category`).
  - Native Qdrant vector database integration and Ollama dense embeddings generation (`all-minilm`).
- **Official `qdrant-client` SDK Adoption & Modernization**:
  - Replaced manual HTTP REST JSON calls with the official `qdrant-client` Python SDK with connection pooling, typed models, batch upserts, and payload filtering.
- **Hierarchical Configuration Modernization (`pydantic-settings`)**:
  - Upgraded `Settings` to inherit from `pydantic_settings.BaseSettings` with `SettingsConfigDict` supporting automatic environment variable binding (`DEVOPS_CLI_*`), schema validation, and secret masking while preserving OS Keyring security.
- **Multi-Context & Remote Cluster Kubernetes Support (`devops k8s`)**:
  - Added dynamic cluster reachability verification (`_cluster_reachable`) supporting remote k3s, EKS, and GKE cluster contexts via `kubectl cluster-info`.
  - Added `--context` (`-c`) option support across `deploy-stack`, `teardown-stack`, `port-forward`, and `configure-urls`.
  - Added automated iterative pre-existing Helm resource adoption (`_adopt_helm_resource_if_conflict`).
- **Multi-GPU Native Ollama DaemonSet Deployment**:
  - Integrated `k8s/llm/ollama-daemonset.yaml` with multi-GPU access (`NVIDIA_VISIBLE_DEVICES: "all"`), `runtimeClassName: nvidia`, hostPort 11434, and shared NFS model cache.
- **Structural Metadata Extraction Engine (`src/devops_cli/ai/rag/metadata.py`)**:
  - Polyglot dependency and import parsing across 8+ programming languages.
  - Automated security sensitivity classification tagging code chunks into `crypto`, `network`, `auth`, `secrets`, `db`, `fs`, and `iam`.
  - Document frontmatter metadata parser extracting YAML/TOML metadata and heading hierarchy metrics.
- **Multi-Signal Search Re-Ranking Engine (`src/devops_cli/ai/rag/reranker.py`)**:
  - Hybrid scoring fusion engine combining dense vector cosine similarity (0.60), lexical token overlap (0.25), exact symbol match bonuses (+0.15), query intent classification (+0.10 for docs/code), and security alignment (+0.10).
  - Attached transparent `rerank_score` and individual `rank_factors` to every retrieved chunk.
- **Universal AI Subcommand RAG Integration**:
  - `devops ai chat`: Per-turn conversational semantic retrieval (`--rag/--no-rag`).
  - `devops ai pipeline`: Seeds multi-agent review and reasoning pipelines with relevant codebase context.
  - `devops ai agents`: Retrieves architectural context and CLI conventions when generating canonical agent instructions.
  - `devops ai analyze`: Injects related architectural context during metadata analysis and pseudocode extraction.
  - `devops ai review`: Injects re-ranked cross-file context with symbol and security tags into multi-persona code reviews.
- **End-to-End OpenTelemetry Tracing & Observability Stack**:
  - Integrated OpenTelemetry trace lifecycle spans across LLM dispatches, pipeline stages, and CLI operations (`devops_cli.telemetry`).
  - Jaeger Query UI and OTLP collector deployment manifests (`k8s/otel/jaeger.yaml`).
  - Customized Grafana dashboards for AI inference latency, token metrics, and Kubernetes cluster health (`k8s/monitoring/dashboards/`).
- **DevContainer Background Git Daemon**:
  - Native automated background Git daemon with `--export-all` across `/workspaces/devops-cli/k8s` and `/workspaces/devops-cli/repos` during container post-start lifecycle.
- **GitHub PR Governance & Remote CI Inspection (`devops pr`)**:
  - Pull request lifecycle management (`create`, `status`, `checks`, `view`, `diff`) with automated release branch base targeting and CI check monitoring.
- **AI Review Subsystem Modularization & Decoupling**:
  - Refactored monolithic `commands/review.py` into cohesive domain modules under `src/devops_cli/ai/review/` (`runner.py`, `chunker.py`, `patching.py`, `exporter.py`, `verification.py`, `pipeline.py`).
- **Atomic AI Tasks, Finding Verification/Invalidation Criteria & Reportability Scoring**:
  - Decomposed AI review tasks into discrete, single-responsibility micro-steps to prevent prompt degradation.
  - Added explicit `verification_criteria` and `invalidation_criteria` to `Finding` data models.
  - Implemented criterion-based verification, deterministic confidence scoring, and `reportable: bool` assessment in review pipelines.
- **External Dependency Vulnerability Scanning & Network Reputation Auditing (`devops_cli.security.intelligence`)**:
  - Automated dependency extraction across Python (`pyproject.toml`, `requirements.txt`), JavaScript/TypeScript (`package.json`), Rust (`Cargo.toml`), and Go (`go.mod`) with live OSV.dev and NVD (NIST) vulnerability CVE lookups.
  - Automated extraction of external network references (public IPs, FQDNs, URLs in docs and source code) with Shodan InternetDB port/vulnerability and Cloudflare Radar threat reputation auditing.
  - Added formatted dependency and network intelligence tables to Markdown review reports and structured findings JSON payloads.
- **Universal AI Agent Memory & Automatic Summarization Engine (`devops_cli.ai.agents.memory`)**:
  - Incorporated structured `AgentMemory` with `MemoryEntry` tracking across all `PydanticAgent` instances, `MultiAgentPipeline` execution stages, and `devops ai chat` sessions.
  - Implemented automatic size-triggered context summarization (`auto_summarize_if_needed`) when interaction histories exceed message count or character limits, preserving critical technical decisions while consolidating older context.
- **Universal AI/LLM Response Fixer & JSON Recovery (`devops_cli.ai.fixer`)**:
  - Integrated `json-repair` library for resilient recovery and structural parsing of corrupted, truncated, or markdown-wrapped JSON payloads across all LLM inference streams.
  - Implemented thought-scratchpad filtering and dedicated natural language synthesis turns to guarantee clean user-facing outputs without leaked reasoning scratchpads.
- **Native Dependency Audit Tool (`scan_uv_audit`, `audit_dependencies`)**:
  - Integrated `uvx pip-audit` tools in native CLI tool registry (`devops_cli.ai.tools.native`) and FastMCP server (`devops_cli.ai.mcp.server`) for auditing Python dependencies in `pyproject.toml`, `uv.lock`, and `requirements.txt`.
- **Parallel Multi-Node LLM Prewarming (`devops ai chat --prewarm`)**:
  - Added parallel model prewarming and VRAM memory pinning (`keep_alive: "1h"`) across all configured Ollama cluster nodes at chat startup.
- **Architectural Separation of Constants and Defaults (`devops_cli.config`)**:
  - Decoupled immutable system invariants (`CONST_*` in `config/constants.py`) from configurable optional parameter defaults (`DEFAULT_*` in `config/defaults.py`).
  - Removed all `DEFAULT` prefixes and substrings from `CONST_` symbol definitions across the entire codebase.

### Changed
- **AI Agent Tool Execution & Anti-Repetition Loop Guardrails**:
  - Enforced parameter validation against tool schemas to eliminate stop-word argument hallucination.
  - Added duplicate tool call detection and autonomous natural language report synthesis in `PydanticAgent`.
- **Review Prompt & Verification Rule Hardening**:
  - Refined `src/devops_cli/ai/tasks/review.md` and `src/devops_cli/ai/tasks/verify_finding.md` to prevent speculative vulnerability reports on hypothetical helper behavior and eliminate false-positive syntax error hallucinations on standard Python 3 tuple exception handlers (`except (Err1, Err2):`).
  - Streamlined feedback dataset exporter (`devops ai review export-feedback`) to export complete review findings into `.data/feedback.jsonl` for continuous improvement benchmarks.

### Security
- **Path Traversal & Injection Defenses**:
  - Added strict path traversal defenses in `load_custom_repo_persona` (`src/devops_cli/ai/personas/__init__.py`).
  - Added tool description sanitization in `PydanticAgent` prompt construction (`src/devops_cli/ai/agents/pydantic_agent.py`) to prevent indirect prompt injection.
  - Added semantic version regex validation in `devops install-tools` binary downloads.
  - Added label format validation in `devops release prepare` before GitHub CLI invocation.
  - Switched Valkey deployment in `k8s/llm/valkey.yaml` from NodePort to `ClusterIP` and removed `--protected-mode no`.

### Fixed
- **API Boundary & Pipeline Invariants**:
  - Removed internal helper functions `_run_mcp_cmd` and `_validate_mcp_arg` from public `__all__` in `src/devops_cli/ai/mcp/__init__.py`.
  - Added positive integer validation for `max_turns_per_agent` and hoisted imports in `MultiAgentPipeline` (`src/devops_cli/ai/agents/pipeline.py`).
  - Added bounds enforcement on `top_k` and `score_threshold` and query masking in telemetry traces (`src/devops_cli/ai/rag/retriever.py`).

## [0.1.11] - 2026-08-18

### Added
- **Git & GitHub Project Best Practice Guardrails (`AGENTS.md`, `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`)**: Comprehensive AI agent and developer operational guardrails for branch hierarchy (zero direct commits to `main`, base branch targeting `release/vX.Y.Z`, fresh topic branches), commit hygiene (Conventional Commits, atomicity, pre-commit validation, zero leaked secrets), PR governance (no autonomous merging by agents, in-place topic branch updates, active CI monitoring, and issue linking), and targeted unit testing during iterative feature development before full final-stage test runs.
- **Published Dev Container User Guide & CLI Scaffolding (`docs/DEVCONTAINER_USAGE.md`)**: Comprehensive user guide for consuming the published multi-tool GHCR DevContainer image (`ghcr.io/dan-petty/devops-cli/devcontainer:latest`) across VS Code, Cursor, and GitHub Codespaces, along with `--published` (`-p`) and `--image` (`-i`) flag support in `devops devcontainer init`.
- **Automated DevContainer Pre-Commit Installation**: Integrated automated `uv run pre-commit install` into the container startup lifecycle hook (`devops devcontainer run-lifecycle --post-start`) and added `.gitattributes` to enforce consistent LF line endings.

### Changed
- **Single Source of Truth Project Metadata Architecture**: Centralized metadata loading in `src/devops_cli/config/metadata.py` dynamically reading package version, description, and Python requirements directly from `pyproject.toml` and standard package distribution metadata (`importlib.metadata`), eliminating hardcoded version and configuration duplication across commands and defaults.
- **AI / LLM Prompt & Token Density Optimization**: Optimized persona domain prompts (`devsecops`, `architect`, `auditor`, `pm`, `qa`) and core review task prompts (`review.md`, `analyze_pseudocode.md`, `verify_finding.md`, `compose.md`, `metadata.md`, `chat.md`), eliminating cross-prompt rule duplication and reducing prompt token consumption.
- **CI Workflow Optimization & Duplicate PR Check Elimination**: Refactored `.github/workflows/ci.yml` to restrict `push` triggers strictly to `main` while maintaining `pull_request` triggers on `main` and `release/**`, eliminating duplicate CI runs on pull requests, and added workflow concurrency management to cancel superseded in-flight builds.
- **Evergreen Validation Nomenclature**: Standardized validation terminology across GitHub Actions workflows, CLI tooling, and documentation from numbered gates to evergreen `validate` / `Validation`.

### Fixed
- **DevContainer MCP & Minikube Initialization Resilience**: Enhanced `devops devcontainer post-start` to automatically scaffold and sync `.vscode/mcp.json` with explicit `env: { PATH: ... }` to `~/.gemini/config/mcp_config.json` and `.agents/mcp_config.json`. Hardened Minikube initialization with GPU detection (`nvidia-smi`), automatic fallback to CPU driver (`--driver=docker`), Docker daemon readiness verification, and automatic `minikube update-context` kubeconfig synchronization.
- **DevContainer GHCR Image Publishing Resilience**: Hardened `.github/workflows/release.yml` with lowercase GHCR repository naming and streamlined tag publication (`vX.Y.Z,latest`) to prevent 403 / `unknown blob` upload errors.

## [0.1.10] - 2026-08-18

### Added
- **Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**: Comprehensive operational manual outlining inner development loops, PR lifecycles, release orchestrations, security audit schedules, and workspace synchronization with explicit sequence ordering, frequencies, and troubleshooting matrices.
- **Strict Python 3.14 Environment Gate (`devops ci python-version`)**: Enforced standard Python 3.14+ runtime requirement across all CI quality checks and dev container configurations.
- **Actionlint & Pre-Commit Hook Integration**: Integrated [actionlint](https://github.com/rhysd/actionlint) (`actionlint-py`) into `devops ci actionlint`, `.github/workflows/ci.yml` validation pipeline, and root `.pre-commit-config.yaml` to detect GitHub Actions workflow schema discrepancies and parameter mismatches before triggering remote jobs.
- **DevContainer Pre-Build Smoke Test & Manifest Validation**: Added `devops devcontainer validate` command with JSONC comment-stripping and schema/mount/feature validation, and integrated pre-build smoke testing into `.github/workflows/ci.yml` and `.github/workflows/release.yml` prior to GHCR container registry publishing.
- **AI Review Feedback Dataset Exporter (`devops ai review export-feedback`)**: Added status-filtered JSONL dataset export (`--status INVALIDATED|VERIFIED|MITIGATED|ALL`) with rich finding metadata for prompt calibration, DPO alignment, and model fine-tuning.
- **FastAPI Service Roadmap Integration**: Defined native async FastAPI REST and OpenAPI service engine (`devops serve`) in `docs/ROADMAP.md` for remote CLI execution, AI reviews, and webhook integrations.
- **Parallel Test Execution & Worker Optimization**: Configured `--maxprocesses=4` for pytest-xdist in `pyproject.toml` and `devops ci`, reducing test suite execution time by ~4x.

### Security & Hardening
- **Path Traversal & Boundary Protection**: Enforced path containment checks across AI cache metadata (`cache.py`), outline timestamps (`outlines.py`), symlink tree walking (`repo.py`), and audit log destination paths (`audit.py`).
- **Data Confidentiality & Masking**: Redacted sensitive tokens, GitHub PATs, and PEM private keys in outline analysis and multi-agent scratchpad reasoning context.
- **SSH Key Permissions**: Implemented atomic creation of `.pub` files with restricted `0644` permissions and sanitized comment control characters.

### Changed
- **Codebase Modernization & Cleanup**: Streamlined developer and agent instruction documents (`AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`), simplified branch protection and PR merge guidelines, and cleaned documentation artifacts.

## [0.1.9] - 2026-08-18

### Added
- **OpenTofu CLI Integration (`devops tofu` / `devops tf`)**: Infrastructure-as-Code command suite automating OpenTofu initialization, planning, application, outputs, and state validation with dual `tofu`/`terraform` binary discovery.
- **Multi-Cloud Cloud Resource Modules (`tf/`)**: Production OpenTofu manifests for provisioning Kubernetes clusters and networking across AWS (EKS), Azure (AKS), and Google Cloud (GKE) tailored for deployment of project `k8s/` resources.
- **Reusable Dev Container Package Publication (GHCR)**: Integrated automated Docker Dev Container image build and publication to GitHub Container Registry (`ghcr.io/dan-petty/devops-cli/devcontainer:<version>`) on release.
- **FastMCP OpenTofu Tools & Agent Bridge**: Exposed `tf_plan`, `tf_apply`, and `tf_output` (with `tofu_*` aliases) over Model Context Protocol and bridged tools for autonomous agent execution.
- **AI Prompt Optimization & Token Density Reduction**: Optimized task directives (`review.md`, `verify_finding.md`, `chat.md`, `compose.md`, `metadata.md`) and persona domain prompts, reducing prompt overhead by ~30% while preserving strict schema invariants.
- **Roadmap & Open-Source Tooling Refresh (`docs/ROADMAP.md`)**: Chronologically ordered all release milestones and defined integrations for OpenTelemetry, Prometheus, PydanticAI, Sigstore Cosign, Semgrep, Infracost, and FastAPI.

### Changed
- **Canonical Command References**: Standardized all legacy `devops review` documentation, tests, and configuration references to `devops ai review`.
- **Python 3 Exception Tuple Invariants**: Refactored multi-exception handling to parenthesized tuples `except (Err1, Err2):` across all codebase modules.
- **Pydantic Mutable Defaults**: Enforced `Field(default_factory=...)` on all Pydantic model mutable collection defaults.

### Governance
- **Agent Branch Isolation Guidelines**: Added strict rules forbidding commits to merged or unrelated branches in `AGENTS.md`, `CONTRIBUTING.md`, and `RELEASE_CYCLE.md`.

## [0.1.8] - 2026-08-17

### Added
- **Automated Release Cycle Suite (`devops release`)**: Native release management commands (`status`, `prepare`, `check`, `notes`, `tag`) automating semver bumping, changelog entries, docs synchronization, and pre-release verification.
- **FastMCP Release Tools**: Added `release_status` MCP tool allowing autonomous AI agents to query version consistency, git tags, and documentation freshness over Model Context Protocol.
- **Automated Documentation Engine (`devops docs`)**: Dynamic CLI and FastMCP introspection engine generating markdown manuals (`CLI_REFERENCE.md`, `MCP_TOOLS.md`, `ENV_VARS.md`) and synchronizing the `README.md` Command Matrix.
- **System Architecture & SRE Governance**: Enterprise system blueprints (`ARCHITECTURE.md`), open-source governance (`LICENSE`, `CONTRIBUTING.md`), defense-in-depth threat model (`SECURITY.md`), and GitHub Actions CI/CD quality gates (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- **Configuration & Constant Centralization**: Unified all static paths, timeouts, regex patterns, and user-facing messages in `config/constants.py`, `config/defaults.py`, and `lang/en.py`.

## [0.1.7] - 2026-08-17

### Added
- **Native DevContainer Lifecycle Engine (`devops devcontainer run-lifecycle`)**: Implemented type-safe, cross-platform Python lifecycle hooks (`--post-create`, `--post-start`, `--all`) replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Enhanced AI Reasoning Scratchpad (`ScratchpadBuffer`)**: Multi-turn reasoning scratchpad context preserving intermediate chain-of-thought, persona notes, and verification hypotheses across multi-agent review stages.
- **Prompt Token & Latency Optimization**: Compact JSON serialization (`separators=(",", ":")`), structured prompt context formatting, and reduced prompt token overhead across local Ollama and remote LLM providers.
- **Robust Worker Error Recovery**: Exception resilience in multi-agent review workers and top-level workspace `.data` directory persistence for all review sessions and metadata.
- **Dry-Run State Isolation**: Added automated test lifecycle fixture resetting dry-run state across test worker processes.

## [0.1.6] - 2026-08-12

### Added
- **SecOps Static Vulnerability Engine (`devops scan`)**: Aqua Trivy integration for vulnerability, secret, and IaC scanning with automated finding injection into `devsecops` persona reviews.
- **Kubernetes Manifest Auditor (`devops k8s lint`)**: Red Hat Kube-linter static analysis for Kubernetes manifests and Helm chart security best practices.
- **Popeye Cluster Health Sanitizer (`devops k8s audit`)**: Active Minikube and Kubernetes cluster scanning for resource limits, probe configurations, and cluster anomalies.
- **Pluto Deprecated API Scanner (`devops k8s check-deprecated`)**: Fairwinds Pluto static scanner detecting deprecated and removed Kubernetes API versions.

## [0.1.5] - 2026-08-12

### Added
- **Minikube Endpoint Auto-Detection (`devops k8s configure-urls`)**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `config.yaml`.
- **Validation Pipeline Integration**: Automated quality gate enforcing sequential checks (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- **Active Model Display**: Explicit model backend and provider visibility for all AI review file requests.

## [0.1.4] - 2026-08-12

### Added
- **Default AI Metadata Analysis (`devops ai analyze`)**: Made `--enhanced` mode the default execution behavior across all analysis commands (`path`, `branch`, `pr`), generating 6-10 line minimalist pseudocode outlines, complexity scoring, and ISO timestamps (`last_analyzed`).
- **Incremental Analysis Caching**: Intelligent skipping of unchanged files based on `st_mtime` vs `last_analyzed` timestamps, with `--update-all` (`-u`) flag to force full metadata regeneration.
- **Submodule-Aware Dependency Scanner**: Preserved full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`) in Python AST and package analysis.
- **Clean Pseudocode Generation**: Eliminated generic boilerplate language and strictly excluded import statements and package directives from pseudocode output to ensure clean separation from extracted dependencies.
- **Code Dry-Run & Core Helper Refactoring**: Added `render_dry_run_result()` in `dry_run/state.py`, `get_repo_origin_name()` in `core/repo.py`, and `get_llm_client()` in `config/settings.py`.

## [0.1.3] - 2026-08-11

### Added
- **Interactive Patch Staging (`devops ai review apply-patch --interactive`)**: Interactive unified diff rendering and confirmation before applying suggested LLM fixes.
- **Air-Gapped Ollama Model Bundler (`devops ai bundle-models`)**: Export and package local Ollama model weight manifests for air-gapped DevContainer environments.
- **Kubernetes RBAC Audit Policy Scanner (`devops k8s rbac-audit`)**: Security audit scanner evaluating RoleBindings and ServiceAccount privileges across namespaces.
- **SIEM Live Audit Streamer (`devops config audit-stream`)**: Streaming structured JSON audit trail records to Syslog or HTTP collectors.

## [0.1.2] - 2026-08-11

### Added
- **Multi-Cluster Kubeconfig Management (`devops k8s switch-context`)**: Added context switching and cluster namespace controls.
- **SIEM Audit Trail Logger (`devops_cli.core.audit`)**: Structured JSON audit trail logging (`AuditLogger`) streaming execution events to `.data/logs/audit.jsonl` or `DEVOPS_CLI_AUDIT_LOG_DEST`.
- **Automated Fix Patch Application (`devops ai review apply-patch`)**: Interactively staging suggested LLM code fixes (`finding.fix`) to target workspace source files.
- **Subcommand Dry-Run Pydantic Expansion**: Standardized `CommandDryRunResult` Pydantic models across `argo`, `grafana`, `prometheus`, `devcontainer` subcommands.

## [0.1.1] - 2026-08-11

### Added
- **Human Invalidation Feedback Exporter (`devops ai review export-feedback`)**: Export invalidated review findings (`status == "INVALIDATED"`) into JSONL benchmark datasets for prompt tuning.
- **Repository-Level Custom Team Personas (`.devops/personas/<name>.md`)**: Dynamic loading of custom reviewer persona prompts defined in `.devops/personas/` under target repositories.
- **Headless CI Ephemeral Auth (`devops config auth-headless`)**: Memory secret storage fallback for DBus-less headless Linux CI environments.
- **Line-Level GitHub PR Inline Comments (`create_pr_review_comment`)**: Line-level inline comment posting capabilities in `GitHubClient`.
- **v0.1.1 Feature Flag Configuration**: Added `FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, and `FEATURE_HEADLESS_AUTH` canonical option constants.

## [0.1.0] - 2026-08-11

### Added
- **Codebase Metadata Analysis (`devops ai analyze`)**: Subcommand generating structured `.data/analysis/<type>-<sanitized-ref>-metadata.json` files containing project structure, dependency graphs, key symbols, and file type classification.
- **Pydantic Model Dry-Run Responses**: All subcommands in `--dry-run` mode (`review`, `analyze`, `k8s`, `docker`, `repos`, `ssh`) construct and output structured Pydantic model JSON representations (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- **`dry_run` Submodule Package (`devops_cli.dry_run`)**: Modular package structure (`state.py`, `models.py`, `__init__.py`) providing environment-backed dry-run state tracking and response schemas.
- **Package Security Audit (`devops ci audit`)**: Added `uv audit` command and integrated dependency vulnerability scans into the standard `devops ci` quality gate pipeline.
- **`UV_MALWARE_CHECK=1` Integration**: Enabled malware scanning for `uv` package operations in `.devcontainer/devcontainer.json` and `.devcontainer/postCreate.sh`.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code with `VERIFIED`, `UNVERIFIED`, and `MITIGATED` status tracking.

### Changed
- **Python 3.14 Compatibility**: Standardized all exception handling clauses to parenthesized tuples `except (Err1, Err2):`.
- **Target-Agnostic Heuristics**: Refactored AI reviewer persona prompts, static analysis heuristics, and review task templates to evaluate target repositories based on their own documented conventions rather than `devops-cli` specific paths.
- **Literal Centralization**: Centralized user-facing messages, command outputs, error responses, and configuration constants in `src/devops_cli/lang/en.py` (`LanguageCatalog`) and `src/devops_cli/config/constants.py`.

### Security & Hardening
- **Path Traversal & Injection Protections**: Enforced workspace boundary checks (`_is_safe_workspace_path`, `_resolve_from_project_root`) and input sanitization against argument injection (`-` prefix validation).
- **OS Keyring Isolation**: Sensitive tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) stored exclusively in OS keyring via `keyring`.
