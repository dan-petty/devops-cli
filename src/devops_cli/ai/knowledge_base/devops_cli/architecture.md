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

## 2. Multi-Persona Code Review Engine

The multi-persona code review pipeline orchestrates specialized AI reviewer personas across target diffs and workspaces:

```
                          ┌───────────────────────────┐
                          │    Target PR / Git Diff   │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │  AST Chunking & Context   │
                          │   (Paginator / Chunker)   │
                          └─────────────┬─────────────┘
                                        │
             ┌──────────────┬───────────┴───────────┬──────────────┐
             ▼              ▼                       ▼              ▼
     ┌──────────────┐┌──────────────┐       ┌──────────────┐┌──────────────┐
     │  Architect   ││  DevSecOps   │  ...  │   Auditor    ││      QA      │
     └───────┬──────┘└──────┬───────┘       └──────┬───────┘└──────┬───────┘
             │              │                       │              │
             └──────────────┼───────────────────────┴──────────────┘
                            ▼
     ┌─────────────────────────────────────────────────────────────┐
     │         Cross-Persona Verification & Invalidation           │
     │           (RAG Grounding & AST Calibrated Scores)           │
     └──────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
     ┌─────────────────────────────────────────────────────────────┐
     │      ReviewSessionPayload / findings.json / Rich Table      │
     └─────────────────────────────────────────────────────────────┘
```

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
- Dual-tier storage: Plaintext non-sensitive properties in `~/.config/devops-cli/config.json`, encrypted secrets (tokens, API keys) stored securely via `keyring`.

### Output & Dry-Run Subsystem (`devops_cli.output` & `devops_cli.dry_run`)
- Centralized terminal rendering using Rich (`print_success`, `print_error`, `print_info`, `print_table`, `print_muted`).
- Unified dry-run execution: `is_dry_run()`, `set_dry_run(bool)`, `print_dry_run_command()`, `print_dry_run_result()`, and `render_dry_run_result()` returning structured `CommandDryRunResult` models.

### Localized Language Catalog (`devops_cli.lang`)
- Centralized, immutable Pydantic language catalog (`MESSAGES`, `HELP`, `PERSONAS_CONFIG`) under `devops_cli.lang.en.messages`.
- Zero raw user-facing string literals in command dispatchers.

### Observability & Distributed Tracing (`devops_cli.telemetry`)
- OpenTelemetry instrumentation with W3C `TRACEPARENT` propagation across subprocesses and HTTP clients.
- Child span tracking for LLM requests (Time to First Token, token latency) and Prometheus metrics scraping.
