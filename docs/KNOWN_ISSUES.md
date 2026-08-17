# Known Issues & Operational Policy — devops-cli

Captures operational edge cases, intentional design trade-offs, and mitigations in `devops-cli`.

---

## Operational Issues & Mitigations

### 1. Non-Interactive GitHub CLI Authentication Timeout
- **Context**: `subprocess.run(["gh", "auth", "token"])` executes with a 5s timeout. If corporate SSO gateways require interactive browser auth, `gh` times out.
- **Mitigation**: Execute `gh auth login` in terminal prior to `devops` commands, or set `DEVOPS_CLI_GH_CLI_TIMEOUT=15`.

### 2. Egress Controls for Internal Service URLs (SSRF Safety)
- **Context**: `validate_service_url()` blocks loopback/private IP targets by default to prevent SSRF vulnerabilities. Connecting to internal cluster endpoints (Ollama, ArgoCD, Grafana) raises `ValueError`.
- **Mitigation**: Set `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` in environment or devcontainer.

### 3. Large Workspace Iteration Bounds
- **Context**: Scanning workspace repositories or directories with nested symlinks can increase pagination latency.
- **Mitigation**: `review.py` and `iter_workspace_repos()` enforce path bounds and skip ignored paths via `git ls-files` and `.gitignore` filtering.

### 4. Optional SDK Dependency Imports
- **Context**: `devops k8s` and `devops docker` rely on optional `kubernetes` and `docker` SDKs. Missing packages raise clear error messages.
- **Mitigation**: Run `uv sync` inside Dev Container to install all optional dependencies in `pyproject.toml`.

### 5. Local Workstation vs Production Container Model
- **Context**: Designed specifically for local DevOps workstations. Uses high timeouts (`DEFAULT_REVIEW_TIMEOUT_SECONDS = 3600.0`) for CPU/GPU Ollama, bind-mounts host `~/.ssh` into `.devcontainer` for key rotation and SSH agent usage, and uses OS keyring for secret isolation. Direct bind mounts of host SSH configuration serve developer convenience in local dev environments.
- **Mitigation**: Defer to Environment & Modernization Policy in `AGENTS.md`. High workstation timeouts and host SSH mounts are accepted design trade-offs for local devcontainers.

### 6. SSH Host Key Scanning (ssh-keyscan) Fingerprint Verification
- **Context**: `_ensure_known_host()` uses `ssh-keyscan` to automatically retrieve public SSH host keys during initial clone operations. Without pre-configured host fingerprints, initial trust-on-first-use occurs over the network.
- **Mitigation**: Pre-populate `~/.ssh/known_hosts` with trusted host fingerprints (e.g. GitHub/GitLab public keys) on developer workstations or build images.

### 7. AI Review False-Positive Detection & Invalidation Feedback Loop
- **Context**: LLM review personas may occasionally hallucinate legacy syntax (e.g. Python 2 comma-separated exception handling), flag pre-submission secret redaction placeholders (`<masked-*>`, `[REDACTED]`, `${{ secrets.* }}`), or cite historical research/evidence notes (`evidence/`, `docs/LOG.md`) as live vulnerabilities.
- **Mitigation**: Use `devops review verify --status INVALIDATED --reason "..."` to record verification feedback. Run `devops review export-feedback` to compile invalidation records into `.data/feedback_dataset.jsonl` for prompt benchmarking and tuning.

### 8. Python 3 Multi-Exception Syntax & Pydantic Mutable Default Invariants
- **Context**: In Python 3, multiple exceptions in an `except` clause must be enclosed in parentheses as a tuple (e.g., `except (Err1, Err2):`). Omitting parentheses (e.g., `except Err1, Err2:`) is legacy Python 2 syntax that binds the first exception instance to the second name rather than catching both. Additionally, Pydantic models must use `Field(default_factory=list|dict)` rather than mutable collections (`[]`, `{}`) for field defaults.
- **Mitigation**: All multi-exception handlers across the codebase use explicit parenthesized tuples `except (Err1, Err2):`. Pydantic models enforce `Field(default_factory=...)`.

---

## Remediation Cost vs. Operational Impact Matrix

| Known Issue / Edge Case | Security / Ops Impact | Resolution Effort | Recommended Action |
|---|---|---|---|
| **1. GitHub CLI SSO Timeout** | Medium (auth failure if unauthenticated) | Low | **Keep Workaround**: Pre-auth via `gh auth login`; env var override provided. |
| **2. Private Network Egress (SSRF)** | High (default SSRF safety) | Low | **Keep Safe Default**: `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` explicit opt-in. |
| **3. Large Workspace Iteration** | Low (performance edge case) | Low | **Keep Path Guards**: `iter_workspace_repos()` and `.gitignore` bounds filtering. |
| **4. Optional SDK Dependencies** | Low (setup error) | Low | **Keep Env Guard**: `uv sync` ensures full SDK availability. |
| **5. Local Workstation Design Policy** | Low (architectural trade-off) | Low | **Keep DevContainer Policy**: Workspace bounds secure file access; SSH mounts serve local model. |
| **6. SSH Host Key Scanning (TOFU)** | Medium (network MITM on initial clone) | Low | **Pre-seed Known Hosts**: Pre-populate `known_hosts` for critical git hosts. |
| **7. AI Review False-Positive Tuning** | Low (prompt noise on non-code assets) | Low | **Verification Feedback**: Use `devops review verify` and `export-feedback` to tune prompts. |
| **8. Multi-Exception Syntax & Model Defaults** | High (runtime unhandled exception bug) | Low | **Enforce Standard**: Parenthesized tuples `except (A, B):` and `Field(default_factory=...)`. |

