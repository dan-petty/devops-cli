# AGENTS.md — AI Agent Instructions & Engineering Best Practices

This document provides foundational context, architectural principles, and operational best practices for AI coding assistants (GitHub Copilot, Claude, Cursor, Codex) working on this codebase or reviewing target repositories.

## 1. Core Engineering Philosophy & Objectives

- **High Reliability & Quality First**: Build robust, resilient workstation automation and agentic developer tooling with defensive error handling, explicit timeouts, and zero tolerance for flaky tests.
- **Poetic Conciseness, Expressive Integration & Zero Boilerplate**:
  - The codebase must read as a poetically concise, expressive integration of tools, libraries, docs, AI, and automation rather than a collection of low-level nested loops, procedural boilerplate, or hard-to-decipher ad-hoc logic.
  - **Strict Complexity & Nesting Caps**:
    - Aim for cyclomatic complexity $\le 10$ and fewer than 6 indentation levels across all functions and code blocks.
    - Proactively decompose complex multi-step tasks, deep branching, and nested iterations into dedicated single-responsibility helper functions and functional pipelines.
    - Replace giant `if/elif` ladders and procedural dispatchers with dictionary mappings, registry lookups, or table-driven dispatch.
    - Extract nested AST node inspection, file traversal guards, and multi-condition filtering into pure predicate helpers.
  - Maximize standard library leverage (`functools`, `itertools`, `pathlib`, `collections`, `ipaddress`, `urllib.parse`), Pydantic v2 models, and functional pipelines.
  - Never write manual string-slicing loops, hand-rolled dictionary traversing, or procedural subprocess parsing when standard library parsers, comprehensions, or high-level declarative abstractions provide clean, self-documenting implementations.
- **Modern Python Ecosystem**: Track modern Python 3.14+ runtime features, typing standards, and established open-source libraries (`pydantic v2`, `httpx2`, `pytest`, `ruff`, `mypy`, `uv.lock`). Avoid custom workarounds when standard library or robust open-source tools exist. Ensure AI code reviewers do not hallucinate CVEs or false malicious package alerts against verified dependencies like `httpx2` (Pydantic HTTP/2 client).
- **Zero-Trust Security & Egress Safety**:
  - Never store plaintext secrets or tokens in code, configuration files, or logs. Always use OS Keyring or secure secret stores.
  - Never leak, extract, or expose information from hidden, private, or `.gitignored` files (`.env*`, `.ssh/`, `.data/`, local credentials, private keys) into any documents, changelogs, review findings, public commits, or code artifacts.
  - When constructing documentation, reviews, prompt context, or code examples, always redact, mask, or generalize any sensitive local environments, file system trees, or user identifiers.
  - Mitigate Server-Side Request Forgery (SSRF) and network egress risks by validating destination endpoints.
  - Enforce subprocess safety with explicit command argument lists, bounded timeouts, and error handling.
- **Never Lower Security Standards or Quality Thresholds**:
  - AI agents and assistants must never lower, relax, disable, bypass, or weaken security standards, quality thresholds (such as minimum code coverage requirements like 90%, strict static type checks, or lint rules), or compliance validations unless explicitly instructed to do so by the user.
- **Continuous Standards Compliance & Solution Refinement**:
  - AI agents and assistants must always check that any proposed solution, design, code change, or architecture meets all project standards and conventions (including modular organization, domain-driven naming, standard library composition, zero boilerplate, Pydantic v2 schemas, strict type annotations, canonical location formatting, and zero hardcoded metrics).
  - AI agents must update and refine the solution whenever necessary until every project standard is met or exceeded.
- **Clean Solutions Over Legacy Remnants (Zero-Tolerance for Zombie Code)**:
  - When modifying, refactoring, or replacing features, schemas, configurations, or interfaces, AI agents must implement clean, complete solutions and ruthlessly remove old, obsolete, or superseded code, variables, aliases, fallback shims, and legacy workarounds across the codebase.
  - Never leave remnants, vestigial aliases, deprecated fallback paths, or ghost implementations for backward compatibility unless explicitly requested to do so by the user.
