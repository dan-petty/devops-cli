# Active Working Log — devops-cli

Chronological log of refactoring milestones, quality gates, and security enhancements.

---

## Log Entries

### [2026-08-11] Release v0.1.0 & v0.1.1 Planning
- **v0.1.0 Release**: Shipped codebase metadata analysis (`devops ai analyze`), structured Pydantic model dry-run outputs, modular `devops_cli.dry_run` package, `devops ci audit` dependency scanning (`uv audit`), `UV_MALWARE_CHECK=1` devcontainer environment, and centralized `LanguageCatalog` literals.
- **v0.1.1 Implementation Plan**: Formulated roadmap for line-level GitHub PR inline comments (`--post-inline`), human invalidation benchmark exporter (`export-feedback`), repository-level custom team personas (`.devops/personas/`), and headless CI auth fallback (`auth-headless`).
- **Quality Gate**: Executed `devops ci` — 201 passed, ruff lint clean, ruff format clean, strict mypy clean, uv audit clean.

### [2026-08-10] AI Review Prompt Injection Defenses & Boundary Sanitization
- **Tag Sanitization**: Implemented `_sanitize_prompt_boundary_tags()` in `commands/review.py` to escape closing XML tags in reviewed content.
- **Untrusted Input Framing**: Wrapped diffs, source files, segment summaries, excerpts, and findings in XML boundary tags (`<untrusted_code_diff>`, `<target_code_to_review>`, etc.).
- **System Prompt Security Directives**: Added prompt isolation guardrails to `_persona_system_prompt()` and enclosed repo `AGENTS.md` in `<project_conventions_context>` tags.
- **Task Prompt Directives**: Updated `review.md`, `compose.md`, `metadata.md`, and `verify_finding.md` with prompt material and indirect injection guardrails.
- **Quality Gate**: Executed `devops ci` — 148 passed, ruff lint clean, ruff format clean, strict mypy clean.

### [2026-08-10] Environment Variable Specification Command (`devops config output`)
- **Config Output Subcommand**: Added `devops config output` (aliases `env`, `env-vars`) in `commands/config.py` supporting Rich Table, `--export`, and `--json`.
- **Specification Metadata**: Added `EnvVarSpec` and `get_all_env_var_specs()` in `config/env.py` covering all 30 environment variables.
- **Quality Gate**: Executed `devops ci` — 141 passed, ruff lint clean, ruff format clean, strict mypy clean.

### [2026-08-10] DevSecOps Hardening & Fast Static Metadata Extraction
- **Python 2 Remediation**: Fixed legacy `except Err1, Err2:` syntax across 7 files.
- **Path Traversal Guards**: Enforced `_is_safe_workspace_path` across `read_file`, `list_files`, `devops review path`, and `devops workspace add`.
- **Fast Metadata Extraction**: Replaced 34+ sequential LLM network calls with deterministic static analysis (`SegmentMeta`) upfront in <5ms.
- **Quality Gate**: Executed `devops ci` — 136 passed, ruff lint clean, ruff format clean, strict mypy clean.
