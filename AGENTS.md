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
  - **Zero Information Leakage & Comprehensive Environment Sanitization**:
    - Never leak, extract, or expose confidential, private, hidden, or `.gitignored` files (`.env*`, `.ssh/`, `.data/`, `~/.gemini/`, credentials, private keys) into any documents, changelogs, review findings, public commits, or code artifacts.
    - **Strict Prohibition of Internal Systems, Homelab Configurations & Real Infrastructure Data**: AI agents, developers, and automated workflows MUST NEVER record, publish, or leak concrete internal hostnames (e.g. `*.lan`, `*.local`, physical machine names, private server/workstation hostnames), private RFC 1918 IP addresses (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`), private container registries, non-standard local NodePort services (e.g. `:30500`), physical block devices or mount paths (e.g. `/mnt/nvme*`, `/dev/sd*`), or private homelab topology details into any task tracking (`docs/agent/tasks/`), documentation, roadmaps, architecture diagrams, code comments, tests, manifests (`k8s/`), or configuration templates (`config.yaml`).
    - **Mandatory Abstract Roles & Documentation Placeholders**: Always replace concrete infrastructure environments with standardized abstractions:
      - Hostnames: `<storage-node>`, `<gpu-node>`, `<worker-node>`, `<host>`, `node1.example.internal`, `localhost`.
      - IP Addresses: RFC 5737 documentation blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or loopback (`127.0.0.1` / `localhost`). Never publish concrete private RFC 1918 IP addresses in documentation.
      - Registry Endpoints: `ghcr.io/<org>/<image>:<tag>` or `<registry-host>:<port>/<image>:<tag>`.
      - Storage Mount Paths: `<storage-mount-path>`, `<fast-storage>`, standard Kubernetes PersistentVolumeClaims.
    - **Configuration Template Hygiene (`config.example.yaml`) vs. User Runtime Config (`config.yaml`)**:
      - Committed configuration templates (`config.example.yaml`) and documentation must strictly use generic documentation or localhost endpoints (`http://localhost:11434`, `http://localhost:6333`, `http://localhost:8080`), never private LAN hostnames, homelab endpoints, or internal IP addresses.
      - **Strict Protection of User Runtime Config (`config.yaml`)**: The local `config.yaml` is uncommitted, gitignored, and belongs exclusively to the user's active runtime environment. AI agents and automated workflows **MUST NEVER** overwrite, sanitize, or reset the user's designated `ollama_urls`, inference hostnames, or custom ports in `config.yaml` to localhost. Sanitization rules apply solely to repository templates, committed code, tests, documentation, and task tracking files.
    - Redact, mask, or generalize sensitive local paths, environments, or user identifiers in documentation, prompt contexts, or code examples.
  - Bounded string truncation on error details: Always enforce bounded length caps ($\le 256$ chars) on external or caller-provided inputs propagated into exception `details` dictionaries or structured error logs to prevent log bloat and injection (CWE-209 / CWE-400).
  - Mitigate Server-Side Request Forgery (SSRF) and network egress risks by validating destination endpoints.
  - Enforce subprocess safety with explicit command argument lists, bounded timeouts, and error handling.
- **Never Lower Security Standards or Quality Thresholds**: Never lower, relax, disable, bypass, or weaken security standards, quality thresholds (such as minimum 90% code coverage, strict static type checks, or lint rules), or compliance validations unless explicitly instructed by the user.
- **Continuous Standards Compliance & Solution Refinement**: Ensure every proposed solution, design, code change, or architecture meets all project standards and conventions, iteratively refining until every standard is met or exceeded.
- **Proactive GitHub Project Tracking & Workflow Grounding**: Every engineering action, planned deliverable, active WIP implementation, review remediation, and defect investigation MUST be formally grounded in GitHub Projects v2 (`https://github.com/dan-petty/devops-cli/projects`) and GitHub Issues. Working on "invisible" or ungrounded tasks without an active project card is strictly prohibited. AI agents must proactively bootstrap tasks into issues, maintain real-time card state transitions, and reconcile custom fields on every lifecycle event.
- **API Rate Limit Honor, Resilient Backoff & Quota Budgeting**:
  - AI agents, automated workflows, and CLI tools MUST actively respect API rate limits, complexity budgets, and resource quotas across all external services (GitHub REST/GraphQL APIs, AI LLM/embedding inference endpoints, package registries, cloud providers, and observability services).
  - **Proactive Rate Limit Inspection**: Actively check remaining rate limits and reset windows (e.g. `gh api rate_limit`, response headers `x-ratelimit-remaining`, `x-ratelimit-reset`, or HTTP 429 `Retry-After`).
  - **Adaptive Fallback**: When complexity-intensive APIs or GraphQL endpoints reach secondary rate limits or complexity bounds, gracefully adapt by falling back to targeted REST API calls or batching requests instead of failing or hammering endpoints.
  - **Bounded Exponential Backoff with Jitter**: Never enter tight, busy-waiting retry loops or unthrottled burst calls against rate-limited endpoints. If an HTTP 429 (`Too Many Requests`) or rate-limit HTTP 403 error is encountered, honor the reset window or apply exponential backoff with random jitter before retrying.
  - **Client-Side Caching & Workload Deduplication**: Cache idempotent queries, remote metadata, and review findings locally (in `.data/` or Valkey L2 cache) to minimize external round-trips and prevent quota exhaustion.
- **Pre-1.0 Alpha Lifecycle & Zero Backwards Compatibility Guarantee**:
  - `devops-cli` is active **alpha software** prior to release `1.0.0`.
  - **Zero Backwards Compatibility Guarantee**: Until at least release `1.0.0`, there is **no intention of maintaining backwards compatibility**. Breaking changes, interface evolutions, parameter alterations, and schema redesigns may occur across any release cycle without legacy shims.
  - **Zero Legacy Remnants & Rapid Path to Maturity**: The codebase MUST remain clean of legacy references, obsolete shims, deprecated aliases, and compatibility remnants at all times so that it can reach architectural maturity at a reasonable rate. AI agents and developers must ruthlessly eliminate vestigial code rather than introducing or retaining backwards-compatibility wrappers.
- **Post-1.0 Semantic Versioning & Enterprise Change Management**:
  - Any version released after `1.0.0` will strictly adhere to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) conventions (`MAJOR.MINOR.PATCH`).
  - Post-1.0 releases will utilize all enterprise change management best practices, including runtime feature flags, structured multi-release deprecation cycles (emitting actionable deprecation warnings for at least one minor release cycle prior to removal), and automated migration tooling.
