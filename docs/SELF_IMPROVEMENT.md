# AI Feedback, Review, and Self-Improvement Loop

This document defines the architecture, operational workflows, and engineering conventions governing the DevOps CLI AI Feedback, Review, and Self-Improvement Loop.

---

## 1. Architectural Principles & Objectives

The primary objective of the self-improvement loop is to achieve **continuous, compounding code quality and security resilience** through structured automated feedback, reproducible verification, and historical memory calibration.

### Dual-Loop Architecture

The self-improvement system operates across two complementary timescales:

```mermaid
flowchart TD
    subgraph FastLoop["Fast Feedback Loop (Pre-Commit / PR Lifecycle)"]
        A[Developer / Agent Code Authoring] --> B[devops ci / Local Gates]
        B --> C[devops review / Multi-Persona AI Review]
        C --> D[devops review verify / Automated Verification]
        D --> E{Findings Verified?}
        E -- Yes --> F[Test-First Remediation]
        F --> A
        E -- No / Clean --> G[Pull Request Ready]
    end

    subgraph DeepLoop["Deep Self-Improvement Loop (Cross-Release / Memory)"]
        G --> H[devops review export-feedback]
        H --> I[feedback_dataset.jsonl Calibration]
        I --> J[common_hallucinations.json Updates]
        J --> K[Prompt & Persona Protocol Refinement]
        K --> L[ai_test_gen Regression Suites]
        L --> A
    end
```

1. **Fast Feedback Loop (Synchronous & Per-Branch)**:
   - **Local Quality Gates**: `devops ci` aggregates formatters, linters (`ruff`), static typing (`mypy`), security scanners (`bandit`, `actionlint`), and test suites ($\ge 90\%$ coverage).
   - **Multi-Persona Review Ensemble**: `devops review` synthesizes findings across specialized personas (`devsecops`, `architect`, `qa`, `performance`, `sre`) using a 5-phase chain-of-thought protocol.
   - **Automated Verification**: `devops review verify` evaluates concrete verification criteria against the target repository, automatically filtering out false alarms.
   - **Test-First Remediation**: Verified findings are immediately converted into failing regression tests before implementation code is updated.

2. **Deep Self-Improvement Loop (Asynchronous & Cross-Release)**:
   - **Feedback Export**: `devops review export-feedback` extracts verified findings, false positives, developer overrides, and remediation diffs into structured datasets (`.data/agent/feedback_dataset.jsonl`).
   - **Hallucination Calibration**: Patterns consistently proven false or invalid are incorporated into `common_hallucinations.json`, teaching review models to disarm recurrent false alerts.
   - **Prompt Evolution**: Persona prompts, review instructions (`src/devops_cli/ai/tasks/review.md`), and system guidelines (`AGENTS.md`) are refined to eliminate blind spots and reinforce verified heuristics.
   - **Continuous Regression Guarding**: Remediated defects are converted into enduring invariant checks (`tests/test_architectural_invariants.py`) and domain test suites.

---

## 2. Review Protocol & Persona Guidelines

Review models must follow the **5-Phase Chain-of-Thought Protocol** specified in [`src/devops_cli/ai/tasks/review.md`](../src/devops_cli/ai/tasks/review.md):

### Phase 1: Context & Target Grounding
- Ground evaluations in universal software engineering standards (OWASP Top 10, CIS benchmarks, SOLID, DRY) and target project conventions (`AGENTS.md`, `CLAUDE.md`).
- Respect authoritative lockfiles (`uv.lock`, `package-lock.json`). Never hallucinate CVEs against verified dependencies.
- Distinguish production code from test fixtures, mocks (`tests/`), documentation, or configuration templates (`*.example.*`).

### Phase 2: Semantic & AST Inspection
- **Network Egress & DNS SSRF**: In outbound HTTP requests and web scrapers, verify that both the initial URL and post-redirect response URLs perform DNS resolution and check that all resolved IPs are public (`validate_url_egress`), guarding against DNS rebinding.
- **Path Traversal Containment**: Enforce path parameter validation (`validate_no_path_traversal`) and ensure paths never resolve to forbidden system directories (`is_forbidden_system_path`).
- **HTTP Client Timeouts**: Ensure numeric timeouts configure the `read` timeout (`request_timeout(read=...)`), keeping short connect timeouts to prevent hung connections (CWE-400).
- **Algorithmic Complexity & Memory Bounds**: Bound JSON parsing inputs ($\le 5\text{ MiB}$) and ensure string lengths in exception details are bounded ($\le 256$ chars) with user credentials scrubbed.
- **Architectural Invariants**: Strictly enforce cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.

### Phase 3: Falsification & Anti-Hallucination
- Actively search surrounding guards, upstream sanitizers, and lockfile constraints to disprove candidate findings.
- Cross-reference candidate alerts against `common_hallucinations.json` (e.g. Python 3.14 PEP 758 syntax, masked placeholder tokens, synthetic test fixtures).
- Dismiss theoretical or already-mitigated alerts; prioritize high-signal, reproducible flaws.

