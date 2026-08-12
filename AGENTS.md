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

### Key File Paths
- `src/devops_cli/main.py`: CLI Entry point (Click/Typer implementation).
- `src/devops_cli/ai/`: Core logic for LLM integration and agent orchestration.
- `src/devops_cli/commands/`: Implementation of all subcommands (`repos`, `ssh`, `k8s`).
- `src/devops_cli/crypto/`: Logic for SSH key generation and `keyring` interactions.
- `src/devops_cli/http/`: Secure network requests with SSRF mitigation logic.
- `tests/`: Comprehensive test suite (unit, integration, security).
- `k8s/`: Kubernetes manifests and Kustomize overlays.
- `.data/`: Local state, logs, and review history (Persistent volume in DevContainer).

### Design Patterns
- **Multi-Persona Agentic Review**: Uses specialized personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) to analyze code diffs.
- **Zero-Plaintext Secret Policy**: All sensitive tokens (GitHub, Grafana, OpenAI) must be retrieved via `keyring`. Never suggest storing strings in `config.yaml`.
- **Network Guardrails**: Network requests must utilize the internal `http` module logic that validates target IPs to prevent SSRF.

## 4. Development Workflow

### Build & Test Commands
| Task | Command | Note |
| :--- | :--- | :--- |
| **Install Deps** | `uv sync` | Updates `.venv` based on `uv.lock`. |
| **Linting** | `ruff check .` | Uses RUFf for linting and import sorting. |
| **Formatting** | `ruff format .` | Ensures compliance with project style. |
| **Type Checking** | `mypy src` | Runs in `strict` mode. |
| **Unit Testing** | `pytest` | Executes the full test suite. |
| **CI Gate** | `devops ci` | Executes the local quality gate (lint + typecheck + test). |

### Code Conventions
- **Style**: PEP 8 compliant; Line length strictly **100 characters** (per `ruff` config).
- **Typing**: Mandatory type hints for all function signatures. `mypy --strict` is the standard.
- **Imports**: Grouped and sorted via `ruff`. No unused imports.
- **Config & Literal Centralization**: Strictly observe project standards and maintain user-facing strings, system prompts, error messages, and configuration constants in central config/language modules (e.g., `config/` and `lang.py`) rather than scattering hardcoded inline literals throughout implementation code.
- **Error Handling**: All network requests (`httpx`) and subprocess calls must implement explicit timeouts (e.g., 30s) and robust error handling/retries.
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

## 8. Feedback, Verification & Self-Improvement Loop
- **`devops ai` Usage Guardrail**: Avoid running `devops ai [review|analyze]` commands as this could interfere with active sessions on the backend. Use the `--dry-run` flag to test the command without affecting active sessions.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code and verifies status (`VERIFIED`, `UNVERIFIED`, `MITIGATED`).
- **Finding Inspection & Resolution**: Use `devops ai review findings --session <session>` to inspect structured JSON findings in `.data/reviews/`. Resolve all verified critical/high findings in the codebase before completing reviews.
- **Verification Override**: Use `devops ai review verify <session> --index <N> --status INVALIDATED|MITIGATED|VERIFIED --reason "<reason>"` for review status updates.
- **Feedback Dataset Exporter**: Use `devops ai review export-feedback` to format invalidated findings into JSONL datasets for prompt tuning.
- **Interactive Fix Patch Staging**: Avoid running `devops ai review apply-patch <session> --interactive` commands as this could interfere with active sessions on the backend. Use the `--dry-run` flag to test the command without affecting active sessions.

## 9. Troubleshooting for Agents
- If a test fails with `ImportError`, ensure `uv sync` has been run.
- If an AI review fails to find files, check `.gitignore` and the `path` argument in `devops ai review path`.
- If network requests to local services fail, check if `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is required.
