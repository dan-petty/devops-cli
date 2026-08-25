# Knowledge Base Task: Multi-Persona AI Code Review

## 1. Overview & Purpose

The Multi-Persona AI Code Review system in `devops-cli` provides automated, high-signal, persona-driven feedback on git diffs, pull requests, and file paths. By leveraging domain-specialized personas (`architect`, `devsecops`, `auditor`, `qa`, `pm`), the review engine analyzes code modifications against universal software engineering principles (SOLID, DRY, OWASP Top 10, CIS benchmarks) as well as the target repository's own declared conventions (`AGENTS.md`).

---

## 2. Architecture & Review Pipeline

```mermaid
graph TD
    A[Git Diff / Target Path / PR] --> B[Diff Token Sizing & Chunking]
    B --> C[Sanitization & Secret Masking]
    C --> D[Multi-Persona Prompt Assembly]
    D --> E[LLM Provider: Ollama / Claude / OpenAI]
    E --> F[Reasoning Stream & Response Repair]
    F --> G[Finding Calibration & Deduplication]
    G --> H[Interactive Terminal Table & Markdown Export]
```

- **Specialized Personas**:
  - `devsecops`: Evaluates CWE vulnerabilities, secret exposures, network egress, and permissions.
  - `architect`: Evaluates SOLID design, coupling, cohesion, module boundaries, and typing.
  - `auditor`: Evaluates compliance, license risks, and log sanitization.
  - `qa`: Evaluates edge cases, exception handling, and test isolation.
  - `pm`: Evaluates documentation sync, changelog updates, and user requirements.
- **Closed-Loop Feedback & Self-Improvement**:
  - `verify_finding`: Tests observable verification and invalidation criteria against visible code and AST structures to eliminate false positives.
  - **Confidence Calibration**: Weighs findings based on concrete criteria satisfaction, discarding unverified or mitigated items.
  - **Lockfile-Aware Dependency Scanning**: Resolves exact package releases from lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) before querying OSV.dev and NVD vulnerability databases.
  - **Network Reference Disambiguation**: Differentiates legitimate network endpoints from source file extensions (`*.py`, `*.md`, `*.sh`, `*.tf`, `*.rs`, `*.pid`) and telemetry/code property paths (`service.name`, `ci.step.*`, `host.name`, `process.pid`).
  - **Self-Healing & Patch Application**: Generates drop-in remediation code patches that can be applied and verified against automated CI quality gates.
  - **Continuous Knowledge Feedback**: Synthesizes recurrent review findings into repository architecture guides and test fixtures to prevent recurrence.

---

## 3. Useful Usage Information & Common Commands

### Review Commands
```bash
# Review active working directory git diff (staged + unstaged)
devops review branch

# Review an entire target path or child repository
devops review path repos/my-org/my-project

# Review a specific GitHub pull request by number
devops review pr 17

# Review using a specific persona and provider
devops review branch --persona devsecops --provider ollama --model qwen2.5-coder:14b

# Export review report to markdown
devops review branch --export-md .data/reviews/review-report.md
```

---

## 4. Best Practice Guidance

1. **Review Small, Atomic Diffs**: Run reviews iteratively on focused commits to maximize AI context focus and receive higher-signal feedback.
2. **Target Path Isolation**: When reviewing child workspaces (under `repos/`), always ensure file paths resolve relative to `target_dir` to prevent host file collisions.
3. **Declare Project Conventions**: Maintain an accurate `AGENTS.md` file in target repositories; the review engine automatically injects it into prompt context.
4. **Use Response Repair**: The review pipeline automatically normalizes LLM outputs using `repair_json_string` and `fix_llm_response` to ensure valid structured schemas.
5. **Context-Aware Documentation & Avoidance Context**: Never flag documentation, architectural guides, security tutorials, or prompt tasks that explain known vulnerabilities or insecure configurations in the context of avoiding, preventing, or mitigating them.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Secret Masking & Path Filtering**: All diffs and source excerpts pass through `_mask_secrets_in_content` before transmission to LLM providers. Secret-containing paths (`.env*`, `.pem`, `*.key`, `*secret*`) are excluded from validation prompt injection.
- **Prompt Injection Defense**: Boundary closing tags and diff titles are escaped to prevent prompt manipulation.
- **Path Traversal Protection**: Directory traversal routines strictly enforce repository boundaries and skip symlinked files.
- **Offline Review Option**: For proprietary or air-gapped environments, use `--provider ollama` to keep all code analysis strictly on the local machine.

---

## 6. General Standards & Output Schemas

- **Finding Severity**: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.
- **Finding Model**: Structured Pydantic model (`ReviewFinding`) with `id`, `file_path`, `line_start`, `line_end`, `persona`, `severity`, `title`, `description`, `remediation`, and `confidence`.

---

## 7. Official References & Published Artifacts

- **DevOps CLI Repository**: [github.com/dan-petty/devops-cli](https://github.com/dan-petty/devops-cli)
- **Review Pipeline Engine**: [src/devops_cli/ai/review.py](../../review/)
- **Persona Prompt Task Definitions**: [src/devops_cli/ai/tasks/](../../../ai/tasks/)