### Phase 4: Root Cause & Severity Classification
- Isolate exact failure mechanisms and categorize severity:
  - **CRITICAL**: Exploitable vulnerability, auth bypass, credential leak, SSRF, arbitrary file write outside root, or fatal crash.
  - **HIGH**: Preconditioned vulnerability, data corruption, race condition, unvalidated path write, or resource leak.
  - **MEDIUM**: Bounded flaw, unhandled error state, or incomplete mitigation.
  - **LOW**: Hardening, observability, defense-in-depth, or maintainability improvement.

### Phase 5: Self-Healing Remediation & Verification Synthesis
- Author drop-in replacements (`fix`) resolving the defect cleanly without breaking API contracts.
- Define 1–3 concrete `verification_criteria` proving defect presence and 1–3 `invalidation_criteria` proving defect resolution.

---

## 3. Step-by-Step AI Agent Remediation Workflow

When an AI agent or automated workflow is tasked with addressing review findings, the following sequence is mandatory:

```mermaid
sequenceDiagram
    autonumber
    actor Developer as Developer / User
    participant Agent as AI Agent
    participant GH as GitHub Projects / Issues
    participant Code as Workspace Code & Tests
    participant CI as DevOps CI Pipeline
    participant Memory as Feedback Dataset

    Developer->>Agent: Request review remediation
    Agent->>GH: Bootstrap tracking issue & project card (In Progress)
    Agent->>Code: Read findings.json & review.md
    Agent->>Code: Author failing unit/integration tests (TDD)
    Agent->>Code: Apply clean, surgical code remediation (Complexity <= 10)
    Agent->>Code: Run targeted pytest (verify invalidation criteria)
    Agent->>CI: Run devops ci (all 10 quality gates pass)
    Agent->>Memory: devops review export-feedback (update feedback memory)
    Agent->>GH: Transition card to In Review / Done & close issue
```

### Step 1: Ingest & Categorize Findings
Read `.data/reviews/<session-id>/findings.json` and `review.md`. Group findings by severity (Critical $\rightarrow$ High $\rightarrow$ Medium $\rightarrow$ Low) and target component. Filter for verified findings (`"verified": true` or `"status": "VERIFIED"`).

### Step 2: Ground in GitHub Projects & Issues
Every review remediation task must have an active GitHub Issue and Project Item:
- Author a formal issue (e.g. `gh issue create --title "fix(security): remediate verified review findings" --label "type/security,scope/review,priority/p1-high"`).
- Move the Project card to `In Progress` via `devops gh project sync`.
- Create a dedicated task file under `docs/agent/tasks/task-<issue>-<slug>.md`.

### Step 3: Author Regression Tests First (Living Contract)
Before altering implementation code in `src/`:
- Formulate tests directly mirroring the finding's `verification_criteria` and `invalidation_criteria`.
- Place tests in canonical submodule test files under `tests/` (e.g. `tests/test_common_tools.py`, `tests/test_validation.py`, `tests/test_http.py`). NEVER create temporary one-off test files.
- Ensure mock hostnames strictly use `example.com` (no subdomains).

### Step 4: Implement Surgical Remediation
- Implement clean, minimal fixes satisfying the tests.
- Ruthlessly remove legacy shims or zombie code (zero compatibility debt).
- Enforce cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$. Decompose multi-branch procedures into single-responsibility pure functions.

### Step 5: Verify Invalidation & Run Full CI Suite
- Execute targeted tests: `uv run pytest tests/test_<submodule>.py`.
- Run architectural invariants: `uv run pytest tests/test_architectural_invariants.py`.
- Run full CI quality gate: `devops ci` (or `uv run devops ci`).

### Step 6: Export Feedback & Update Knowledge Memory
- Run `devops review export-feedback` to append the session's findings, verifications, and resolutions to `feedback_dataset.jsonl`.
- If any finding was identified as a false positive, update `src/devops_cli/ai/knowledge_base/common_hallucinations.json`.
- Commit changes atomically: `fix(review): remediate findings and update self-improvement memory (#<issue>)`.

---

## 4. Observability, Telemetry & Key Metrics

The self-improvement loop is monitored via OpenTelemetry distributed tracing and structured Prometheus metrics:

| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `devops_cli_review_sessions_total` | Counter | Total AI review sessions executed. |
| `devops_cli_review_findings_total` | Counter | Total findings identified, labeled by `severity` and `persona`. |
| `devops_cli_review_verified_total` | Counter | Findings verified as true defects by verification criteria. |
| `devops_cli_review_invalidated_total` | Counter | Findings disproven as false alarms by invalidation criteria. |
| `devops_cli_review_feedback_exports_total` | Counter | Feedback records exported to `feedback_dataset.jsonl`. |

Tracing spans decorated with `@trace_span("review.<phase>")` capture execution latency, prompt token counts, and completion budgets across the entire pipeline.
