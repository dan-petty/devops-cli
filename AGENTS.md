# AGENTS.md — AI Agent Instructions & Engineering Best Practices

This document provides foundational context, architectural principles, and operational best practices for AI coding assistants (GitHub Copilot, Claude, Cursor, Codex) working on this codebase or reviewing target repositories.

> **Canonical Source**: This file is the single source of truth for AI agent instructions. [CLAUDE.md](./CLAUDE.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers to this file.

---

## 1. Core Engineering Philosophy & Objectives

- **High Reliability & Quality First**: Build robust, resilient workstation automation and developer tooling with defensive error handling, bounded timeouts, and zero tolerance for flaky tests.
- **Poetic Conciseness, Expressive Integration & Zero Boilerplate**:
  - The codebase must read as an expressive, poetically concise integration of tools, libraries, docs, AI, and automation rather than a sprawl of procedural loops or boilerplate.
  - **Strict Complexity & Nesting Caps**: Strictly enforce cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ (< 6 indentation levels) project-wide across all functions, closures, and blocks. Continuous compliance is validated by `devops scan complexity` and automated architectural invariant gates ([`tests/test_architectural_invariants.py`](tests/test_architectural_invariants.py)).
  - Decompose multi-step tasks, deep branching, and nested iterations into dedicated single-responsibility helper functions, pure predicate helpers, and functional pipelines.
  - Replace procedural dispatchers and `if/elif` ladders with dictionary mappings, registry lookups, or table-driven dispatch.
  - Maximize standard library leverage (`functools`, `itertools`, `pathlib`, `collections`, `ipaddress`, `urllib.parse`), Pydantic v2 models, and functional pipelines.
- **Modern Python Ecosystem**: Track Python 3.14+ runtime features, typing standards, and established libraries (`pydantic v2`, `httpx2`, `pytest`, `ruff`, `mypy`, `uv.lock`). Avoid custom workarounds when standard library or established open-source tools exist. Never hallucinate CVEs or false malicious alerts against verified dependencies like `httpx2`.
- **Zero-Trust Security & Egress Safety**:
  - Never store plaintext secrets or tokens in code, configuration files, or logs. Always use OS Keyring or secure secret stores.
  - **Zero Information Leakage**: Never leak, extract, or expose confidential, private, hidden, or `.gitignored` files (`.env*`, `.ssh/`, `.data/`, `~/.gemini/`, credentials, private keys) into any documents, changelogs, review findings, public commits, or code artifacts.
  - Redact, mask, or generalize sensitive local paths, environments, or user identifiers in documentation, prompt contexts, or code examples.
  - Mitigate Server-Side Request Forgery (SSRF) and network egress risks by validating destination endpoints.
  - Enforce subprocess safety with explicit command argument lists, bounded timeouts, and error handling.
- **Never Lower Security Standards or Quality Thresholds**: Never lower, relax, disable, bypass, or weaken security standards, quality thresholds (such as minimum 90% code coverage, strict static type checks, or lint rules), or compliance validations unless explicitly instructed by the user.
- **Continuous Standards Compliance & Solution Refinement**: Ensure every proposed solution, design, code change, or architecture meets all project standards and conventions, iteratively refining until every standard is met or exceeded.
- **Clean Solutions Over Legacy Remnants (Zero Zombie Code)**: When modifying, refactoring, or replacing features, schemas, configurations, or interfaces, implement clean, complete solutions and ruthlessly remove obsolete code, variables, aliases, fallback shims, and legacy workarounds. Never leave remnants or vestigial fallback paths.
- **Dedicated Agent Workspace Data Isolation**: The workspace data directory is configured via `DEVOPS_CLI_DATA_DIR` (or configuration key `data.dir`, defaulting to `./.data`). AI agents executing CLI review sessions, background benchmarks, analysis scans, test executions, or temporary operational tasks must isolate agent work products (reviews, logs, traces, metadata) under the dedicated `agent/` subfolder (`<data_dir>/agent`, e.g. `./.data/agent`) to keep agent artifacts separate from the user workspace data tier.
- **Mandatory Backup for Files Outside Workspace**: Whenever modifying, overwriting, editing, or truncating any file located outside the project workspace directory (e.g. `~/.ssh/`, `~/.bashrc`, `~/.zshrc`, `/etc/`), AI agents **MUST ALWAYS** create a timestamped backup named `<original-filepath>.bak-<YYYYMMDD-HHMMSS>` prior to making edits.

---

## 2. Development Workflow & Progressive Verification

All work follows a test-first progressive verification strategy to optimize developer feedback loops while guaranteeing release readiness:

### Test-First Development Cycle (TDD as Living Contract)
1. **Define Specification via Tests First**: Before writing or changing implementation code in `src/`, author comprehensive unit and integration tests in `tests/test_<feature>.py` defining intended behavior, arguments, return structures, edge cases, and exception handling. Tests serve as the authoritative, executable specification.
2. **Implement Feature Logic**: Write clean, concise implementation code in `src/` to satisfy the tests.
3. **Verify Locally**: Run targeted tests (`uv run pytest tests/test_<feature>.py`) for immediate feedback during development.
4. **Comprehensive Quality Gate**: Execute `devops ci` (or `uv run devops ci`) to validate all gates and enforce the minimum 90% code coverage requirement across `src/`.

### Project Planning & Task Tracking
- **Mandatory Planning Artifacts**: Document project planning and technical implementation designs in dedicated planning documents (`implementation_plan.md`, `docs/agent/task.md`, `docs/ROADMAP.md`, `docs/PENDING_FEATURES.md`, `docs/LOG.md`) prior to executing complex, multi-step, or architectural changes.
- **Continuous Task Status Tracking (`docs/agent/task.md`)**: Maintain and track transparent task statuses across three unambiguous categories in real time:
  - **Pending Tasks**: Queued deliverables, backlog requirements, and upcoming milestones awaiting execution.
  - **In-Progress Tasks (WIP)**: Active focus items, specific files under modification, and ongoing test specifications.
  - **Completed Tasks**: Verified implementations, green test gates, synchronized documentation, and closed operational loops.
- **GitHub Projects v2 & Issue Alignment**: Ground all task lifecycles, issue tracking, and sprint planning in GitHub Projects v2 (`.github/project-template.json`) and roadmap milestones (`docs/ROADMAP.md`), continuously reconciling state transitions (`Backlog` $\to$ `Ready` $\to$ `In Progress` $\to$ `In Review` $\to$ `Done`) and auditing issue/PR taxonomies.

### Knowledge Base Consultation
Before planning, implementing, debugging, refactoring, or reviewing code, consult the **DevOps CLI Knowledge Base** under [`src/devops_cli/ai/knowledge_base/README.md`](src/devops_cli/ai/knowledge_base/README.md):
- **DevOps CLI Internals ([`devops_cli/`](src/devops_cli/ai/knowledge_base/devops_cli/))**: Architecture, configuration, keyring management, CLI matrix, and 13 operational task manuals (`devops_cli/tasks/`).
- **IT Domain Guides ([`it_domains/`](src/devops_cli/ai/knowledge_base/it_domains/))**: 10 IT domain topic guides (`it_domains/topics/`) and 20 integrated tool manuals (`it_domains/tools/`).

### Verification Strategy & Routine Tasks Execution
- **Mandatory Routine Tasks Execution**: Check and execute applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) in sequence and cadence.
- **Primary CI Verification Gate**: Run `devops ci` (or `uv run devops ci`) to comprehensively validate all 10 gates. Do not run redundant standalone tools that are already aggregated by `devops ci`.
- **Mandatory Iterative CI Loop**: Make planned code changes, run `devops ci`, fix reported issues, and run `devops ci` again iteratively until all quality gates pass cleanly.
- **Mandatory Documentation Synchronization**: Update documentation, command matrix, and README (`devops docs generate --sync-readme`, `docs/`, `AGENTS.md`) after every change to prevent documentation drift.