- **Clean Solutions Over Legacy Remnants (Zero Zombie Code)**: When modifying, refactoring, or replacing features, schemas, configurations, or interfaces, implement clean, complete solutions and ruthlessly remove obsolete code, variables, aliases, fallback shims, and legacy workarounds. Never leave remnants or vestigial fallback paths.
- **Dedicated Agent Workspace Data Isolation**: The workspace data directory is configured via `DEVOPS_CLI_DATA_DIR` (or configuration key `data.dir`, defaulting to `./.data`). AI agents executing CLI review sessions, background benchmarks, analysis scans, test executions, or temporary operational tasks must isolate agent work products (reviews, logs, traces, metadata) under the dedicated `agent/` subfolder (`<data_dir>/agent`, e.g. `./.data/agent`) to keep agent artifacts separate from the user workspace data tier.
- **Mandatory Backup for Files Outside Workspace**: Whenever modifying, overwriting, editing, or truncating any file located outside the project workspace directory (e.g. `~/.ssh/`, `~/.bashrc`, `~/.zshrc`, `/etc/`), AI agents **MUST ALWAYS** create a timestamped backup named `<original-filepath>.bak-<YYYYMMDD-HHMMSS>` prior to making edits.
- **Mandatory Defect Filing on CLI Errors & Warnings (Zero Unrecorded Issues)**: Whenever an AI agent or automated workflow encounters an unhandled error, subcommand failure, exception, crash, diagnostic warning, or unexpected output while executing `devops` CLI commands, the agent **MUST ALWAYS PROMPTLY CREATE A FORMAL BUG/ISSUE ENTRY** in GitHub Issues and synchronize it into GitHub Projects tracking. Suppressing, ignoring, bypassing, or silently working around CLI errors or warnings without formal defect tracking is strictly prohibited.
- **Mandatory PR Check Monitoring & Review Thread Resolution (Zero Unmonitored PRs & Unresolved Threads)**:
  - **Always Monitor & Fix CI Checks**: Whenever creating a pull request or pushing commits to a pull request branch, AI agents **MUST ALWAYS** actively monitor remote CI checks (`gh pr checks <pr_number>`) until all checks pass. If any check fails, immediately inspect failed job logs (`gh run view --log-failed`), diagnose root causes, apply test-first fixes, push corrective commits, and re-verify until 100% green. Never abandon a PR or conclude work with failing checks.
  - **Always Check & Address Review Comments**: When working on any pull request branch, AI agents **MUST ALWAYS** check for pull request comments and review discussion threads (`devops pr threads list <pr_number> --unresolved-only` or `gh api`), author test-first fixes, reply directly within the review thread on the exact comment being addressed (`devops pr threads reply <thread_id> "<body>"` or GraphQL mutation `addPullRequestReviewThreadReply`), and resolve each thread (`devops pr threads resolve <thread_id>` or GraphQL mutation `resolveReviewThread`) when all issues in the thread have been addressed.
- **Unambiguous, Purpose-Driven Naming & Zero Namespace Confusion**:
  - Every file, configuration document, module, class, function, and variable MUST have a self-documenting name that explicitly conveys its exact architectural responsibility and purpose.
  - **Strictly Avoid Vague or Cryptic File Names**: NEVER create or retain vague, ambiguous, or cryptic file names (such as `_config.yaml`, `config_v2.yaml`, `temp_util.py`, `helper.py`, `common.py`, `data.json`).
  - **Zero Duplicative Names Across Scopes**: NEVER co-locate files with overlapping or near-identical names (e.g. `config.yaml` alongside `_config.yaml`) that obscure file ownership, configuration scope, or operational role. Tool-specific configurations (such as documentation sites, linters, or bundlers) MUST be housed within their respective functional directories and purpose-named (e.g. `docs/github-pages.config.yaml` instead of root `_config.yaml`).
  - **Context-Rich Variable Naming**: Strictly avoid single-letter variables, ambiguous abbreviations, or generic names (`res`, `obj`, `data`, `val`, `cfg`, `page`, `url`). Use expressive, domain-grounded variable names (`review_diff_segment`, `jekyll_config_path`, `embedding_cluster_urls`) that clarify intent without requiring callers to reverse-engineer context.

---

## 2. Development Workflow & Progressive Verification

All work follows a test-first progressive verification strategy to optimize developer feedback loops while guaranteeing release readiness:

### Test-First Development Cycle (TDD as Living Contract)
1. **Define Specification via Tests First**: Before writing or changing implementation code in `src/`, author comprehensive unit and integration tests defining intended behavior, arguments, return structures, edge cases, and exception handling. Tests serve as the authoritative, executable specification.
2. **Submodule-Aligned Test Organization (No Arbitrary One-Off Files)**:
   - Tests MUST be organized strictly by submodule and domain functionality under `tests/` (`tests/test_<submodule>.py` or `tests/<submodule>/test_<feature>.py`), mirroring the source tree in `src/devops_cli/`.
   - **Prohibited Naming**: NEVER create arbitrary, one-off, or temporary test files named after review sessions, bug report numbers, incident timestamps, or pull requests (e.g. `tests/test_review_findings_remediation_164259.py`, `tests/test_findings_session_*.py`).
   - Regression tests, bug fixes, and review finding remediations MUST be incorporated directly into the canonical, corresponding submodule test file (e.g. `tests/test_consolidation_dry_run_decorator.py`, `tests/test_server.py`, `tests/test_consolidation_security_sanitizer.py`, `tests/test_review_verification.py`, `tests/test_github_projects.py`, `tests/test_github_milestones.py`).
3. **Implement Feature Logic**: Write clean, concise implementation code in `src/` to satisfy the tests.
4. **Verify Locally**: Run targeted tests (`uv run pytest tests/test_<feature>.py`) for immediate feedback during development.
5. **Comprehensive Quality Gate**: Execute `devops ci` (or `uv run devops ci`) to validate all gates and enforce the minimum project-specified code coverage requirement across `src/`.

### Project Planning & Task Tracking
- **Mandatory Planning Artifacts**: Document project planning and technical implementation designs in dedicated planning documents (`implementation_plan.md`, `docs/agent/tasks/task-<issue>-<slug>.md`, `docs/ROADMAP.md`) prior to executing complex, multi-step, or architectural changes.
- **Mandatory GitHub Projects v2 Session Bootstrap (Zero Ungrounded Tasks)**:
  - At the inception of every AI agent session, upon receiving any user prompt, or before starting development, AI agents **MUST PROACTIVELY BOOTSTRAP GITHUB PROJECT TRACKING**:
    1. **Query Active Project Status**: Inspect board status and views via `devops gh project status` (or FastMCP `gh_project_status`) and triage queue via `devops gh issues triage` (or FastMCP `gh_issue_triage`).
    2. **Ground User Request to an Issue Card**: Every feature, bug fix, refactor, or documentation task must have a corresponding GitHub Issue and Project Item.
       - If a matching open issue exists: link the task to it, verify its milestone and taxonomy labels, and immediately move its project card to `In Progress` (`devops gh project sync`).
       - If no issue exists: **IMMEDIATELY AUTHOR A FORMAL TRACKING ISSUE** (`gh issue create` or FastMCP `gh_issue_create`), assign the active release milestone (`--milestone "v<version>"`), assign declarative taxonomy labels matching `.github/labels.yml` (`type/*`, `scope/*`, `priority/*`, `status/in-progress`), and synchronize it to the project board (`devops gh project sync` or FastMCP `gh_project_sync`).
- **Modular Per-Task Tracking Architecture (`docs/agent/tasks/`) & Real-Time Card Movement**:
  - **Zero Merge Conflicts Mandate**: To eliminate git merge conflicts between concurrent feature branches, task tracking is maintained in **dedicated per-task files** under `docs/agent/tasks/` (`docs/agent/tasks/task-<issue>-<slug>.md`). Topic branches must ONLY create or modify their own dedicated task file; editing other branches' task files is strictly prohibited. An index table of active tasks is maintained in [`docs/agent/task.md`](docs/agent/task.md).
  - **Commit Context Mandate & Zero Standalone Tracking Commits**: Updates to task tracking files under `docs/agent/tasks/` MUST ONLY be made in the context of the functional changes delivering that specific task (bundled atomically into functional deliverable commits) or when merging the PR into the release branch. They must NEVER be committed as standalone or isolated one-off commits.
  - Maintain bidirectional synchronization between `docs/agent/tasks/` and GitHub Projects v2 cards across five unambiguous lifecycle states:
    - **Backlog**: Queued deliverables, backlog requirements, and upcoming milestone items awaiting assignment.
    - **Ready**: Scoped items with concrete acceptance criteria and tests designed, awaiting active development.
    - **In Progress (WIP)**: Active work items currently being authored or edited. **Card must be moved to In Progress before modifying code in `src/`**. Mirrored in `docs/agent/tasks/task-<issue>-<slug>.md` under `**Status**: In Progress` or `### In-Progress Tasks (WIP)`.
    - **In Review**: Pull Request opened with automated review, CI checks running, and peer feedback in progress. Mirrored in `docs/agent/tasks/task-<issue>-<slug>.md` under `**Status**: In Review`.
    - **Done**: Pull Request squash-merged into release branch, remote CI checks green, issue closed, and milestone ratios updated. Mirrored in `docs/agent/tasks/task-<issue>-<slug>.md` under `**Status**: Done` or `### Completed Tasks`.
- **Mandatory Custom Field Reconciliation (`devops gh project sync`)**:
  - Ground all task lifecycles, issue tracking, and sprint planning in GitHub Projects v2 (`.github/project-template.json`) and roadmap milestones (`docs/ROADMAP.md`).
  - Every project item MUST be enriched with all 6 standardized custom fields: `Status`, `Milestone`, `Priority`, `Category`, `Value`, and `Effort`.
  - AI agents must run `devops gh project sync` (or FastMCP `gh_project_sync`) after authoring issues, creating PRs, or updating branches to ensure data-driven custom fields reflect declarative taxonomy labels (`type/*`, `priority/*`).

