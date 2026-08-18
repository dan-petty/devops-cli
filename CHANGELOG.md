# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.12] - 2026-08-18

### Added
- **Remote CI Inspection & Monitoring (`devops ci remote status|logs|watch`)**: Terminal-based monitoring and failure log introspection for GitHub Actions workflow runs and check suites.
- **GitHub Pull Request Governance (`devops pr list|view|checks|edit|create`)**: Comprehensive PR workflow management enforcing branch hierarchy and active release branch targeting (`release/vX.Y.Z`).
- **Standardized Branch & Repo Lifecycle (`devops branches create|status`, `devops repos exec`)**: Standardized topic branch creation with release base discovery, workspace drift inspection, and multi-repo batch command execution across `repos/`.
- **FastMCP SDLC & Release Automation Tools**: 10 new Model Context Protocol tools exposing remote CI checks, PR operations, branch workflows, repo execution, and release note extraction to AI agents.
- **Minikube LLM & GPU Host Bridge (`k8s/llm/ollama-host-service.yaml`)**: Kubernetes Service and Endpoints bridge routing in-cluster LLM traffic directly to the host DevContainer NVIDIA CUDA GPU runtime for full hardware acceleration.

### Changed
- **Version Centralization & Review Configuration**: Upgraded package release version to `0.1.12` and centralized `DEFAULT_REVIEW_CONTEXT_LINES` in configuration defaults.

## [0.1.11] - 2026-08-18

### Added
- **Git & GitHub Project Best Practice Guardrails (`AGENTS.md`, `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`)**: Comprehensive AI agent and developer operational guardrails for branch hierarchy (zero direct commits to `main`, base branch targeting `release/vX.Y.Z`, fresh topic branches), commit hygiene (Conventional Commits, atomicity, pre-commit validation, zero leaked secrets), PR governance (no autonomous merging by agents, in-place topic branch updates, active CI monitoring, and issue linking), and targeted unit testing during iterative feature development before full final-stage test runs.
- **Published Dev Container User Guide & CLI Scaffolding (`docs/DEVCONTAINER_USAGE.md`)**: Comprehensive user guide for consuming the published multi-tool GHCR DevContainer image (`ghcr.io/dan-petty/devops-cli/devcontainer:latest`) across VS Code, Cursor, and GitHub Codespaces, along with `--published` (`-p`) and `--image` (`-i`) flag support in `devops devcontainer init`.
- **Automated DevContainer Pre-Commit Installation**: Integrated automated `uv run pre-commit install` into the container startup lifecycle hook (`devops devcontainer run-lifecycle --post-start`) and added `.gitattributes` to enforce consistent LF line endings.

### Changed
- **Enhanced Finding Verification & Continuous Self-Improvement Loop**: Calibrated finding verification directives (`verify_finding.md`, `verification.py`, `devsecops/prompt.md`) to strictly reject speculative assumptions without visible code flaws, preserve structured invalidation reasons and confidence scores into `findings.json`, and streamline feedback dataset export (`devops ai review export-feedback`) for prompt calibration.
- **Single Source of Truth Project Metadata Architecture**: Centralized metadata loading in `src/devops_cli/config/metadata.py` dynamically reading package version, description, and Python requirements directly from `pyproject.toml` and standard package distribution metadata (`importlib.metadata`), eliminating hardcoded version and configuration duplication across commands and defaults.
- **AI / LLM Prompt & Token Density Optimization**: Optimized persona domain prompts (`devsecops`, `architect`, `auditor`, `pm`, `qa`) and core review task prompts (`review.md`, `analyze_pseudocode.md`, `verify_finding.md`, `compose.md`, `metadata.md`, `chat.md`), eliminating cross-prompt rule duplication and reducing prompt token consumption.
- **CI Workflow Optimization & Duplicate PR Check Elimination**: Refactored `.github/workflows/ci.yml` to restrict `push` triggers strictly to `main` while maintaining `pull_request` triggers on `main` and `release/**`, eliminating duplicate CI runs on pull requests, and added workflow concurrency management to cancel superseded in-flight builds.
- **Evergreen Validation Nomenclature**: Standardized validation terminology across GitHub Actions workflows, CLI tooling, and documentation from numbered gates to evergreen `validate` / `Validation`.

### Fixed
- **DevContainer Manifest Path Traversal Guard & Input Validation**: Added workspace containment checks in `devops devcontainer validate` preventing traversal outside the repository and enforced semantic version validation on `--python` in `devops devcontainer init`.
- **Kubernetes Stack Hardening & Namespace Isolation**: Added explicit `namespace: argocd` in `k8s/argocd/kustomization.yaml`, hardened Valkey deployment with non-root `securityContext` (`runAsNonRoot: true`, capabilities drop), switched in-cluster cache service to `ClusterIP`, and pinned immutable image tag (`v0.5.11`) in `k8s/llm/values-open-webui.yaml`.
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
