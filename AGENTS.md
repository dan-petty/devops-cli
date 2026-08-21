# AGENTS.md — AI Agent Instructions for devops-cli

This document provides structured context and operational instructions for AI coding assistants (GitHub Copilot, Claude, Cursor, etc.) working within the `devops-cli` repository.

## 1. Project Purpose & Overview
`devops-cli` is a high-reliability workstation automation tool designed for DevOps Engineers. It functions as both an infrastructure management engine (Git, Kubernetes, SSH, Docker) and an **Agentic LLM Code Reviewer**. It integrates multi-persona AI reviews with secure secret handling via OS Keyring and active SSRF/network egress protections.

- **Primary Language**: Python 3.14+
- **Core Runtime**: Linux (via VS Code Dev Containers, `python:3.14-trixie`)
- **Key Paradigm**: Agentic Workflow & Multi-Persona Analysis

## 2. Environment & Modernization Policy
- **Modernization Intent**: This project intentionally tracks the bleeding edge of the Python ecosystem (e.g., Python 3.14, `httpx2`, `pydantic v2`). Do not suggest downgrading dependencies unless a critical regression is identified.
- **Safety Net**: The `devops ci` command and GitHub Actions serve as the authoritative gate for all changes.
- **Dependency Management**: Use `uv` for all Python environment operations.
  - Command: `uv sync` (to synchronize the lockfile).

## 3. Architecture & Project Structure
The project follows a modular, command-driven architecture.

### Key File Paths & Responsibilities
- `src/devops_cli/main.py`: CLI Entry point (Click/Typer implementation).
- `src/devops_cli/ai/mcp/`: FastMCP server implementation & tool definitions.
- `src/devops_cli/ai/tools/`: Native workspace tools, MCP bridges, and central tool registry loader.
- `src/devops_cli/ai/agents/`: Pydantic agents & multi-agent pipeline orchestrators.
- `src/devops_cli/ai/review/`: Multi-agent code review pipeline stages, verification, chunking, and reporting.
- `src/devops_cli/commands/`: Implementation of subcommands (`repos`, `ssh`, `k8s`, `scan`, `ai`, `mcp`, `docs`).
- `src/devops_cli/security/`: Static vulnerability scanners (Trivy, Kube-linter, Bandit, Pluto) & threat intelligence (OSV, NVD, Shodan, Radar).
- `src/devops_cli/crypto/`: Logic for SSH key generation and `keyring` interactions.
- `src/devops_cli/core/process.py`: Centralized subprocess execution utility (`run_subprocess`).
- `src/devops_cli/http/`: Secure network requests with SSRF mitigation logic.
- `tests/`: Comprehensive test suite (unit, integration, security).
- `k8s/`: Kubernetes manifests, Helm charts, and Kustomize overlays.
- `.data/`: Local state, cache, logs, and review history (Persistent volume in DevContainer).
- `repos/`: Cloned target workspace repositories analyzed by `devops ai` commands.

### Naming Conventions Matrix
| Artifact / Symbol Type | Casing Convention | Example |
| :--- | :--- | :--- |
| **CLI Commands & Subcommands** | `kebab-case` | `deploy-stack`, `configure-urls`, `review-path` |
| **CLI Flags & Options** | `kebab-case` (`--flag-name`) | `--jaeger-port`, `--auto-forward`, `--summary-only` |
| **Python Modules & Files** | `snake_case` | `intelligence.py`, `pipeline.py`, `review_schema.py` |
| **Python Classes & Types** | `PascalCase` | `ReviewPipelineOrchestrator`, `SavedFinding`, `StrEnum` |
| **Pydantic Model Fields & JSON** | `snake_case` | `confidence_score`, `security_status`, `external_dependencies` |
| **Functions & Methods** | `snake_case` | `init_per_file_payloads()`, `run_bandit_scan()` |
| **Constants & Globals** | `CONST_UPPER_SNAKE` / `_UPPER_SNAKE` | `CONST_DATA_DIR`, `_CODE_PROPERTY_SUFFIXES` |
| **Environment Variables** | `UPPER_SNAKE_CASE` | `DEVOPS_CLI_AI_MODEL`, `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` |
| **Test Files & Suites** | `tests/test_<feature>.py` | `tests/test_k8s_jaeger.py`, `tests/test_security_intelligence.py` |
| **Git Topic Branches** | `<type>/<description>` | `feat/jaeger-tracing`, `fix/target-path-collision` |