### Knowledge Base Consultation
Before planning, implementing, debugging, refactoring, or reviewing code, consult the **DevOps CLI Knowledge Base** under [`src/devops_cli/ai/knowledge_base/README.md`](src/devops_cli/ai/knowledge_base/README.md):
- **DevOps CLI Internals ([`devops_cli/`](src/devops_cli/ai/knowledge_base/devops_cli/))**: Architecture, configuration, keyring management, CLI matrix, and 13 operational task manuals (`devops_cli/tasks/`).
- **IT Domain Guides ([`it_domains/`](src/devops_cli/ai/knowledge_base/it_domains/))**: 10 IT domain topic guides (`it_domains/topics/`) and 20 integrated tool manuals (`it_domains/tools/`).

### Verification Strategy & Routine Tasks Execution
- **Mandatory Routine Tasks Execution**: Check and execute applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) in sequence and cadence.
- **Primary CI Verification Gate**: Run `devops ci` (or `uv run devops ci`) to comprehensively validate all 10 gates. Do not run redundant standalone tools that are already aggregated by `devops ci`.
- **Mandatory Iterative CI Loop**: Make planned code changes, run `devops ci`, fix reported issues, and run `devops ci` again iteratively until all quality gates pass cleanly.
- **Mandatory Documentation Synchronization**: Update documentation, command matrix, and README (`devops docs generate --sync-readme`, `docs/`, `AGENTS.md`) after every change to prevent documentation drift.
- **Mandatory CLI Defect Filing**: If `devops` CLI commands emit unexpected errors, traceback failures, or warnings during local development or routine tasks, immediately file a tracking issue and sync to GitHub Projects before continuing.
- **Mandatory Telemetry, Log & CLI Output Review**: AI agents must routinely review devops CLI command outputs, application logs (under `.data/logs/`), metrics, and OpenTelemetry tracing data (`@trace_span` / Logfire) for performance issues, latency bottlenecks, misconfigurations, unhandled exceptions, and diagnostic warnings. Any detected regression, error, or warning must be remediated and formally tracked in GitHub project tracking.


### Build, Lint & Test Commands
| Operation | Command | Purpose |
| :--- | :--- | :--- |
| **Dependency Sync** | `uv sync` | Synchronize virtual environment with lockfile. |
| **Full CI Suite (Primary Gate)** | `devops ci` / `uv run devops ci` | Comprehensive quality gate (version, test, coverage $\ge 90\%$, lint, format, typecheck, audit, security, actionlint, docs). |
| **Targeted Test** | `uv run pytest tests/test_<feature>.py` | Fast, isolated unit test execution for debugging. |
| **Targeted Lint** | `uv run ruff check path/to/file.py` | Fast lint inspection on modified files. |
| **Targeted Typecheck** | `uv run mypy path/to/file.py` | Strict static type validation on modified modules. |
| **Documentation Sync** | `devops docs generate --sync-readme` | Introspect CLI and synchronize markdown references and README. |
| **Milestone Lifecycle** | `devops gh milestones list` / `close <ver>` | Inspect milestone completion rates and close on release merge. |
| **Project Sync** | `devops gh project sync` | Synchronize task items and provision fields on GitHub Projects v2. |

---

## 3. Git Hygiene, Release Governance & GitHub Integration

- **Branch Hierarchy & Isolation**:
  - **Zero Direct Commits to `main`**: All work must be conducted on dedicated topic branches (`feat/<description>`, `fix/<description>`, `docs/<description>`, `refactor/<description>`).
  - **PR Base Branch Targeting**: Feature, fix, and refactoring PRs must target the active release branch (`--base release/v<version>`). Release branches target `main` when cutting an official release.
  - **Branch Freshness**: Always branch off fresh upstream tracking branches (`git fetch origin`).
  - **Strict Remote Branch Lifecycle & PR Governance (Zero Orphan Remote Branches)**:
    - Every remote topic or feature branch on `origin` MUST have an associated, open Pull Request targeting the active release branch (`release/v<version>`) or `main` (for official release PRs).
    - **Immediate Deletion of Merged or Superseded Branches**: Once a PR is merged into its target branch, or if a branch's changes have been incorporated or superseded, the remote branch MUST be deleted immediately (`git push origin --delete <branch>`) and local tracking references pruned (`git fetch --prune origin`).
    - **No Orphan Remote Branches**: Remote branches without an active PR or active development purpose are strictly prohibited. If updates from an old or dormant branch are still required, apply or cherry-pick them to the current active release branch / active PR, and delete the obsolete remote branch immediately.
