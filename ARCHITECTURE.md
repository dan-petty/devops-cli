# System Architecture & Technical Design — devops-cli

This document outlines the architecture, subsystem design, data flow, and security boundaries of `devops-cli`.

---

## 1. High-Level System Architecture

`devops-cli` is architected as a modular infrastructure automation CLI and multi-agent code analysis platform.

```mermaid
flowchart TD
    subgraph UserInterface["User & Agent Interfaces"]
        CLI["CLI Entrypoint (Typer/Click)"]
        MCP["FastMCP Server (Stdio / SSE)"]
        AI_AGENT["AI Reasoning Agents (Pydantic)"]
    end

    subgraph CoreEngine["devops-cli Core Engine"]
        MAIN["Lazy Command Delegator (main.py)"]
        PROCESS["Subprocess Runner with Dry-Run"]
        HTTP_SEC["Secure HTTP Client & SSRF Guard"]
        KEYRING["OS Keyring Secret Store"]
        DOCS_GEN["Dynamic Documentation Engine"]
    end

    subgraph Subsystems["Infrastructure & AI Subsystems"]
        SUB_INFRA["Infra Management (Git, K8s, Docker, SSH, Argo)"]
        SUB_SECOPS["Static Security Scanners (Trivy, Pluto, Popeye, KubeLinter)"]
        SUB_AI_REV["Multi-Persona Code Review Pipeline"]
        SUB_DEVCONTAINER["Python DevContainer Lifecycle Engine"]
        SUB_RELEASE["Release Cycle Automation Engine"]
    end

    CLI --> MAIN
    MCP --> MAIN
    AI_AGENT --> MCP

    MAIN --> SUB_INFRA
    MAIN --> SUB_SECOPS
    MAIN --> SUB_AI_REV
    MAIN --> SUB_DEVCONTAINER
    MAIN --> SUB_RELEASE

    SUB_AI_REV --> HTTP_SEC
    SUB_INFRA --> PROCESS
    SUB_SECOPS --> PROCESS
    SUB_INFRA --> KEYRING
    SUB_AI_REV --> KEYRING
    MAIN --> DOCS_GEN
```

---

## 2. Multi-Persona Code Review Pipeline

The Agentic Code Review engine splits code analysis across specialized domain personas with structured reasoning context and deterministic verification.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / CI
    participant Orch as ReviewPipelineOrchestrator
    participant Meta as Metadata Analyzer
    participant LLM as Multi-Persona LLMs
    participant Verify as Finding Verification Stage
    participant Store as .data/reviews/ Storage

    Dev->>Orch: devops ai review branch <name>
    Orch->>Meta: Pre-analysis scan & AST refresh
    Meta-->>Orch: FileAnalysisMeta payload
    loop For each Persona (devsecops, architect, pm, auditor, qa)
        Orch->>LLM: Multi-turn prompt + diff + ScratchpadBuffer
        LLM-->>Orch: Structured JSON findings (ReviewResult)
    end
    Orch->>Verify: Cross-reference findings against live code AST
    Verify-->>Orch: Verified / Unverified / Mitigated status
    Orch->>Orch: Dynamic Finding Reranking
    Orch->>Store: Save session JSON & Markdown summary
    Orch-->>Dev: Render Rich Review Table & Recommendations
```

### Review Personas & Specializations
- **`devsecops`**: Static vulnerability scanning, secret detection, and IAM least-privilege analysis.
- **`architect`**: Scalability, SOLID design principles, structural coupling, and boundary cohesion.
- **`pm`**: Feature completeness, requirement traceability, and non-functional guarantees.
- **`auditor`**: Compliance, governance, audit trail logging, and regulatory controls.
- **`qa`**: Edge cases, error handling paths, test mocking adherence, and regression risk.

---

## 3. FastMCP Integration & Bridge Architecture

`devops-cli` exposes its complete infrastructure and review capabilities over the **Model Context Protocol (FastMCP)**, enabling seamless integration with external AI IDEs, autonomous subagents, and Claude/Cursor tools.

```mermaid
flowchart LR
    subgraph ExternalAgents["AI Assistants & IDEs"]
        Cursor["Cursor / Copilot"]
        Claude["Claude Desktop / CLI"]
        Subagents["Antigravity / Auto-Agents"]
    end

    subgraph FastMCPServer["devops-cli FastMCP Server"]
        Router["Tool Router (Stdio / SSE)"]
        Bridge["Lazy Loaded Subcommand Bridge"]
        Registry["Tool Registry (25+ DevOps Tools)"]
    end

    ExternalAgents <-->|JSON-RPC| Router
    Router --> Bridge
    Bridge --> Registry
```

---

## 4. Native DevContainer Lifecycle Engine

Replacing fragile bash scripts (`postCreate.sh`, `postStart.sh`), `devops devcontainer run-lifecycle` executes cross-platform Python lifecycle tasks:

```mermaid
flowchart TD
    DC_HOOK["DevContainer Lifecycle Trigger"] --> PY_ENGINE["devops devcontainer run-lifecycle"]

    subgraph PostCreateTasks["Post-Create Stage"]
        T1["Persist Shell History (.data/zsh_history)"]
        T2["Generate Shell Autocompletions"]
        T3["Scaffold .data Directories & Config"]
    end

    subgraph PostStartTasks["Post-Start Stage"]
        T4["Sync Managed SSH Keys & Agent"]
        T5["Apply Git User & Security Defaults"]
        T6["Validate Kubeconfig & Cluster Context"]
        T7["Register FastMCP Server Configuration"]
    end

    PY_ENGINE --> PostCreateTasks
    PY_ENGINE --> PostStartTasks
```

---

## 5. Security & Threat Model

1. **Zero-Plaintext Secret Storage**:
   - Secrets are managed exclusively through OS Keyring (`keyring`), isolating API tokens and credentials from git commits, environment dumps, and config files.
2. **SSRF Guardrails (`validate_service_url`)**:
   - Outbound network requests evaluate resolved IP addresses against RFC 1918, loopback, and cloud metadata ranges to prevent SSRF vulnerabilities.
3. **Safe Subprocess Execution**:
   - All external binary invocations (`git`, `kubectl`, `trivy`, `docker`) use explicit argument arrays with `shell=False` and deterministic timeout boundaries.

---

## 6. SRE Reliability, Observability & Quality Gates

- **Structured Metrics & Telemetry**: Integrates with Prometheus query endpoints (`devops prometheus`) and Grafana dashboards (`devops grafana`) to monitor workstation and cluster health.
- **7-Gate CI Quality Gate**: Automated enforcement of Python 3.14 runtime, Ruff formatting, Mypy strict typing, documentation freshness, test coverage, and static security scanning (`devops ci run`).
- **Release Verification & Introspection**: Built-in release cycle management (`devops release status`, `devops release check`, `devops release tag`) ensures consistent versioning and documentation synchronization across releases.
