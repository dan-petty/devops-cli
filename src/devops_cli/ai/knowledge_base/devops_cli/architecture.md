# DevOps CLI Architecture & Subsystem Guide

This document provides foundational context and technical specifications for the internal architecture, engine subsystems, and design patterns of `devops-cli`.

---

## 1. Architectural Philosophy & Principles

The DevOps CLI is designed as an agentic workstation automation platform, unified developer CLI, and multi-persona AI code reviewer built with modern Python 3.14+ runtime capabilities.

```
                     ┌──────────────────────────────────────────────┐
                     │            DevOps CLI Terminal / API         │
                     │          (Typer CLI & FastAPI Server)        │
                     └──────────────────────┬───────────────────────┘
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
   ┌───────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────┐
   │    AI Engine Layer    │   │  Workstation Operations   │   │  Core Foundation      │
   │  - Multi-Persona Rev  │   │  - K8s / Helm / Minikube  │   │  - Settings & Keyring │
   │  - RAG & Vector Store │   │  - OpenTofu / Terraform   │   │  - Output & Dry-Run   │
   │  - LLM Clients/Spans  │   │  - TLS & SSH Crypto Mgmt  │   │  - Language Catalogs  │
   │  - Prompt Tasks (.md) │   │  - Telemetry & Tracing    │   │  - Process Execution  │
   └───────────────────────┘   └───────────────────────────┘   └───────────────────────┘
```

### Core Tenets
1. **Zero Boilerplate & Poetic Conciseness**: Control complexity project-wide (fewer than 6 indentations across all functions). Maximize standard library leverage (`pathlib`, `itertools`, `functools`, `ipaddress`, `urllib.parse`), Pydantic v2 models, and functional pipelines over nested procedural loops.
2. **Zero-Trust Security & Egress Safety**: No plaintext secrets in logs, configs, or public commits. Mandatory OS Keyring for sensitive credentials, SSRF egress validation, and strict subprocess argument list execution.
3. **Pure Markdown Prompt Isolation**: All LLM prompts, task rubrics, and guardrails reside in dedicated `.md` files under `src/devops_cli/ai/tasks/` rather than multi-line inline strings in Python code.
4. **Target-Agnostic Code Analysis**: When inspecting target repositories, path resolution is anchored strictly relative to `target_dir` to prevent host file collisions.
5. **Canonical Location Formatting**: All review findings, table rows, and terminal references follow the `filename.ext:n-n` or `filename.ext:line` convention.

---

## 2. Multi-Persona Code Review Engine & 6-Stage Pipeline

The multi-persona code review pipeline orchestrates specialized AI reviewer personas and static analysis tools across target diffs and workspaces:

```
                          ┌───────────────────────────┐
                          │    Target PR / Git Diff   │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 1: Pre-Analysis Metadata Refresh & Cache Sync              │
    └───────────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 2: Static Security Analyzers & Dependency Probing           │
    │   (Bandit, KubeLinter, Pluto, Semgrep, Gitleaks, OSV, Shodan)    │
    └───────────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 3: Multi-Persona LLM Inspection (Concurrent Workers)        │
    │   (DevSecOps, Architect, QA, Auditor, PM)                        │
    └───────────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 4: Cross-Referencing Verification & Multi-Agent Debate (MAD)│
    │   (Step-by-step evidence tracing against visible source & AST)   │
    └───────────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 5: Finding Re-Ranking & Severity Deduplication             │
    └───────────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │ Stage 6: Consolidated Markdown Report & JSON Payload Export      │
    │   (review.md, findings.json, Rich Terminal Table)                 │
    └───────────────────────────────────────────────────────────────────┘
```

### Review Stage Feature Flags
Every stage in the review pipeline can be selectively enabled or bypassed via CLI feature flags:
- `--no-pre-analysis` / `--pre-analysis-only`: Stage 1 control.
- `--no-static-scan` / `--static-scan-only`: Stage 2 control (runs concurrent static tools only in ~2s).
- `--no-persona-review` / `--persona-review-only`: Stage 3 control.
- `--no-verification` / `--verification-only`: Stage 4 control.
- `--no-reranking` / `--reranking-only`: Stage 5 control.
- `--no-reporting` / `--reporting-only`: Stage 6 control.

### Review Personas
- **`devsecops`**: Zero-Trust security, credential exposure, dependency CVEs, SAST rules (Bandit/Trivy), injection vulnerabilities.
- **`architect`**: Separation of concerns, indentation limits, functional naming, standard library leverage, system scalability.
- **`pm`**: Product scope alignment, user experience, documentation freshness, release readiness.
- **`auditor`**: Compliance, license integrity, regulatory hygiene, audit trail logging.
- **`qa`**: Deterministic test isolation, edge-case coverage, mock boundaries, flaky test mitigation.

---

## 3. Subsystem Architecture

### Configuration & Keyring (`devops_cli.config`)
- Declarative Pydantic v2 `Settings` with dot-notated access (`devops config get/set`).
- Dual-tier storage: Plaintext non-sensitive properties in `~/.config/devops-cli/config.json`, encrypted secrets (tokens, API keys) stored securely via OS `keyring`.
- Secret audit tooling: `devops config audit-keys` verifies that zero unencrypted secrets exist in plaintext config files.

### Dedicated Agent Workspace Data Isolation (`DEVOPS_CLI_DATA_DIR=./.data/agent`)
- AI review agents and test automation runs configure `DEVOPS_CLI_DATA_DIR=./.data/agent` to isolate agent-generated reviews, logs, traces, and metadata from primary user workspace data.

### Output & Dry-Run Subsystem (`devops_cli.output` & `devops_cli.dry_run`)
- Centralized terminal rendering using Rich (`print_success`, `print_error`, `print_info`, `print_table`, `print_muted`).
- Unified dry-run execution: `is_dry_run()`, `set_dry_run(bool)`, `print_dry_run_command()`, `print_dry_run_result()`, and `render_dry_run_result()` returning structured `CommandDryRunResult` models.

### Response Repair & Thought Stream Processing (`devops_cli.ai.response_repair`)
- Resilient JSON parsing and automatic schema recovery via `repair_json_string` and `fix_llm_response`.
- Specialized reasoning model support (`ThinkingStreamProcessor`) parsing `<think>...</think>` tags cleanly while extracting structured output payloads.

### Localized Language Catalog (`devops_cli.lang`)
- Centralized, immutable Pydantic language catalog (`MESSAGES`, `HELP`, `PERSONAS_CONFIG`) under `devops_cli.lang.en.messages`.
- Zero raw user-facing string literals in command dispatchers.

### Observability & Distributed Tracing (`devops_cli.telemetry`)
- OpenTelemetry instrumentation with W3C `TRACEPARENT` propagation across subprocesses and HTTP clients.
- Granular child span tracking (`@trace_span`) for LLM requests (Time to First Token, token latency) and in-memory Prometheus metrics via `GLOBAL_METRICS`.