- **Commit Standards**:
  - Follow **Conventional Commits** (`feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, `docs(scope): ...`).
  - **Atomic Commits by Default**: Break multi-faceted work into small, logically self-contained commits with precise messages.
  - **No Internal References or Numeric IDs in Commit Messages**: Commit messages and PR titles MUST describe the technical or functional change using standard, descriptive engineering terminology. NEVER include internal session timestamps (e.g. `164259`, `003105`), review session numbers, subagent IDs, prompt phase numbers (e.g. `Phase 48.5`), or arbitrary numeric identifiers in commit subjects or messages.
  - **No Standalone Agent Tracking Commits**: Updates to internal agent tracking documentation under `docs/agent/` (such as `docs/agent/tasks/` or `docs/agent/task.md`) MUST NEVER be committed as standalone one-off commits. They must always be bundled atomically into the corresponding feature, fix, or refactoring commit that delivers the actual code changes, or kept in local workspace state until bundled with functional deliverable commits.
- **Pull Request Governance & Title Conventions**:
  - **Conventional Commit PR Titles**: Standard feature, fix, refactoring, documentation, and chore PR titles MUST follow Conventional Commits (`feat(scope): concise description`) in standard engineering terminology for clean squash-merging.
  - **Strict Release PR Title Convention (`feat(release): v<version>`)**: Release Pull Requests targeting `main` from a release branch MUST strictly follow the exact canonical format `feat(release): v<version>` (or `fix(release): v<version>` / `feat(release)!: v<version>` for breaking changes), e.g. `feat(release): v0.2.12`. NEVER append descriptive summaries, release highlights, or verbose explanations to release PR titles (highlights belong strictly in the PR body and release notes). This matches `_format_release_title()` and repository squash-merge git history.
  - **GitHub Release Titles**: Strictly the version tag / number from `pyproject.toml` (e.g. `v0.2.12`) without conventional commit prefixes.
  - **Pre-1.0 vs Post-1.0 Release Governance**:
    - **Pre-1.0 (`0.y.z`)**: Active alpha software with no backwards compatibility guarantees. The codebase remains clean of legacy remnants at all times to reach maturity rapidly.
    - **Post-1.0 (`X.Y.Z`)**: Strict adherence to Semantic Versioning 2.0.0 and enterprise change management (feature flags, multi-release deprecation cycles, and automated migrations).
  - **Human-in-the-Loop Merging**: AI agents prepare clean commits, open/update PRs, monitor remote CI checks (`gh pr checks`), and leave merge approval to maintainers. Never merge autonomously.
  - **Mandatory CI Check Monitoring & Remediation on PR Creation and Branch Pushes**:
    - AI agents **MUST ALWAYS** actively monitor remote CI checks whenever creating a pull request (`gh pr create`) or pushing commits to a branch that has an active pull request (`git push`).
    - Actively monitor remote GitHub Actions status (`gh pr checks <pr-number>` or `gh run watch`) until all checks complete.
    - If any check fails, AI agents **MUST IMMEDIATELY** inspect the failure logs (`gh run view --log-failed`), diagnose the root cause, author test-first corrective commits, push to the branch, and re-verify checks until all checks are 100% green. Never abandon a pull request or conclude an agent turn with failing CI checks.
  - **Mandatory PR Review Comment Inspection, In-Thread Replies & Thread Resolution**:
    - When working on any pull request branch, AI agents **MUST ALWAYS** check for pull request review comments and discussion threads (`devops pr threads list <pr-number> --unresolved-only`, FastMCP `pr_threads_list`, or `gh api`).
    - Actively inspect, evaluate, and address all code review feedback (from GitHub Copilot, CodeQL, security scanners, or human reviewers).
    - Address every comment using Test-First Development (author/update tests first, implement clean fixes, ensure zero zombie code).
    - **Mandatory Direct In-Thread Replies**: AI agents MUST reply **directly within each specific review discussion thread** on the exact comment being addressed (`devops pr threads reply <thread-id> "<body>"`, FastMCP `pr_thread_reply`, or GraphQL mutation `addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: $threadId, body: $body })`). Posting solely a general, top-level PR summary comment (`gh pr comment`) is **STRICTLY PROHIBITED** and does not satisfy this requirement.
    - Every in-thread reply must clearly articulate the concrete code modification, architectural rationale, or test addition implemented to resolve the reviewer's finding.
    - **Mandatory Thread Resolution**: Once all issues in a review discussion thread have been addressed and verified, AI agents **MUST PROGRAMMATICALLY RESOLVE THE THREAD** on GitHub (`devops pr threads resolve <thread-id>`, FastMCP `pr_thread_resolve`, or GraphQL mutation `resolveReviewThread(input: { threadId: $threadId })`). Never leave addressed review threads unresolved.
    - **Closed-Loop Feedback Dataset Calibration**: Whenever remediating review findings from automated review sessions (`.data/reviews/<session>/findings.json`), AI agents MUST update the status to `MITIGATED` or `INVALIDATED` with explicit step-by-step rationale, export the feedback dataset via `devops review export-feedback --status ALL --output .data/reviews/feedback_dataset.jsonl` (or FastMCP `review_export_feedback`), synchronize prompt task instructions (`src/devops_cli/ai/tasks/`) to prevent recurrence, and synchronize the knowledge base to ensure verified remediations permanently reinforce the self-improvement training loop.
    - Always re-verify local quality gates (`devops ci`) and monitor remote GitHub Actions status (`gh pr checks`) until 100% green.
- **GitHub Projects, Issues, Views, Milestones & Label Governance (Project Management Integration)**:
  - **Active Milestone GitHub Resource & Issue Population Mandate**:
    - When cutting a new release branch or transitioning to a new active milestone, AI agents **MUST PROACTIVELY POPULATE GITHUB RESOURCES** (milestones, issues, project items, labels) for that active milestone.
    - **Zero Empty Open Issues State**: The repository's open issues queue (`https://github.com/dan-petty/devops-cli/issues?q=is%3Aissue+state%3Aopen`) must **NEVER** be left empty while an active release milestone exists with planned deliverables in [`docs/ROADMAP.md`](docs/ROADMAP.md).
    - Immediately upon milestone activation, AI agents must author formal tracking issues for every planned deliverable using standard templates (`.github/ISSUE_TEMPLATE/`), assigning:
      - Canonical title following Conventional Commits (e.g. `feat(<scope>): <description>`).
      - Milestone linkage (`--milestone "v<version>"`).
      - Taxonomy labels matching `.github/labels.yml`: at least one `type/*`, one `scope/*`, and appropriate `priority/*` (`priority/p0-critical` through `priority/p3-low`).
      - Clear problem statement, proposed architectural solution, and acceptance criteria.
    - Synchronize the new issues into GitHub Projects v2 (`devops gh project sync` or FastMCP `gh_project_sync`), linking card lifecycles with [`docs/agent/tasks/`](docs/agent/tasks/README.md) and PRs via closing keywords (`Closes #<issue>`).
  - **Mandatory Defect & Warning Incident Tracking (Zero Unrecorded CLI Errors & Warnings)**:
    - Whenever an AI agent encounters an unhandled error, subcommand failure, crash, diagnostic warning, or unexpected behavior while executing `devops` CLI commands (e.g. CLI crashes, option parsing errors, unhandled exceptions, linter/scanner warnings, or unexpected non-zero exits), the agent **MUST IMMEDIATELY CREATE A FORMAL BUG/ISSUE ENTRY** in GitHub project tracking.
    - **Issue Creation Protocol**:
      - File a GitHub issue using the standardized bug report template (`.github/ISSUE_TEMPLATE/bug_report.yml` or `gh issue create`).
      - Format the title using Conventional Commits: `fix(<scope>): <concise description of error/warning>`.
      - Apply declarative taxonomy labels matching `.github/labels.yml`: `type/bug`, appropriate `scope/*`, `priority/*` (`priority/p0-critical` for blocking CLI crashes/failures, `priority/p1-high` or `priority/p2-medium` for warnings/non-blocking bugs), and `status/triage` (or `status/in-progress` if actively resolving).
      - Link the active release milestone (`--milestone "v<version>"`).
      - Provide full operational context in the issue body: exact CLI command executed, operating environment, full terminal traceback or warning message, steps to reproduce, and root-cause analysis.
      - Synchronize the new issue into GitHub Projects v2 (`devops gh project sync` or FastMCP `gh_project_sync`) so that it appears in the *Triage & Quality Table* view (`type/bug`, `status/blocked`, `status/triage`).
      - Immediately mirror the bug tracking entry in a dedicated task file under [`docs/agent/tasks/`](docs/agent/tasks/README.md) and [`docs/ROADMAP.md`](docs/ROADMAP.md) under active defects.
      - **Zero Suppression Policy**: Never suppress, ignore, work around silently, or bypass errors or warnings emitted by the `devops` CLI without formally documenting and tracking them as defects in GitHub Issues and GitHub Projects.
  - **Issue Tracking, Triage & PR Linkage**:
    - Track all engineering issues, bug reports, feature requests, and technical chores using standardized issue templates (`.github/ISSUE_TEMPLATE/`: `bug_report.yml`, `feature_request.yml`, `security_advisory.yml`, `task.yml`).
    - Every PR addressing an issue MUST explicitly link to it using canonical GitHub closing keywords in the PR body (`Fixes #<issue>`, `Closes #<issue>`, `Resolves #<issue>`).
    - Enforce declarative taxonomy labels on all issues matching `.github/labels.yml` across `type/*`, `scope/*`, `priority/*`, and `status/*`.
    - Prioritize incoming defects and blockers using the standardized *Triage & Quality Table* view (`type/bug`, `status/blocked`, `status/triage`) ordered by `Priority` (`P0-Critical` through `P3-Low`).
    - **Continuous Issues Triage Auditing**: AI agents MUST regularly run `devops gh issues triage` (or FastMCP `gh_issue_triage`) to detect and remediate untriaged issues missing mandatory taxonomy labels or milestone linkage. Inspect issue portfolio health via `devops gh issues status` (or FastMCP `gh_issue_status`).
  - **Mandatory PR Taxonomy Labels**: Every PR MUST possess at least one `type/*` label and at least one `scope/*` label. Validate compliance with `devops gh labels audit`.
  - **Roadmap-Driven Milestone Linking & Automated Closure**:
    - Every issue and PR targeting a release branch MUST link to the active release milestone in [`docs/ROADMAP.md`](docs/ROADMAP.md). Synchronize via `devops gh milestones sync` and inspect progress via `devops gh milestones status <version>`.
    - **Automated Milestone Closure**: When preparing release tags or when a release PR is merged into `main`, AI agents and CI workflows MUST close the release milestone via `devops gh milestones close <version>` (or FastMCP `gh_milestone_close`) to prevent stale open milestones.
  - **Mandatory Historical Documentation Compaction on Major & Minor Releases**:
    - When cutting, preparing, or finalizing a new major (`vX.0.0`) or minor (`v0.X.0`) release, AI agents and automated release workflows **MUST AUTOMATICALLY COMPACT HISTORICAL DOCUMENTATION** across the repository:
      - **`docs/ROADMAP.md`**: Consolidate completed milestone subsections of older major/minor release series (e.g., condensing individual `v0.1.0` through `v0.1.9` subsections into a single `### Workstation Foundation, SecOps, Multi-Cloud IaC & Core Architecture (v0.0.1 – v0.1.9 - Completed)` milestone block). In Section 3 (*Value vs. Effort Prioritization Matrix*), consolidate older completed rows into high-level category summary entries (e.g., `v0.1.x`) to keep the matrix tightly focused on the active minor release and forward-looking roadmap.
      - **`docs/RELEASE_NOTES.md`**: Consolidate verbose highlight sections of older minor/major series into a unified, high-level summary block (e.g., `## 🚀 Highlights of v0.1 Series (v0.1.0 – v0.1.13 - Completed)`), preventing vertical document sprawl.
      - **`RELEASE_CYCLE.md`**: Ensure roadmap references point strictly to the canonical, active release series in `docs/ROADMAP.md`, ruthlessly pruning vestigial or outdated version targets.
      - **Historical Logs & Archive (`docs/agent/archive/`)**: Maintain historical task archives under `docs/agent/archive/` while keeping active task tracking lean and scoped strictly to active release milestones, eliminating redundant scratchpad planning blocks.
      - **Context Optimization Rationale**: Historical compaction preserves context window capacity, eliminates assistant distraction on obsolete milestones, and maintains a high-density, poetic codebase without losing commit traceability.
  - **GitHub Pages Publishing & Deployment Verification Mandate**:
    - **Publishing Health & SSL Inspection**: Inspect GitHub Pages site deployment status, custom domains, and HTTPS enforcement (`enforce_https: true`) via `devops gh pages status` (or FastMCP `gh_pages_status`).
    - **Local Configuration & Docs Root Verification**: Before submitting documentation changes or cutting releases, AI agents MUST execute `devops gh pages verify` (or FastMCP `gh_pages_verify`) to validate local Jekyll configuration files (`docs/github-pages.config.yaml` syntax, title, markdown parser) and ensure the `docs/` publishing root exists.
    - **Build Triggering & History**: When documentation deployments require re-dispatching, trigger builds via `devops gh pages build` (or FastMCP `gh_pages_build`) and inspect deployment progression via `devops gh pages builds`.
  - **GitHub Projects & Issues Views Lifecycle Population Mandate (`https://github.com/dan-petty/devops-cli/projects` & `https://github.com/dan-petty/devops-cli/issues/views`)**:
    - The repository's Projects tab (`https://github.com/dan-petty/devops-cli/projects`) and issue views interface (`https://github.com/dan-petty/devops-cli/issues/views`) are powered by GitHub Projects v2. AI agents MUST ensure that repository projects and issue views are populated, linked, and actively synchronized matching the 4 canonical views in `.github/project-template.json`:
      1. **Sprint Kanban** (`BOARD`, Group By: `Status`): Active sprint execution tracking cards across lifecycle columns (`Backlog`, `Ready`, `In Progress`, `In Review`, `Done`), filtered strictly to the active release milestone.
      2. **Roadmap Timeline** (`ROADMAP`, Group By: `Milestone`): Chronological delivery roadmap grouped by release milestone, tracking deliverable start/target dates and milestone completion ratios.
      3. **Triage & Quality Table** (`TABLE`, Priority-Ordered): Incoming defect and blocker triage queue ordered by `Priority` (`P0-Critical` through `P3-Low`), filtering active bugs (`type/bug`, `status/blocked`, `status/triage`).
      4. **Value vs Effort Priority Matrix** (`TABLE`, Group By: `Category`): Strategic portfolio matrix grouping deliverables into Quick Wins, Major Projects, Fill-Ins, and Foundation in direct alignment with [`docs/ROADMAP.md`](docs/ROADMAP.md).
    - **Mandatory Repository Project Linkage & Creation**: Ensure that the active GitHub Projects v2 board conforming to `.github/project-template.json` is created and linked to the repository (`devops gh project link <number>`) so that the board appears directly under `https://github.com/dan-petty/devops-cli/projects` and its views appear under `https://github.com/dan-petty/devops-cli/issues/views`. Discover existing boards via `devops gh project list` (or FastMCP `gh_project_list`). If no project board exists yet, AI agents must instruct or provision the project matching the declarative template (`.github/project-template.json`) and link it immediately.
    - **Continuous Project & Views Drift Auditing**: Routinely audit project board health and field schema alignment via `devops gh project audit` (or FastMCP `gh_project_audit`) and view configurations via `devops gh views audit` (or FastMCP `gh_views_audit`).
    - **Continuous Custom Field & Project Item Population**: Every issue and pull request for the active milestone MUST be added as a project item and populated with custom project fields: `Status`, `Milestone`, `Priority`, `Category`, `Value`, `Effort`. Synchronize card states using `devops gh project sync` or FastMCP `gh_project_sync`.
    - **Strict Real-Time Kanban State Progression & WIP Movement**:
      - Manage state transitions strictly (`Backlog` $\to$ `Ready` $\to$ `In Progress` $\to$ `In Review` $\to$ `Done`) across issues and tasks in [`docs/agent/tasks/`](docs/agent/tasks/README.md):
        - `Backlog`: Queued items awaiting milestone assignment or scheduling.
        - `Ready`: Scoped items ready for immediate development with designed test specifications.
        - `In Progress`: Active work items currently being authored or edited. **Card MUST be transitioned to In Progress before making edits in `src/`**. Mirrored in `docs/agent/tasks/task-<issue>-<slug>.md` under `**Status**: In Progress`.
        - `In Review`: Pull Request opened with CI checks running and code reviews in progress. Mirrored in `docs/agent/tasks/task-<issue>-<slug>.md` under `**Status**: In Review`.
        - `Done`: Pull Request squash-merged by maintainer into release branch, remote CI verified, and issue closed.
      - **Zero Disconnected PRs**: Every PR MUST link to an active tracking issue (`Closes #<id>`, `Fixes #<id>`), be added as a project item to the project board, and possess taxonomy labels (`type/*`, `scope/*`) so that its custom fields (`Category`, `Value`, `Effort`) are data-driven and automatically populated.
    - **Active Triage & Quality Queue Monitoring**: AI agents must routinely inspect and populate the *Triage & Quality Table* (`type/bug`, `status/blocked`, `status/triage`) to promptly triage, remediate, and track incoming bugs, review findings, and pipeline failures.
    - **OAuth Scope Diagnostics & Offline Validation**: When the local GitHub token lacks `project` or `read:project` scopes, instruct the user to authorize via `gh auth refresh -s project,read:project`, while validating template integrity offline via `devops gh project status`, `devops gh views list`, `devops gh views spec`, and `devops gh project sync --dry-run`.
    - **Zero Empty Projects & Views State**: The repository's Projects tab (`https://github.com/dan-petty/devops-cli/projects`) and issue views queue (`https://github.com/dan-petty/devops-cli/issues/views`) must NEVER be left unlinked or empty during active release development.
    - Never invent ad-hoc status tags or unregistered labels outside `.github/labels.yml` and `.github/project-template.json`.
  - **GitHub API Rate Limit Awareness & Resilient Fallback Mandate**:
    - AI coding assistants interacting with GitHub via `gh` CLI, FastMCP tools, or REST/GraphQL endpoints MUST actively respect GitHub API rate limits. Inspect rate limit allocation proactively via `gh api rate_limit` or response headers (`x-ratelimit-remaining`, `x-ratelimit-reset`).
    - **GraphQL vs REST Fallback Strategy**: GitHub enforces distinct rate limits for REST (5,000 requests/hr) and GraphQL (5,000 points/hr, with query complexity weighting and secondary concurrency limits). If GraphQL queries hit secondary rate limits or quota boundaries, AI agents MUST gracefully fall back to equivalent REST endpoints (`gh api repos/:owner/:repo/...`) rather than failing or crashing.
    - **Strict Ban on Aggressive Polling**: Never execute unthrottled loops or busy-waiting polling commands against GitHub APIs. When waiting for workflow runs, status checks, or deployments, leverage reactive messaging, exponential backoff, or bounded sleep intervals matching reset timestamps (`x-ratelimit-reset`).
    - **Honoring HTTP 429 & Secondary Limits**: When receiving HTTP 429 (`Too Many Requests`) or HTTP 403 (`API rate limit exceeded` / `secondary rate limit`), extract the `Retry-After` header or `x-ratelimit-reset` Unix timestamp, pause requests until the indicated window elapses, and apply randomized jitter to subsequent requests.
  - **FastMCP Agent Project Management & Observability Integration**: AI coding assistants MUST leverage the built-in FastMCP project management tools (`gh_pages_status`, `gh_pages_build`, `gh_pages_verify`, `gh_issue_list`, `gh_issue_create`, `gh_issue_triage`, `gh_issue_status`, `gh_project_list`, `gh_project_status`, `gh_project_audit`, `gh_project_sync`, `gh_views_audit`, `gh_views_sync`, `gh_view_spec`, `gh_milestone_list`, `gh_milestone_sync`, `gh_milestone_close`, `gh_label_list`, `gh_label_sync`), dynamic system resources (`resource://gh/pages/status`, `resource://gh/issues/status`, `resource://gh/project/status`, `resource://gh/views/status`), and CLI equivalents (`devops gh pages`, `devops gh issues`, `devops gh project`, `devops gh views`, `devops gh milestones`, `devops gh labels`) for all project tracking, milestone lifecycle management, pages verification, and taxonomy auditing.