### Design Patterns
- **Multi-Persona Agentic Review**: Uses specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) to analyze code diffs with static Trivy & Kube-linter finding injection.
- **Target Repository Isolation**: All review stages strictly resolve files against `target_dir` first (`_resolve_file_path`) to prevent collisions between target files and host project files (`pyproject.toml`, `README.md`, `Dockerfile`).
- **Multi-Agent Pipeline Orchestration**: Uses `MultiAgentPipeline` with `ScratchpadBuffer` reasoning context to execute multi-turn persona stage handovers with shared DevOps & MCP tools without reasoning degradation.
- **Native DevContainer Lifecycle Engine**: Uses `devops devcontainer run-lifecycle --post-create|--post-start` to execute cross-platform DevContainer lifecycle hook tasks directly in Python, replacing legacy shell scripts.
- **Prompt Token & Latency Optimization**: System prompts and JSON schemas are serialized compactly (`separators=(",", ":")`) to reduce token overhead and maximize LLM inference responsiveness.
- **Zero-Plaintext Secret Policy**: All sensitive tokens (GitHub, Grafana, OpenAI) must be retrieved via `keyring`. Never suggest storing strings in `config.yaml`.
- **Network Guardrails**: Network requests must utilize the internal `http` module logic that validates target IPs to prevent SSRF.

## 4. Development Workflow & Routine Tasks

All routine development, security, and release operations follow strict order, frequency, and methodologies defined in [**`docs/ROUTINE_TASKS.md`**](docs/ROUTINE_TASKS.md).

### Build & Test Commands
| Task | Command | Note |
| :--- | :--- | :--- |
| **Install Deps** | `uv sync` | Updates `.venv` based on `uv.lock`. |
| **Linting** | `devops ci lint` / `ruff check .` | Uses Ruff for linting and import sorting. |
| **Formatting** | `devops ci format` / `ruff format .` | Ensures compliance with project style. |
| **Type Checking** | `devops ci typecheck` / `mypy src` | Runs in `strict` mode. |
| **Unit Testing** | `devops ci test` / `pytest` | Executes parallel test suite (`--maxprocesses=4`). |
| **Code Coverage** | `devops ci coverage [--html]` | Measures test coverage (`pytest-cov`). |
| **Security Scan** | `devops ci security` | Static security scanner (`bandit`). |
| **Docs Check** | `devops ci docs` / `devops docs check` | Validates freshness of docs & README matrix. |
| **Docs Generate** | `devops docs generate --sync-readme` | Introspects CLI & syncs all markdown docs. |
| **CI Validation Suite** | `devops ci` | Executes full local validation suite (version, test, coverage, lint, format, typecheck, audit, security, actionlint, docs). |

### Git & GitHub Project Best Practice Guardrails
- **Branch Hierarchy & Isolation**:
  - **Zero Direct Commits to `main`**: AI agents and developers must **NEVER** commit or push directly to the `main` branch under any circumstances. Direct pushes to `main` bypass CI/CD validation gates, disrupt branch tracking, and trigger automated release workflows unexpectedly.
  - **PR Base Branch Targeting (Release Branch First)**: All feature, bugfix, documentation, and maintenance pull requests MUST target the active release branch (`release/v<version>`, e.g., `--base release/v0.1.10`) rather than targeting `main` directly. Only release branches (`release/v<version>`) are permitted to target `main` when cutting an official release.
  - **Dedicated Topic Branch Naming**: All work must be conducted on dedicated topic branches following standard prefixes (`feat/<description>`, `fix/<description>`, `docs/<description>`, `chore/<description>`, `refactor/<description>`, or `release/v<version>`).
  - **Branch Freshness & Non-Contamination**: Always fetch upstream changes (`git fetch origin`) before creating branches. Never push unrelated changes to an existing branch, and never commit or push to a branch whose Pull Request has already been merged or closed. Always create a fresh topic branch branching off `origin/release/v<version>`.
