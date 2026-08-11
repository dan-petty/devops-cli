# AGENTS.md — AI Agent Instructions for devops-cli

This document provides structural context, operational constraints, and architectural patterns for AI coding assistants (GitHub Copilot, Claude, Cursor, etc.) working on the `devops-cli` repository.

## 1. Project Essence
**Purpose**: `devops-cli` is an advanced workstation automation tool designed for DevOps Engineers. It provides a unified interface for managing multi-repo Git workflows, Kubernetes/ArgoCD clusters, SSH key lifecycles, and integrating **Agentic LLM Code Reviews**.
- **Primary Language**: Python 3.14+ (Targeting the latest stable/pre-release features).
- **Entry Point**: `devops` (via `src/devops_cli/main.py`).
- **Environment Manager**: `uv` (Standard for dependency resolution and virtual environments).
- **Runtime Environment**: Primarily designed to run within a VS Code Dev Container (`.devcontainer/`).

## s2. Environment & Modernization Policy
**Strict Adherence Required**:
- **Intentionality**: This project uses cutting-edge dependencies (e.g., Python 3.14, `httpx2`, `fastmcp`). Do **NOT** suggest downgrading dependencies to "stable" versions unless a specific breakage is identified.
- **The Source of Truth**: The `pyproject.toml` and `uv.lock` files are the authoritative definitions for the runtime environment. 
- **Quality Gate**: Any change that breaks `devops ci` (the internal quality check command) must be reverted.

## 3. Developer Workflow & Commands
Use these commands to validate changes:
- **Setup/Sync**: `uv sync` (Always run after modifying `pyproject.toml`).
- **Linting**: `ruff check .` (Enforces PEP8, Import sorting, and Modern Python upgrades).
- **Formatting**: `ruff format .` (Standardizes code style).

- **Type Checking**: `mypy src` (Strict mode enabled; all type hints must be accurate).
- **Testing**: `pytest` (Run the full suite).
- **Integration Check**: `devops ci` (Executes a holistic check of lints, types, and core tests).

## 4. Code Conventions & Standards
- **Python Syntax**: Use Python 3.14+ features. Specifically, use parenthesized exception tuples `except (E1, E2):`.
- **Line Length**: Maximum **100 characters** (defined in `ruff` and `.devcontainer`).
- **String Formatting**: Prefer f-strings for all interpolation.
- **Imports**: Use absolute imports from `src.devops_cli`. Follow `ruff`'s `I` (Isort) rules.
- **HTTP Operations**: Use `httpx` for all network requests. Ensure all subprocess calls include an explicit `timeout` parameter (`DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`).
- **Secret Management**: 
    - **NEVER** hardcode tokens, keys, or passwords in source code.
    - **ALWAYS** use the `keyring` integration for sensitive data (e.g., `github.token`, `ai.api_key`).
    - Use `.env` only for non-sensitive configuration overrides.

## 5. Architecture Overview
The project follows a modular command-pattern architecture:

```text
src/devops_cli/
├── ai/             # Agentic LLM logic (LLM providers, prompt templates)
├── commands/       # CLI Subcommand implementations (Click/Typer)
├── config/         # Configuration management (YAML, Keyring integration)
├── core/           # Shared business logic and orchestration
├── crypto/         # SSH key generation and Ed25519 management
├── github/         # GitHub API integrations (PRs, Repos, Users)
├── http/           # Network utilities & SSRF mitigation logic
├── models/         # Pydantic schemas for data validation
└── mcp.py          # Model Context Protocol implementation
```

**Data Persistence**:
- `.data/reviews/`: Stores structured AI review findings and session metadata.
- `.data/logs/`: Stores execution logs for auditing and debugging.

## 6. AI Feature Commands & Personas
When generating or modifying code related to `devops review`, respect the multi-persona paradigm:
- **Available Personas**: `devsecops` (Security), `architect` (Design), `pm` (Product/Logic), `auditor` (Compliance), `qa` (Testing).
- **Key AI Workflows**:
    - `devops review branch`: Analyzing diffs.
    - `devops review verify`: The human-in-the-loop mechanism to validate findings.
    - `devops ai agents`: Command used to regenerate the instructions found in this file and other agent configuration files.

## 7. Security & Network Integrity
- **SSRF Protection**: The `LLMClient` and `validate_service_url()` functions implement a strict egress policy. They refuse connections to private/loopback IP ranges (e.g., `127.0.0.1`, `169.254.x.x`) unless the explicit override `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is present in the environment.
- **Identity**: SSH keys are managed and rotated via the `ssh` command group; do not modify `.ssh` logic without updating the `crypto` module test suite.
- **Credential Exposure**: Do not flag `<masked-*>` placeholders as leaks; these are intentional redactions by our deployment pipeline.
