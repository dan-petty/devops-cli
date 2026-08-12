# Strategic Roadmap — devops-cli

High-density product roadmap for `devops-cli`.

## Core Vision & Design Principles
1. **Workstation-Native DevContainer First**: Native to local Dev Container workstation environments with Python 3.14+ and `uv`.
2. **Zero-Plaintext Secret Isolation**: Mandatory OS Keyring integration (`keyring`) for tokens (`github`, `grafana`, `argocd`, `ai`).
3. **SSRF-Defended AI Integrations**: Multi-provider LLM client (`ollama`, `claude`, `copilot`, `openai`) with private-network egress guards (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).
4. **Auditable AI Code Reviews**: Multi-persona reviews (`devsecops`, `architect`, `pm`, `auditor`, `qa`) with static metadata extraction (`SegmentMeta`), prompt isolation guardrails, and finding verification loops.

---

## Phased Milestones

### Phase 1: Core Foundation & Modernization (Completed)
- [x] Python 3.14+ runtime with `uv` virtual environment management.
- [x] OS Keyring integration for zero-plaintext secret storage.
- [x] Multi-persona code review engine with diff pagination (`devops review branch|pr|path`).
- [x] Infrastructure subcommands: `repos`, `ssh`, `k8s`, `kustomize`, `argo`, `grafana`, `prometheus`, `docker`, `workspace`, `install-tools`, `config`, `ci`, `branches`, `devcontainer`, `uv`.
- [x] `devops ci` unified quality gate (pytest, ruff check, ruff format, strict mypy).

### Phase 2: Finding Verification, Metadata Analysis & Dry-Run Models (v0.1.0 - Completed)
- [x] Finding inspection & human invalidation CLI (`devops review findings`, `devops review verify`, `devops review stats`).
- [x] Codebase metadata analysis command (`devops ai analyze [path|branch|pr]`) producing `.data/analysis/*-metadata.json`.
- [x] Pydantic model response outputs for all `--dry-run` subcommands (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- [x] Modular `devops_cli.dry_run` submodule package (`state.py`, `models.py`).
- [x] Dependency vulnerability scanner (`devops ci audit` via `uv audit`) and `UV_MALWARE_CHECK=1` devcontainer integration.
- [x] Python 3.14 exception syntax standardization (`except (Err1, Err2):`) and centralized `LanguageCatalog` literal management.

### Phase 3: Line-Level PR Comments & Custom Personas (v0.1.1 - Completed)
- [x] **Line-Level GitHub PR Inline Comments**: Post persona review findings directly to PR diff line hunks via GitHub API (`create_pr_review_comment`).
- [x] **Human Invalidation Feedback Exporter**: Export invalidated findings (`status="INVALIDATED"`) as benchmark JSONL datasets for prompt tuning (`devops ai review export-feedback`).
- [x] **Custom Team Personas**: Repository-level `.devops/personas/<name>.md` prompt overrides allowing custom reviewer personas.
- [x] **Headless CI Keyring Fallback Auth**: Memory token loading (`devops config auth-headless`) for headless CI environments lacking DBus.
- [x] **v0.1.1 Feature Flags**: Config options (`FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, `FEATURE_HEADLESS_AUTH`).

### Phase 4: Kubeconfig Contexts & SIEM Audit Logging (v0.1.2 - Completed)
- [x] **Multi-Cluster Kubeconfig Management**: Context switching (`devops k8s switch-context <name>`) with namespace controls.
- [x] **SIEM Audit Trail Logging**: Execution logging (`AuditLogger`) streaming to `.data/logs/audit.jsonl` or Syslog.
- [x] **Automated Code Patch Application Prep**: Staging suggested LLM code fixes (`devops ai review apply-patch`).
- [x] **Expanded Subcommand Dry-Run Models**: Pydantic `CommandDryRunResult` models across `argo`, `grafana`, `prometheus`, `devcontainer`.

### Phase 6: Default AI Metadata Analysis & Submodule Scanners (v0.1.4 - Completed)
- [x] **Default Enhanced Analysis**: Default `--enhanced` metadata generation (pseudocode outlines, complexity, ISO `last_analyzed` timestamps).
- [x] **Incremental Analysis Caching**: Skip redundant LLM calls on unchanged files (`st_mtime <= last_analyzed`), with `--update-all` bypass flag.
- [x] **Submodule-Aware Dependency Scanner**: Preserve full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`).
- [x] **Clean Pseudocode Generation**: Eliminate canned template language and strictly exclude import statements from pseudocode outlines.

---

## Value vs. Effort Prioritization Matrix

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | Input Sanitization & Path Traversal Guards | High | Low | ✅ Completed |
| | Human Finding Verification CLI & Accuracy Stats | High | Low | ✅ Completed |
| | Deterministic Static Segment Metadata (`SegmentMeta`) | High | Low | ✅ Completed |
| | Prompt Isolation Guardrails & Tag Sanitization | High | Low | ✅ Completed |
| | `devops config output` Env Var Spec Command | High | Low | ✅ Completed |
| **Strategic Investments** | Line-Level GitHub PR Inline Comments | High | High | 🔄 Short-Term (Q3 2026) |
| | Human Feedback Dataset Exporter | High | Medium | 🔄 Short-Term (Q3 2026) |
| | Custom Team Persona Overrides (`.devops/personas/`) | High | Medium | 🔄 Short-Term (Q3 2026) |
| **Fill-ins** | Non-Interactive GitHub CLI Timeout Config | Medium | Low | ℹ️ Mitigated via Env Var |
| | Ephemeral Headless Keyring Auth | Medium | Medium | 🔄 Mid-Term (Q4 2026) |
| **De-prioritized** | Bare-Metal OS Installers | Low | High | ❌ Rejected (Devcontainer native) |