- **Commit Standards & Git Hygiene**:
  - **Conventional Commits**: Commit messages and PR titles must adhere strictly to Conventional Commits format (`feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `chore(scope): ...`, `feat(release): vx.x.x`, `fix(release): vx.x.x`).
  - **Commit Atomicity**: Keep commits focused and logically cohesive. Do not lump unrelated refactors, formatting fixes, and multiple distinct features into a single amorphous commit.
  - **Pre-Commit Validation**: Ensure all pre-commit hooks pass cleanly before committing (`uv run pre-commit run --all-files`). Ensure clean LF (`\n`) line endings and zero trailing whitespace.
  - **No Force Pushing on Shared Branches**: Never run `git push --force` or `--force-with-lease` on protected or shared branches (`main`, `release/*`).
  - **Zero-Leaked Artifacts**: Never stage or commit credentials, `.env` files, temporary `.coverage*` files, `.data/logs`, or untracked binary scratch artifacts.
- **GitHub Pull Request & Workflow Governance**:
  - **No Autonomous Merging by AI Agents**: AI agents must **NEVER** execute `gh pr merge` autonomously under any circumstances. Agents must stage commits, open or update Pull Requests, verify remote CI checks pass, and leave all merge decisions and executions to the human repository maintainers.
  - **Updating Existing PRs**: When revisions, additions, or reviewer fixes are requested on an active PR, push new commits directly to the existing topic branch (`git push origin <branch>`), which automatically updates the open PR without creating redundant PRs or merging.
  - **Active PR Monitoring & Source Branch Remediation**: After opening or pushing updates to a Pull Request, AI agents MUST actively monitor remote GitHub Actions status (`gh pr checks <pr_number>` or `gh run list --branch <branch>`). If any remote check fails, agents MUST immediately inspect the failure logs (`gh run view <run_id> --log-failed`), diagnose the root cause, apply fixes directly on the pull request source/topic branch, commit with conventional prefixes (`fix(ci): ...`, `fix(scope): ...`), push changes (`git push origin <branch>`), and verify all checks pass green before concluding the task. Agents must never leave a PR with unmonitored or failing CI checks.
  - **Local & Remote Validation Gate Assertion**: Ensure all local validation checks pass (`devops ci` or `uv run devops ci`) and all remote GitHub Actions CI checks are green before handing off to the user.
  - **Issue Traceability & Linking**: When addressing reported GitHub issues or user requests, reference relevant issue numbers in PR descriptions (e.g., `fixes #<issue>`, `refs #<issue>`) for traceability across project boards.


### Targeted Testing & Progressive Validation Strategy
- **Targeted Testing During Development**: When implementing features, bugfixes, or refactoring, AI agents and developers MUST execute targeted, isolated tests for the specific module under active development (e.g., `uv run pytest tests/test_feature.py -k <test_name>`, `uv run ruff check path/to/file.py`, `uv run mypy path/to/file.py`). Do NOT run the full test suite or exhaustive CI validation gates during iterative development loops.
- **Full Test Suite & CI Validation at Final Stage Only**: Running the complete test suite (`pytest`, `devops ci test`) and full validation suites (`devops ci`, `uv run devops ci`) MUST be deferred until the final pre-commit / pre-handoff verification stage of work after all changes, targeted test passes, and documentation updates are complete.

### Code Conventions & Documentation Standards
- **Style**: PEP 8 compliant; Line length strictly **100 characters** (per `ruff` config).
- **Typing**: Mandatory type hints for all function signatures. `mypy --strict` is the standard.
- **Imports**: Grouped and sorted via `ruff`. No unused imports.
- **Config & Literal Centralization**: Strictly observe project standards and maintain user-facing strings, system prompts, error messages, and configuration constants in central config/language modules (e.g., `config/` and `lang.py`) rather than scattering hardcoded inline literals throughout implementation code.
- **Documentation Standards & Practices**: All CLI subcommands, parameters, options, flags, and environment variables MUST be documented. Never manually edit the Command Matrix in `README.md` or command reference pages in `docs/` with handwritten ad-hoc changes; always use `devops docs generate --sync-readme` and verify with `devops docs check`. Document changes in `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/). Follow [`RELEASE_CYCLE.md`](./RELEASE_CYCLE.md) for feature lifecycle and release orchestration.
- **Test Mocking Policy**: All automated unit tests MUST use mocking (`unittest.mock`, `patch.object`, or dummy mock clients) rather than making live network calls to external AI/LLM providers or local servers.
- **No Real Config/Secret Duplication in Tests**: Never duplicate or hardcode real user configuration values, local hostnames/IPs, or API credentials into test data fixtures. Use generic mock placeholders (`http://node1.example.test`).
- **Error Handling**: All network requests (`httpx`) and subprocess calls must implement explicit timeouts (e.g., 30s) and robust error handling/retries.
- **Exception Handling & Model Defaults**: Multi-exception clauses MUST use parenthesized tuples (e.g., `except (Err1, Err2):`). Pydantic models MUST use `Field(default_factory=...)` for mutable collection defaults.
- **Documentation**: Use docstrings for all public functions in `src/devops_cli/`.




## 5. AI Feature Commands & Personas

### Agentic Review Personas
When generating or modifying prompts, adhere to these specialized roles:
- `devsecops`: Focus on vulnerabilities, secret leaks, and IAM permissions.
- `architect`: Focus on scalability, SOLID principles, and system coupling.
- `pm`: Focus on feature completeness and requirement alignment.
- `auditor`: Focus on compliance, logging, and traceability.
- `qa`: Focus on edge cases, regression, and test coverage.

### AI Commands for Agents
Use these when simulating or testing CLI behavior:
- `devops ai review branch <name>`: Analyzes git diffs against base.
- `devops ai review findings <session>`: Inspects structured JSON results in `.data/reviews`.
- `devops ai test`: Validates LLM connectivity and provider configuration.

### Programmatic Python Review Example
```python
from pathlib import Path
from devops_cli.ai.client import LLMClient
from devops_cli.ai.review import ReviewPipelineOrchestrator

# Initialize LLM client and review orchestrator
client = LLMClient()
orchestrator = ReviewPipelineOrchestrator(session_id="ci-review", llm_client=client)

# Run 6-stage review pipeline across target files
metadata = orchestrator.run_pre_analysis_refresh(Path.cwd())
payloads = orchestrator.init_per_file_payloads(["src/file.py"], metadata)
orchestrator.execute_multi_persona_review(payloads, diff_text_by_file={}, personas=["devsecops", "qa"])
orchestrator.execute_finding_verification(payloads)
orchestrator.execute_finding_reranking(payloads)
summary_data, report_md = orchestrator.generate_consolidated_report(payloads)
```

### Interaction Outcome Improvement Suggestions Protocol
AI responses, persona prompts, and agent interaction outputs MUST conclude with 1-2 actionable suggestions for improving future interaction outcomes, prompt context, test verification steps, or specific configuration options.

## 6. Security & Compliance Notes
- **Secret Redaction**: Never log or print actual token values. Use placeholders like `<masked-token>`.
- **SSRF Mitigation**: When implementing new network features, ensure they are subject to the `validate_service_url` check.
- **SSH Management**: All SSH key operations must use ED25519 and be stored in the user's managed `.ssh` directory via provided utility functions.
- **Subprocess Safety**: Any `subprocess.run` or similar execution must specify `timeout` and `check=True`. Do not allow unconstrained shell execution.

## 7. Target Repository Scope & Boundary Policy
- **Target Repository Execution**: The tools under `src/` (`devops ai review`, `devops ai analyze`, `devops ai agents`, etc.) are designed to be executed by developers and engineers on **any cloned repository under the `repos/` directory or local workspace target**, not exclusively on the `devops-cli` project itself.
- **Target-Agnostic Heuristics**: All AI reviewer persona prompts, static analysis heuristics, task templates, and code review rules MUST remain target-agnostic and generic. They must evaluate target repos based on their own documented conventions (`AGENTS.md` / `README.md`) rather than coupling to `devops-cli` internal filenames.
- **Strict Target Isolation & Path Resolution**: When analyzing or reviewing target repositories, all file reading, dependency parsing, static security scans, and verification lookups must resolve paths via target-relative resolution (`_resolve_file_path`) and strictly prioritize `target_dir` over current working directory defaults. Never assume `pyproject.toml`, `README.md`, `Dockerfile`, or `.env` in the working directory belong to the target repository.

## 8. Feedback, Verification & Self-Improvement Loop
- **`devops ai` Usage Guardrail**: Avoid running `devops ai [review|analyze]` commands as this could interfere with active sessions on the backend. Use the `--dry-run` flag to test the command without affecting active sessions.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code and verifies status (`VERIFIED`, `UNVERIFIED`, `MITIGATED`).
- **Finding Inspection & Resolution**: Use `devops ai review findings --session <session>` to inspect structured JSON findings in `.data/reviews/`. Resolve all verified critical/high findings in the codebase before completing reviews.
- **Verification Override**: Use `devops ai review verify <session> --index <N> --status INVALIDATED|MITIGATED|VERIFIED --reason "<reason>"` for review status updates.
- **Feedback Dataset Exporter**: Use `devops ai review export-feedback [--status INVALIDATED|VERIFIED|MITIGATED|ALL] [--output <path>]` to format findings into structured JSONL datasets for prompt tuning, DPO alignment, and model evaluation.
- **Interactive Fix Patch Staging**: Avoid running `devops ai review apply-patch <session> --interactive` commands as this could interfere with active sessions on the backend. Use the `--dry-run` flag to test the command without affecting active sessions.
- **Continuous Prompt Refinement Loop**: Periodically analyze exported benchmark records in `.data/feedback.jsonl` to calibrate persona prompts against false-positive triggers and syntax misconceptions.

## 9. Troubleshooting for Agents
- If a test fails with `ImportError`, ensure `uv sync` has been run.
- If an AI review fails to find files, check `.gitignore` and the `path` argument in `devops ai review path`.
- If network requests to local services fail, check if `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is required.