---

## 4. Code Quality & Architectural Standards

- **Separation of Concerns**: Separate configuration, domain logic, data models, network I/O, and user interface layers. Avoid monolithic modules and deep indentation.
- **Purpose-Driven, Functional Naming & Zero Ambiguity**: Use file names, classes, functions, and variables that directly indicate concrete operational purpose (e.g. `reference_extractor.py`, `vulnerability_lookup.py` over abstract names like `common.py`, `helpers.py`, `data.py`, `_config.yaml`). Eliminate duplicative or shadowing names across workspaces, schemas, and configurations. Avoid vague variables (`data`, `temp`, `res2`, `page`) in favor of descriptive domain terms (`review_page_content`, `target_config_path`, `cluster_ollama_endpoints`).
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
- **Clean Test Collection Hygiene & Submodule Test Grouping**: Test helper classes and dummy test models in `src/devops_cli` must declare `__test__ = False` to prevent `PytestCollectionWarning`. Safely await or close coroutine returns. Group tests strictly by submodule and domain functionality matching `src/devops_cli/` rather than creating arbitrary one-off test files.
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
- **AI Inference Rate Limit & Token Budget Management**:
  - Review pipelines and AI agent stages calling local or remote LLMs (Ollama, Anthropic, Gemini, OpenAI) must budget token usage and honor provider rate limits (Tokens-Per-Minute / TPM and Requests-Per-Minute / RPM).
  - Bounded concurrency with semaphores (`asyncio.Semaphore(5)` for 4–8 concurrent workers) prevents overloading inference endpoints.
  - On HTTP 429 or provider overload errors, implement exponential backoff with jitter and retry reflection rather than unthrottled burst retries.