### Build, Lint & Test Commands
| Operation | Command | Purpose |
| :--- | :--- | :--- |
| **Dependency Sync** | `uv sync` | Synchronize virtual environment with lockfile. |
| **Full CI Suite (Primary Gate)** | `devops ci` / `uv run devops ci` | Comprehensive quality gate (version, test, coverage $\ge 90\%$, lint, format, typecheck, audit, security, actionlint, docs). |
| **Targeted Test** | `uv run pytest tests/test_<feature>.py` | Fast, isolated unit test execution for debugging. |
| **Targeted Lint** | `uv run ruff check path/to/file.py` | Fast lint inspection on modified files. |
| **Targeted Typecheck** | `uv run mypy path/to/file.py` | Strict static type validation on modified modules. |
| **Documentation Sync** | `devops docs generate --sync-readme` | Introspect CLI and synchronize markdown references and README. |

---

## 3. Git Hygiene, Release Governance & GitHub Integration

- **Branch Hierarchy & Isolation**:
  - **Zero Direct Commits to `main`**: All work must be conducted on dedicated topic branches (`feat/<description>`, `fix/<description>`, `docs/<description>`, `refactor/<description>`).
  - **PR Base Branch Targeting**: Feature, fix, and refactoring PRs must target the active release branch (`--base release/v<version>`). Release branches target `main` when cutting an official release.
  - **Branch Freshness**: Always branch off fresh upstream tracking branches (`git fetch origin`).