- **Dedicated Agent Workspace Data Isolation (`DEVOPS_CLI_DATA_DIR=./.data/agent`)**:
  - AI agents executing CLI review sessions, background benchmarks, analysis scans, test executions, or temporary operational tasks must configure and isolate agent data artifacts under `./.data/agent` (via `DEVOPS_CLI_DATA_DIR=./.data/agent`) to separate agent-generated reviews, logs, traces, and metadata from the primary user workspace data tier.
- **Mandatory Backup for Files Outside Workspace (`.bak-<YYYYMMDD-HHMMSS>`)**:
  - Whenever modifying, overwriting, editing, or truncating any file located anywhere outside of the project workspace directory (such as files in user home directories, global configuration files, `~/.ssh/`, `~/.bashrc`, `~/.zshrc`, `/etc/`, or system files), AI agents and assistants **MUST ALWAYS** create a timestamped backup of the target file named `<original-filepath>.bak-<YYYYMMDD-HHMMSS>` (e.g. `~/.ssh/config.bak-20260831-134100`) prior to making any edits.
- **Mandatory Documentation Synchronization After Every Change**:
  - AI agents and assistants must always update project documents, architecture references, command documentation, examples, and README files (`devops docs generate --sync-readme`, `docs/`, `AGENTS.md`, and relevant knowledge base task manuals) after every change to maintain 100% documentation integrity and prevent documentation drift.

## 2. Development Workflow & Progressive Verification

All work follows a progressive verification strategy to optimize developer feedback loops while guaranteeing release readiness:

### Mandatory Knowledge Base Consultation
Before planning, implementing, debugging, refactoring, or reviewing code, architectures, or operational workflows, AI agents and assistants **MUST ALWAYS** consult the **DevOps CLI Knowledge Base** under [`src/devops_cli/ai/knowledge_base/README.md`](src/devops_cli/ai/knowledge_base/README.md).
- **DevOps CLI Information ([`src/devops_cli/ai/knowledge_base/devops_cli/`](src/devops_cli/ai/knowledge_base/README.md#-division-1-devops-cli-information-devops_cli))**: Consult for DevOps CLI internals, subsystem architecture, configuration & keyring management, CLI command matrix, and 12 operational task manuals (`devops_cli/tasks/`).
- **IT Domain-Specific Information ([`src/devops_cli/ai/knowledge_base/it_domains/`](src/devops_cli/ai/knowledge_base/README.md#-division-2-information-technology-domain-specific-information-it_domains))**: Consult for deep architectural patterns and standards across 10 IT domain topic guides (`it_domains/topics/`) and 20 integrated tool reference manuals (`it_domains/tools/`).

### Verification Strategy & CI Quality Gate
- **Primary CI Verification Gate**: AI agents must simply run `devops ci` (or `uv run devops ci`) to comprehensively validate changes. AI agents should not run any other tooling (such as standalone ruff, mypy, pytest, actionlint, bandit, trivy, pip-audit, or docs checks) that is already automatically executed and aggregated by `devops ci`. Enforces a strict minimum 90% code coverage requirement across `src/`.
- **Mandatory Iterative CI Loop**: AI agents must always make all planned code changes, run `devops ci`, fix all reported issues, and run `devops ci` again, iteratively fixing issues and running `devops ci` until all quality gates pass cleanly.

### Build, Lint & Test Commands
| Operation | Command | Purpose |
| :--- | :--- | :--- |
| **Dependency Sync** | `uv sync` | Synchronize virtual environment with lockfile. |
| **Full CI Suite (Primary Gate)** | `devops ci` / `uv run devops ci` | Comprehensive quality gate (version, test, coverage, lint, format, typecheck, audit, security, actionlint, docs). |
| **Targeted Test** | `uv run pytest tests/test_<feature>.py` | Fast, isolated unit test execution for debugging. |
| **Targeted Lint** | `uv run ruff check path/to/file.py` | Fast lint inspection on modified files. |
| **Targeted Typecheck** | `uv run mypy path/to/file.py` | Strict static type validation on modified modules. |
| **Documentation Sync** | `devops docs generate --sync-readme` | Introspect CLI and synchronize markdown references and README. |

## 3. Git Hygiene & Branch Management

- **Branch Hierarchy & Isolation**:
  - **Zero Direct Commits to `main`**: All work must be conducted on dedicated topic branches (`feat/<description>`, `fix/<description>`, `docs/<description>`, `refactor/<description>`, or `release/v<version>`).
  - **PR Base Branch Targeting**: Feature, fix, and refactoring PRs must target the active release branch (`--base release/v<version>`). Release branches target `main` when cutting an official release.
  - **Branch Freshness**: Always branch off fresh upstream tracking branches (`git fetch origin`).
- **Commit Standards**:
  - Follow **Conventional Commits** format (`feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, `docs(scope): ...`).
  - **Atomic Commits by Default**: AI agents must create atomic, cohesive commits whenever possible. Break multi-faceted work into small, logically self-contained commits (e.g., separating schema changes, implementation, tests, refactorings, or documentation) with precise conventional commit messages rather than bundling disparate changes into single massive commits.
  - Maintain clean commit messages with informative descriptions.
- **Pull Request Governance & Title Conventions**:
  - **Conventional Commit PR Titles**: All Pull Request titles MUST strictly follow the **Conventional Commits** format (`feat(scope): description`, `fix(scope): description`, `feat(release): v<version>`, `chore(release): v<version>`) so that when maintainers squash-merge PRs onto `main`, the resulting commit message on `main` conforms to conventional commits.
  - **GitHub Release Titles**: GitHub Release titles must strictly be the version tag / number from `pyproject.toml` (e.g. `v0.2.1` or `0.2.1`) without any conventional commit prefix.
  - **Human-in-the-Loop Merging**: AI agents must never merge PRs autonomously. Agents prepare clean commits, open/update PRs, monitor CI checks, and leave merge approval to maintainers.
  - **Active CI Monitoring & Remediation**: When opening or updating a PR, actively monitor remote GitHub Actions status (`gh pr checks <pr>` or `gh run list --branch <branch>`). If any check fails, inspect logs, diagnose root causes, push corrective commits, and verify green status.


## 4. Code Quality & Architectural Best Practices

- **Separation of Concerns & Indentation Limits**:
  - Separate configuration, domain logic, data models, network I/O, and user interface layers.
  - Avoid monolithic modules, procedural boilerplate, and overly complex, deeply nested code blocks (aim for fewer than 6 indentations project-wide; extract complex nested tasks into dedicated helper functions).
- **Purpose-Driven, Functional Naming & Structural Clarity**:
  - Always use file names, folder structures, classes, functions, and variable names that directly and unambiguously indicate the concrete purpose and function of the code they contain.
  - Avoid abstract, vague, or purely conceptual names (e.g. `intelligence.py`, `manager.py`, `misc.py`, `common.py`, `helpers.py`, `data.py`) in favor of concrete, operational descriptors (e.g. `reference_extractor.py`, `vulnerability_lookup.py`, `ssh_key_generator.py`).
  - Variables, parameters, and data structures must express domain intent clearly, avoiding vague single-letter identifiers or arbitrary abbreviations.
  - Group files into directories reflecting functional domain boundaries and cohesive subsystems rather than generic technical buckets.
- **Config & Defaults Separation**: Distinguish immutable invariant constants (system paths, protocol regexes, static identifiers) from configurable defaults (timeouts, model names, retry limits, server ports).
- **Strict Typing & Modern Idioms**:
  - Enforce complete type annotations on all function signatures (`mypy --strict`).
  - Use Python 3.14+ union syntax (`A | B`), standard collection types (`list`, `dict`, `set`), and `from collections.abc import ...`.
  - Use Pydantic models with `Field(default_factory=...)` for structured schemas.
- **Deterministic Test Isolation**:
  - Unit tests must isolate external dependencies (network, LLM providers, subprocesses) using mocks (`unittest.mock`, `pytest-mock`).
  - Never hardcode real user credentials or live environment endpoints in test suites.
- **Comprehensive, Robust Implementations Over Brittle Literal Collections**:
  - **Strict Prohibition on Incomplete Literal Collections (Zero-Tolerance Policy)**: Never rely on partial iterable collections of string literals, ad-hoc lists of file extensions, arbitrary keyword/attribute sets, or fragile regex substring matching for domain logic, syntax analysis, file classification, or security filtering. Using a list of strings that represents an incomplete subset of possibilities for code logic is strictly prohibited and considered a firable offense for AI agents.
  - **Why Incomplete Collections Fail**: Subsets of string literals (e.g. hardcoded lists of extensions, directory names, or error keywords) inevitably introduce random inconsistencies, false positives, fragile edge cases, and severe maintenance debt when encountering valid languages, frameworks, or domain structures outside the hardcoded subset.
  - **Always Use Standard Parsers & Dynamic Introspection**: Use established language-agnostic code quality standards, standard library parsers (`ast`, `tokenize`, `json`, `tomllib`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, `functools.lru_cache`), official specifications (e.g. Public Suffix List via `tldextract`, PEP 508 `packaging.requirements`), dynamic filesystem queries (`Path.iterdir()`), and syntactic/structural analysis over matching against a hardcoded subset of possibilities.
  - **Target-Agnostic & Language-Agnostic Design**: DevOps automation and AI developer tooling must remain robust and resilient across any software ecosystem (Python, Go, Rust, TypeScript, Java, C#, HCL, Kubernetes, Docker) without hardcoding runtime assumptions or brittle token subsets.
- **Pure Markdown Prompt Tasks & Zero Inline LLM Prompts (Zero-Tolerance Policy)**:
  - All LLM system prompts, task instructions, guardrails, evaluation rubrics, benchmark prompts, and reference criteria MUST reside in dedicated Markdown files (`.md`) under `src/devops_cli/ai/`.
  - Cramming AI/LLM prompts, multi-line instructions, evaluation text, or prompt templates inline into Python code logic is strictly prohibited and considered a firable offense for AI agents. Python code must only load prompts via `load_task_prompt()`.
- **Documentation Integrity**:
  - Keep CLI documentation, option help text, environment variable tables, and architecture guides synchronized with source code via `devops docs generate --sync-readme`.
- **Canonical Location Formatting (`filename.ext:n-n`)**:
  - All CLI terminal outputs, Rich tables, Markdown review reports, findings, external dependencies, and network reference audit records must use the canonical `filename.ext:n-n` or `filename.ext:line` location convention project-wide to ensure consistent parsing, clickable referencing, and seamless IDE integration.
- **Zero Hardcoded Scoring, Quality Assessment, or Synthetic Confidence Values**:
  - Never hardcode arbitrary numerical scores, confidence weights, synthetic thresholds, or default scoring floats anywhere in the codebase (neither inline in function bodies nor as static configuration constants).
  - All scoring, confidence ratings, and quality assessments MUST originate directly from external tools that natively produce those metrics (e.g., security scanners providing native severity ratings, tool confidence levels, or CVSS scores) or from structured AI/LLM model responses.
  - When an external tool or AI model does not produce a score or confidence rating, the field MUST remain `None` (or 0.0 where non-nullable) — never invent, synthesize, or inject artificial scoring numbers via static default constants or fallback weights.
- **Modular Stage Pipeline Architecture**:
  - Complex multi-step pipelines (such as code review, indexing, analysis, or compliance validation) must be partitioned into dedicated, single-responsibility stage modules under a `stages/` subpackage (e.g. `pre_analysis.py`, `static_scan.py`, `persona_review.py`).
  - Each stage must expose a pure functional interface, maintain explicit input/output contracts, and be decorated with `@trace_span` for granular telemetry waterfalls.
- **Provider Protocol & Deterministic Mock Isolation**:
  - External LLM backends, cloud providers, and container runtimes must implement abstract provider protocols under `providers/` (e.g. `BaseLLMProvider`) and supply deterministic mock implementations for fast, offline unit testing.
- **Standardized Domain Exception Taxonomy**:
  - All domain error states must raise strongly typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`, specifying explicit POSIX exit codes, canonical machine-readable error codes, and structured context dictionaries rather than raising generic `RuntimeError` or `ValueError`.
- **Telemetry & Metrics by Default**:
  - All new CLI subcommands, background tasks, and AI pipeline stages must be instrumented with OpenTelemetry distributed spans (`@trace_span`, `inject_traceparent_headers`) and record in-memory Prometheus metrics via `GLOBAL_METRICS`.


## 5. Agentic AI & Review System Guidelines

- **Multi-Persona Code Review**: Review systems should utilize distinct, domain-specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) to analyze diffs and provide actionable, high-signal feedback.
- **Knowledge Base & RAG Grounding**: AI review systems and coding assistants must reference repository knowledge bases (`src/devops_cli/ai/knowledge_base/` or target project docs) to ground findings against established architecture patterns, avoiding hallucinatory, outdated, or generic recommendations.
- **Zero Information Leakage & Data Privacy**: AI assistants and review systems must never extract, copy, or expose confidential, private, hidden (dotfiles/dotfolders), or `.gitignored` file contents, credentials, system paths, or proprietary data into any documents, review findings, changelogs, public commits, or code artifacts.
- **Target-Agnostic Code Analysis**: When analyzing or reviewing external repositories (e.g. under `repos/` or local target directories), evaluate code against universal software engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and the target project's own declared conventions (`AGENTS.md`, `README.md`) rather than coupling to host CLI internal assumptions.
- **Target Path Resolution & Isolation**: All file reading, AST analysis, security scanning, and dependency lookups on target projects must resolve paths relative to the target root directory (`target_dir`) to prevent host-workspace file collisions.
- **Pure Markdown Prompt Tasks & Zero Inline LLM Prompts**: All LLM system prompts, task instructions, guardrails, evaluation rubrics, benchmark prompts, and reference criteria must reside in dedicated Markdown files (`.md`) under `src/devops_cli/ai/`. Never declare multi-line prompt text strings or evaluation criteria inline in Python code.
- **Context-Aware Documentation, Example Files & Anti-Pattern Evaluation**: AI review systems and coding assistants must **never** flag documentation, architectural guides, security tutorials, knowledge base articles, prompt benchmarks, test assertions/fixtures, test mocks, template/example configuration files (`*.example.*`, `*.sample.*`, `*.tfvars.example`, `*.env.example`), or explanatory comments that describe known vulnerabilities, attack vectors, or sample configurations in the context of avoiding, mitigating, warning against, demonstrating, or explaining said configurations. Furthermore, standard Infrastructure-as-Code operator convenience outputs (`outputs.tf` generating local commands like `aws eks update-kubeconfig` or `az aks get-credentials`) must not be flagged as server-side remote command injection.
- **Zero Hallucinated CVEs & Synthetic Vulnerability IDs**: AI review systems and coding assistants must never synthesize, guess, or invent fictitious CVE numbers (e.g., `CVE-2023-4567`). All CVE citations must strictly originate from verified security scanner outputs (`scan_trivy`, `scan_uv_audit`, OSV, NVD) or established public databases.
- **Workstation & Local Development vs. Production Infrastructure Context**: AI review systems must distinguish local workstation/Minikube developer manifests (`host.minikube.internal`, local in-cluster git daemons, NodePort services, `IfNotPresent` pull policy) from production cloud deployments. Provide constructive dual-mode guidance (local default with production hardening comments) rather than reporting local dev conveniences as critical defects.
- **Multi-Namespace Root Kustomizations**: AI review systems must never flag missing namespace declarations on root or umbrella kustomization files (`k8s/kustomization.yaml`) that aggregate multiple child namespace resources or component directories (`argocd/`, `llm/`, `monitoring/`, `otel/`), as setting a top-level namespace would incorrectly override child namespace boundaries.
- **Closed-Loop Review & Self-Improvement Cycle**:
  - **Deduplication & Calibration**: Calibrate confidence scores and test explicit verification/invalidation criteria to eliminate phantom alerts.
  - **Information Exposure & Exception Sanitization (CWE-200)**: Exception messages, CLI error output, and logs must sanitize and mask private IP addresses, internal hostnames, and credentials, preserving raw targets strictly inside structured debug details dictionaries.
  - **Self-Healing & Patch Application**: Review findings should provide drop-in remediations verifiable by unit tests and automated CI gates.
  - **Feedback Dataset Export & RAG Grounding**: Export verified and invalidated review findings to structured datasets (`devops review export-feedback`) to continuously ground RAG retrieval and refine LLM evaluation prompts.
  - **Continuous Knowledge Feedback**: Synthesize recurrent patterns into repository architecture guidelines and targeted test fixtures.
