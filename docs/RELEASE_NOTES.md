# Release Notes — devops-cli v0.1.0

Workstation-native DevOps CLI for managing repositories, SSH keys, Kubernetes clusters, Kustomize, ArgoCD, Grafana, Prometheus, Docker, workspace files, and multi-persona AI code reviews.

---

## 🚀 Highlights of v0.1.0

### 🤖 Codebase Metadata Analysis & Structured Dry-Run Responses
- **`devops ai analyze [path|branch|pr]`**: Scans project repositories using standard library metadata extraction and dynamic `.gitignore` parsing to generate structured `.data/analysis/*-metadata.json` metadata files.
- **Pydantic Dry-Run Models**: All subcommands in `--dry-run` mode construct and output structured Pydantic model JSON responses (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- **Dedicated `dry_run` Submodule**: Created `src/devops_cli/dry_run/` (`state.py`, `models.py`) for clean environment-backed dry-run state management.

### 🛡️ Vulnerability Audit & DevContainer Security
- **`devops ci audit`**: Added `audit` subcommand running `uv audit` to scan dependencies for known package advisories.
- **`UV_MALWARE_CHECK=1`**: Configured `UV_MALWARE_CHECK=1` in `.devcontainer/devcontainer.json` and `.devcontainer/postCreate.sh`.
- **Target-Agnostic AI Reviewers**: Persona prompts, static analysis heuristics, and review task templates evaluate target repositories under `repos/` based on their own documented conventions (`AGENTS.md` / `README.md`).

### 📦 Multi-Persona AI Code Reviews & Finding Verification
- **Specialized Personas**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`).
- **Prompt Isolation Guardrails**: Boundary tag sanitization (`_sanitize_prompt_boundary_tags`) and XML tag framing isolate untrusted reviewed code from LLM instructions.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code.
- **Centralized Language Catalog**: All user-facing strings and message templates are defined in `src/devops_cli/lang/en.py` (`LanguageCatalog`).

---

## 🛠️ Environment & Requirements
- **Runtime**: Python >=3.14 (managed by `uv`)
- **Container**: VS Code Dev Container / Local workstation environment (`python:3.14-trixie`)
- **Tool Dependencies**: `kubectl`, `helm`, `minikube`, `kustomize`, `docker`, `gh`
