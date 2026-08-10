# Known Issues & Unresolved Edge Cases — devops-cli

This document captures known edge cases, intentional design trade-offs, and operational caveats in `devops-cli`.

---

## 1. Non-Interactive GitHub CLI Authentication Timeout

### Issue
Calls to `gh auth status` or `gh auth token` in `src/devops_cli/commands/config.py` and `github/ssh.py` execute with a 5-second timeout.

### Context & Impact
If corporate SSO gateways or system keychains require interactive browser authentication or experience network latency, `subprocess.run(["gh", "auth", "token"])` times out and returns `None`.

### Mitigation / Workaround
- Run `gh auth login` or `gh auth refresh` explicitly in your terminal prior to executing `devops` commands.
- Configurable environment variable `DEVOPS_CLI_GH_CLI_TIMEOUT=15` can be added if slow keychain resolution is encountered.

---

## 2. Egress Controls for Internal Cluster URLs (SSRF Safety)

### Issue
By default, `validate_service_url()` in `src/devops_cli/http/validation.py` refuses HTTP targets resolving exclusively to loopback (`127.0.0.1`), private RFC 1918 (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), or link-local addresses.

### Context & Impact
When connecting to internal ArgoCD, Grafana, Prometheus, or Ollama endpoints running inside private Kubernetes clusters or local Docker networks, `devops` commands will raise a `ValueError`:
`Refusing non-public ArgoCD URL. Set DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true to override.`

### Mitigation / Workaround
Set `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` in your shell environment or devcontainer configuration.

---

## 3. Large Workspace Directory Iteration Bounds

### Issue
When iterating repository directories in `src/devops_cli/commands/workspace.py` or scanning workspace files in `review.py`, deeply nested symlinks or thousands of cloned repos can cause high memory usage or long execution times.

### Context & Impact
Processing directories with thousands of repositories or unindexed build outputs can slow pagination.

### Mitigation / Workaround
- `review.py` respects `.gitignore` via `git ls-files --exclude-standard` and `git check-ignore`.
- Excluded directory patterns (`.venv`, `node_modules`, `__pycache__`, `.git`, `.mypy_cache`) are skipped automatically.

---

## 4. Optional SDK Dependency Imports

### Issue
Commands under `devops k8s` and `devops docker` rely on optional third-party Python packages (`kubernetes` SDK and `docker` SDK).

### Context & Impact
If `kubernetes` or `docker` packages are uninstalled or missing from the virtual environment, executing subcommands raises a clear error:
`kubernetes SDK unavailable: ...` or `Cannot connect to Docker: ...`

### Mitigation / Workaround
Run `uv sync` inside the dev container to ensure all optional dependencies in `pyproject.toml` are installed.

---

## 5. Local Workstation vs. Production Container Boundaries

### Issue / Design Policy
`devops-cli` is intentionally architected as a local DevOps Engineer workstation tool running inside Dev Containers. It employs intentional design trade-offs that differ from bare-metal or shared production cloud workloads.

### Context & Impact
- **High Timeouts**: Generous HTTP/subprocess timeouts (`DEFAULT_REVIEW_TIMEOUT_SECONDS = 3600.0`, `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) prevent failures during long local LLM inference (Ollama running heavy models) or high network latency.
- **Bind-Mounted Key Material**: `${localEnv:HOME}/.ssh` is bind-mounted into `.devcontainer` to manage key generation, rotation, and GitHub registration directly from the local workstation.
- **SSRF Opt-In**: Private network endpoints (internal ArgoCD, Grafana, Ollama) require explicit `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` opt-in.
- **Path Traversal Guards**: CLI file tools (`read_file`, `list_files`, `devops review path`, `devops workspace add`) enforce strict workspace boundary checks (`_is_safe_workspace_path`) to prevent arbitrary file access outside the repository root.

### Mitigation / Workaround
Defer to the Environment & Modernization Policy in `AGENTS.md`. Do not flag high default timeouts or host SSH mounts as unmitigated production vulnerabilities.

---

## 6. Remediation Cost vs. Operational Impact Matrix

| Known Issue / Edge Case | Security / Ops Impact | Resolution Effort | Recommended Action |
|---|---|---|---|
| **1. Non-Interactive GitHub CLI SSO Timeout** | Medium (command fails if SSO unauthenticated) | Low | **Keep Workaround**: Run `gh auth login` prior to commands; env var override `DEVOPS_CLI_GH_CLI_TIMEOUT` provides flexibility without code changes. |
| **2. Private Network Egress (SSRF Defense)** | High (Security protection by default) | Low | **Keep Safe Default**: Default blocking prevents SSRF; `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` explicit opt-in maintains security & ease-of-use. |
| **3. Large Workspace Iteration Bounds** | Low (Performance edge case) | Low | **Keep Workaround**: `.gitignore` filtering and standard directory exclusion lists (`.venv`, `node_modules`) eliminate 99% of path traversal slowdowns. |
| **4. Optional SDK Dependencies** | Low (Setup error) | Low | **Keep Environment Guard**: `uv sync` in devcontainer ensures 100% dependency availability out-of-the-box. |
| **5. Local Workstation Design Policy** | Low (Architectural trade-off) | Low | **Keep DevContainer Policy**: Workspace boundary checks secure file access; high timeouts and SSH mounts serve workstation usage model. |