- **Commit Standards**:
  - Follow **Conventional Commits** (`feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, `docs(scope): ...`).
  - **Atomic Commits by Default**: Break multi-faceted work into small, logically self-contained commits with precise messages.
- **Pull Request Governance & Title Conventions**:
  - **Conventional Commit PR Titles**: PR titles MUST follow Conventional Commits (`feat(scope): description`) for clean squash-merging onto `main`.
  - **GitHub Release Titles**: Strictly the version tag / number from `pyproject.toml` (e.g. `v0.2.11`) without conventional commit prefixes.
  - **Human-in-the-Loop Merging**: AI agents prepare clean commits, open/update PRs, monitor remote CI checks (`gh pr checks`), and leave merge approval to maintainers. Never merge autonomously.
  - **Active CI Monitoring & Remediation**: Actively monitor remote GitHub Actions status. If any check fails, inspect logs, diagnose root causes, push corrective commits, and verify green status.
- **GitHub Projects, Issues, Views, Milestones & Label Governance (Project Management Integration)**:
  - **Issue Tracking, Triage & PR Linkage**:
    - Track all engineering issues, bug reports, feature requests, and technical chores using standardized issue templates (`.github/ISSUE_TEMPLATE/`: `bug_report.yml`, `feature_request.yml`, `security_advisory.yml`, `task.yml`).
    - Every PR addressing an issue MUST explicitly link to it using canonical GitHub closing keywords in the PR body (`Fixes #<issue>`, `Closes #<issue>`, `Resolves #<issue>`).
    - Enforce declarative taxonomy labels on all issues matching `.github/labels.yml` across `type/*`, `scope/*`, `priority/*`, and `status/*`.
    - Prioritize incoming defects and blockers using the standardized *Triage & Quality Table* view (`type/bug`, `status/blocked`, `status/triage`) ordered by `Priority` (`P0-Critical` through `P3-Low`).
  - **Mandatory PR Taxonomy Labels**: Every PR MUST possess at least one `type/*` label and at least one `scope/*` label. Validate compliance with `devops gh labels audit`.
  - **Roadmap-Driven Milestone Linking**: Every issue and PR targeting a release branch MUST link to the active release milestone in [`docs/ROADMAP.md`](docs/ROADMAP.md). Synchronize via `devops gh milestones sync` and inspect progress via `devops gh milestones status <version>`.
  - **GitHub Projects v2 Lifecycle & Views Integration**:
    - Track tasks according to the 4 standardized views in `.github/project-template.json` (*Sprint Kanban*, *Roadmap Timeline*, *Triage & Quality Table*, *Value vs Effort Priority Matrix*).
    - Manage state transitions strictly (`Backlog` $\to$ `Ready` $\to$ `In Progress` $\to$ `In Review` $\to$ `Done`) across issues and tasks in [`docs/agent/task.md`](docs/agent/task.md):
      - `Backlog`: Queued items awaiting milestone assignment or scheduling.
      - `Ready`: Scoped items ready for immediate development.
      - `In Progress`: Active work items currently being authored/edited (mirrored in `docs/agent/task.md` under `### In-Progress Tasks (WIP)`).
      - `In Review`: Pull Request opened with CI checks running and code reviews in progress.
      - `Done`: Pull Request squash-merged by maintainer into release branch, remote CI verified, and issue closed.
    - Populate and maintain custom project fields: `Status`, `Milestone`, `Priority`, `Category`, `Value`, `Effort`.
    - Validate alignment via `devops gh project sync --dry-run`, `devops gh project status`, and `devops gh views list`.
    - Never invent ad-hoc status tags or unregistered labels outside `.github/labels.yml` and `.github/project-template.json`.
  - **FastMCP Agent Project Management Integration**: AI coding assistants MUST leverage the built-in FastMCP project management tools (`gh_project_status`, `gh_view_spec`, `gh_milestone_list`, `gh_milestone_sync`, `gh_label_list`, `gh_label_sync`) and CLI equivalents (`devops gh project`, `devops gh views`, `devops gh milestones`, `devops gh labels`) for all project tracking, milestone inspection, and taxonomy auditing.

---

## 4. Code Quality & Architectural Standards

- **Separation of Concerns**: Separate configuration, domain logic, data models, network I/O, and user interface layers. Avoid monolithic modules and deep indentation.
- **Purpose-Driven, Functional Naming**: Use file names, classes, functions, and variables that directly indicate concrete operational purpose (e.g. `reference_extractor.py`, `vulnerability_lookup.py` over abstract names like `common.py`, `helpers.py`, `data.py`).
- **Config & Defaults Separation**: Distinguish immutable invariant constants (system paths, protocol regexes) from configurable defaults (timeouts, model names, retry limits).
- **Strict Typing & Modern Idioms**: Enforce complete type annotations (`mypy --strict`), Python 3.14+ union syntax (`A | B`), standard collections (`list`, `dict`, `set`), and Pydantic v2 models with `Field(default_factory=...)`.
- **Deterministic Test Isolation**: Isolate external dependencies (network, LLM providers, subprocesses) using mocks (`unittest.mock`, `pytest-mock`). Never hardcode real credentials or live endpoints in test suites.
- **Standard Parsers Over Brittle Literal Collections**:
  - Never rely on partial iterable collections of string literals, ad-hoc lists of file extensions, or fragile regex substrings for domain logic, syntax analysis, or security filtering.
  - Always use established language-agnostic code quality standards, standard library parsers (`ast`, `tokenize`, `json`, `tomllib`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, `functools.lru_cache`), official specifications (Public Suffix List via `tldextract`, PEP 508 `packaging.requirements`), dynamic filesystem queries (`Path.iterdir()`), and syntactic analysis.
  - Maintain target-agnostic and language-agnostic designs resilient across any software ecosystem (Python, Go, Rust, TypeScript, Java, C#, HCL, Kubernetes, Docker).
- **Pure Markdown Prompt Tasks & Zero Inline LLM Prompts**: All LLM system prompts, task instructions, guardrails, evaluation rubrics, and benchmark prompts MUST reside in dedicated Markdown files (`.md`) under `src/devops_cli/ai/` loaded exclusively via `load_task_prompt()`. Multi-line prompt strings inline in Python code are strictly prohibited.
- **Canonical Location Formatting**: All terminal outputs, Rich tables, Markdown reports, findings, and audit records must use the canonical `filename.ext:n-n` or `filename.ext:line` location convention for consistent parsing and IDE navigation.
- **Zero Hardcoded Scoring or Synthetic Confidence Values**: Never hardcode arbitrary numerical scores, confidence weights, synthetic thresholds, or default scoring floats. All scoring and confidence assessments MUST originate directly from external tools providing native ratings or structured AI model responses; otherwise fields must remain `None` (or 0.0 where non-nullable).
- **Modular Stage Pipeline Architecture**: Partition complex multi-step pipelines into dedicated, single-responsibility stage modules under a `stages/` subpackage, decorated with `@trace_span`.
- **Provider Protocol & Deterministic Mock Isolation**: Implement abstract provider protocols under `providers/` (e.g. `BaseLLMProvider`) and supply deterministic mock implementations for offline testing.
- **Standardized Domain Exception Taxonomy**: All domain error states must raise strongly typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`, specifying explicit POSIX exit codes, canonical machine-readable error codes (`CONST_ERROR_CODE_*`), and structured context dictionaries. Raising bare Python built-in exceptions (`ValueError`, `RuntimeError`, `TypeError`) in domain logic is strictly prohibited.
- **Clean Test Collection Hygiene**: Test helper classes and dummy test models in `src/devops_cli` must declare `__test__ = False` to prevent `PytestCollectionWarning`. Safely await or close coroutine returns.
- **Telemetry & Metrics by Default**: Instrument new subcommands, background tasks, and AI pipeline stages with OpenTelemetry distributed spans (`@trace_span`) and record metrics via `GLOBAL_METRICS`.

---

## 5. Agentic AI & Review System Guidelines

- **Multi-Persona Code Review**: Utilize distinct domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) to analyze diffs and provide actionable, high-signal feedback.
- **Knowledge Base & RAG Grounding**: Ground findings against repository knowledge bases (`src/devops_cli/ai/knowledge_base/` or target project docs) to avoid hallucinatory or generic recommendations.
- **Target-Agnostic Code Analysis & Path Isolation**: Evaluate target projects against universal software engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and target project conventions (`AGENTS.md`, `README.md`). Resolve all file reading, AST analysis, and security scanning relative to the target root directory (`target_dir`).
- **Context-Aware Documentation, Examples & Test Evaluation**:
  - Never flag documentation, architectural guides, security tutorials, knowledge base articles, prompt benchmarks, test assertions/fixtures, test mocks, template/sample configuration files (`*.example.*`, `*.sample.*`, `*.tfvars.example`, `*.env.example`), or explanatory comments that describe known vulnerabilities or configurations in the context of avoiding, explaining, or mitigating them.
  - Standard Infrastructure-as-Code operator outputs (`outputs.tf` generating local commands like `aws eks update-kubeconfig`) must not be flagged as remote command injection.
- **Zero Hallucinated CVEs & Synthetic IDs**: Never synthesize or invent fictitious CVE numbers. All CVE citations must originate from verified security scanner outputs (`scan_trivy`, `scan_uv_audit`, OSV, NVD) or public databases.
- **Workstation vs Production Infrastructure Context**: Distinguish local workstation/Minikube developer manifests (`host.minikube.internal`, local git daemons, NodePort services, `IfNotPresent` pull policy) from production cloud deployments, providing constructive dual-mode guidance.
- **Multi-Namespace Root Kustomizations**: Never flag missing namespace declarations on root or umbrella kustomization files (`k8s/kustomization.yaml`) that aggregate multiple child namespace component directories (`argocd/`, `llm/`, `monitoring/`, `otel/`).
- **Closed-Loop Review & Self-Improvement Cycle**:
  - **Deduplication & Calibration**: Calibrate confidence scores and test explicit verification/invalidation criteria to eliminate phantom alerts.
  - **Information Exposure Sanitization (CWE-200)**: Exception messages, CLI error output, and logs must sanitize private IPs, internal hostnames, and credentials, preserving raw targets strictly inside structured debug details dictionaries.
  - **Self-Healing Drop-In Fixes**: Review findings must provide drop-in remediations verifiable by unit tests and automated CI gates.
  - **Feedback Dataset Export**: Export verified and invalidated review findings to structured datasets (`devops review export-feedback`) to continuously ground RAG retrieval and refine LLM prompts.
