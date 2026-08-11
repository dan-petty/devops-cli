# devops-cli — Agent Instructions

> **Canonical Source.** Single source of truth for AI coding agents. `CLAUDE.md` and `.github/copilot-instructions.md` are thin pointers to this file. Edit this file (or run `devops ai agents`), not pointers.

## Project & Environment Policy
- **Language**: Python >=3.14 | **Entrypoint**: `devops` | **Package Manager**: `uv` (`.venv/`)
- **Workstation-Native Model**: Designed to run inside VS Code Dev Containers on local DevOps workstations.
- **Modernization Policy**: Tracking latest Python releases, base container images, and dependencies is intentional to avoid upgrade debt and CVE exposure. A failing `devops ci` after a dependency bump signals a code fix, not pinning backward.

## Build & Quality Commands
```bash
uv sync                        # Sync dependencies
devops ci                      # Run full quality gate (test + lint + format + typecheck)
devops ci test [-v] [-k expr]  # pytest
devops ci lint [--fix]         # ruff check
devops ci format [--fix]       # ruff format
devops ci typecheck            # mypy (strict)
```

## Code Conventions
- Python 3.14+, strict `mypy`, `ruff` (E/F/I/N/W/UP rules), 100-char line limit, 4-space indent for Python (2-space for JSON/YAML/TOML/shell), LF line endings.
- Always use parenthesized exception tuples `except (E1, E2):` (never comma-separated legacy Python 2 syntax `except E1, E2:`).
- Type annotations on all public functions; `from __future__ import annotations`.
- Import `Callable` from `collections.abc`, not `typing`. Use `httpx2` (not `httpx`) for HTTP calls.
- Secrets stored in OS keyring (`keyring`); never in config files or environment variables.

## Architecture Subpackage Map
```
src/devops_cli/
  main.py              # Typer app entry point and command registration proxy
  core/                # Application initialization, Typer helpers, and dry-run execution state
  config/              # Settings (Pydantic), option keys, defaults, and env var specs
  http/                # Network security, SSRF validation, and HTTP client timeout config
  models/              # Centralized Pydantic domain models (git, ssh, github, grafana, prometheus, argo, ai)
  commands/            # CLI subcommands (ai, review, repos, ssh, k8s, kustomize, argo, grafana, prometheus, docker, workspace, install_tools, config, ci, branches, devcontainer, uv)
  ai/                  # LLM Client, PydanticAgent engine, agent tools, tasks, and personas (devsecops, architect, pm, auditor, qa)
  github/              # PyGithub + httpx2 wrapper & SSH key registration
  git/                 # GitPython helpers and workspace repository iterator
  crypto/              # ED25519 SSH keypair generation, auditing, and 90-day rotation
  templates/           # Jinja2 templates for devcontainer scaffolding
tests/                 # pytest, pytest-asyncio, pytest-mock suite
```

## Configuration & Environment Priority
Priority order (last wins): `~/.config/devops-cli/config.yaml` -> `config.yaml` / `$DEVOPS_CLI_CONFIG` -> `DEVOPS_CLI_*` env vars.

| Config Key | Env Variable | Purpose / Notes |
|---|---|---|
| `github.default_org` | `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | Default GitHub organization for cloning |
| `ssh.key_dir` | `DEVOPS_CLI_SSH_KEY_DIR` | Directory for SSH key pairs (`~/.ssh`) |
| `ssh.rotation_days` | `DEVOPS_CLI_SSH_ROTATION_DAYS` | SSH key rotation interval (default: 90) |
| `repos.base_dir` | `DEVOPS_CLI_REPOS_BASE_DIR` | Base directory for cloned repositories |
| `workspace.file` | `DEVOPS_CLI_WORKSPACE_FILE` | VS Code multi-root `.code-workspace` file path |
| `grafana.url` | `DEVOPS_CLI_GRAFANA_URL` | Grafana service endpoint URL |
| `prometheus.url` | `DEVOPS_CLI_PROMETHEUS_URL` | Prometheus service endpoint URL |
| `argocd.url` | `DEVOPS_CLI_ARGOCD_URL` | ArgoCD service endpoint URL |
| `ai.provider` | `DEVOPS_CLI_AI_PROVIDER` | Active LLM provider (`ollama` \| `claude` \| `copilot` \| `openai`) |
| `ai.model` | `DEVOPS_CLI_AI_MODEL` | Default LLM model name |
| `ai.ollama_url` | `DEVOPS_CLI_AI_OLLAMA_URL` | Ollama service endpoint URL |
| `ai.api_base_url` | `DEVOPS_CLI_AI_API_BASE_URL` | Custom OpenAI-compatible API base URL |
| `ai.allow_private_network` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | `true` permits private-IP network targets (SSRF defense) |
| — | `DEVOPS_CLI_CONFIG` | Absolute path to project configuration file |

Secrets (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the OS keyring (`devops config set <key> <value>`).
Inspect all 30 environment variables: `devops config output [--export|--json]` (aliases: `devops config env`, `devops config env-vars`).

## Complete Command Matrix

| Command Group | Subcommand / Usage | Functionality |
|---|---|---|
| **ai** | `devops ai config --provider <p>` | Set LLM provider (`ollama`, `claude`, `copilot`, `openai`) |
| | `devops ai test` | Test LLM connectivity and query available models |
| | `devops ai agents` | (Re)generate `AGENTS.md` and pointer instruction files |
| **review** | `devops review branch [<branch>] [--base main]` | Review branch git diff against base using AI personas |
| | `devops review pr <number> [--post]` | Review GitHub PR diff; optionally post summary as PR comment |
| | `devops review path [<target>] [--pattern <glob>]` | Review local files respecting `.gitignore` exclusions |
| | `devops review findings [<session>]` | Inspect structured review findings by verification status |
| | `devops review verify <session> --index N` | Validate (`verified`) or invalidate (`invalidated`) finding |
| | `devops review stats` | View accuracy metrics and false-positive rates per persona |
| **repos** | `devops repos clone-org --org <org>` | Batch clone all repositories in a GitHub organization |
| | `devops repos clone <url>` | Clone standalone repository into workspace |
| | `devops repos list` | List local workspace repositories and active git branches |
| | `devops repos sync [--all]` | Fetch and pull tracking branches across workspace repos |
| | `devops repos status` | Display uncommitted changes and branch drift across workspace |
| **ssh** | `devops ssh generate [--email <e>]` | Generate ED25519 keypair (`~/.ssh/id_ed25519-YYYYMMM[DD]`) |
| | `devops ssh status` | Inspect age and rotation status of managed SSH keys |
| | `devops ssh register` | Register SSH key and signing key with GitHub account |
| | `devops ssh rotate` | Rotate SSH keys older than threshold and update GitHub |
| | `devops ssh audit` | Audit SSH key expiration dates and key file permissions |
| **k8s** | `devops k8s deploy-stack` | Deploy ArgoCD, Prometheus, Grafana, OTEL to minikube |
| | `devops k8s status` | Display pod status across infrastructure namespaces |
| | `devops k8s pods [--namespace <ns>]` | List pod status with RFC 1123 label filtering |
| | `devops k8s logs <pod> --container <c>` | Stream container logs safely with bounded `--tail` |
| | `devops k8s apply -f <file>` | Apply Kubernetes manifest via `kubectl` |
| **kustomize** | `devops kustomize build <dir>` | Build and validate Kustomize overlay manifests |
| **argo** | `devops argo list` | List ArgoCD applications |
| | `devops argo status --app <app>` | Check ArgoCD application health and sync status |
| | `devops argo sync --app <app>` | Trigger ArgoCD application sync operation |
| | `devops argo workflows list` | List active and historical Argo Workflows |
| | `devops argo rollouts list` | List Argo Rollouts and deployment strategy status |
| **grafana** | `devops grafana dashboards` | Search and list Grafana dashboards by tag or query |
| | `devops grafana alerts` | List active Grafana alert rules and firing states |
| | `devops grafana search --query <q>` | Search Grafana dashboards by query string |
| **prometheus** | `devops prometheus query "<promql>"` | Execute PromQL instant query against Prometheus |
| | `devops prometheus targets` | List Prometheus active scrape targets and health |
| **docker** | `devops docker prune` | Prune dangling Docker containers, networks, and volumes |
| | `devops docker clean` | Deep clean unused Docker images and build cache |
| | `devops docker stats` | Display resource usage metrics for running containers |
| **workspace** | `devops workspace generate` | Regenerate multi-root VS Code `.code-workspace` file |
| | `devops workspace open` | Open multi-root workspace file in VS Code |
| | `devops workspace add <dir>` | Add directory to workspace file with boundary checks |
| | `devops workspace list` | List configured directories in active workspace file |
| **install-tools**| `devops install-tools [tools...]` | Install verified DevOps binaries with SHA-256 checksums |
| | `devops install-tools check` | Verify presence and versions of required CLI binaries |
| **config** | `devops config show` | Display configuration settings with masked secret tokens |
| | `devops config get <key>` | Get specific configuration value |
| | `devops config set <key> <val>` | Set configuration setting or store secret in OS keyring |
| | `devops config output [--export\|--json]`| Output environment variables available for configuration |
| **ci** | `devops ci` | Run complete quality gate (pytest, ruff, format, mypy) |
| | `devops ci test\|lint\|format\|typecheck` | Execute individual CI quality checks |
| **branches** | `devops branches list` | List local and remote tracking branches across repos |
| | `devops branches prune` | Delete local tracking branches merged into main |
| | `devops branches sync` | Synchronize branch state across workspace repositories |
| **devcontainer**| `devops devcontainer init` | Scaffold `.devcontainer/` setup from Jinja2 templates |
| | `devops devcontainer up` | Launch Dev Container environment via VS Code CLI |
| **uv** | `devops uv sync` | Sync Python 3.14 virtual environment dependencies |
| | `devops uv add <pkg>` | Add dependency to `pyproject.toml` and sync |
| | `devops uv remove <pkg>` | Remove dependency from `pyproject.toml` and sync |
| | `devops uv python-install <ver>` | Install Python runtime version via `uv` |
| **mcp** | `devops mcp serve [--transport stdio\|sse] [--port 8000]` | Launch FastMCP server exposing devops-cli tools to MCP clients |
| | `devops mcp tools` | Print Rich table of all registered FastMCP tools and descriptions |

## AI Review Architecture & Security Directives
- **Personas**: `devsecops` · `architect` · `pm` · `auditor` · `qa`.
- **Step 1/4 Deterministic Metadata**: Static analysis (`SegmentMeta`) extracts `primary_purpose`, `key_symbols`, `dependencies`, and `change_types` in <5ms upfront.
- **Review Artifacts**: Output saved to `.data/reviews/<YYMMDD-HHMM>-<title>/`: `summary.md`, `segment-N.md`, `<persona>-review.md`, `findings.json`.
- **Repo Instructions Ingestion**: All review commands load `AGENTS.md` from the target repo and inject it into reviewer prompts inside `<project_conventions_context>` tags. Reviewers MUST defer to conventions documented here rather than raise findings against intentional policies.
- **Prompt Isolation Guardrails**: Diffs, source files, excerpts, and findings are enclosed in XML boundary tags (`<untrusted_code_diff>`, `<target_code_to_review>`, etc.) with explicit security instructions forbidding prompt injection execution or persona shifts.

## Security Architecture & Local Workstation Model
- **Workstation-Native Timeouts**: High default timeouts (`DEFAULT_REVIEW_TIMEOUT_SECONDS = 3600.0`, `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) accommodate local LLM inference (CPU/GPU Ollama) and corporate proxies.
- **SSH Key Mounting**: `.devcontainer/devcontainer.json` bind-mounts `${localEnv:HOME}/.ssh` by design to support key generation, 90-day rotation tracking, and GitHub registration.
- **SSRF Defenses**: `LLMClient` and `validate_service_url()` block non-public IP targets unless `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set.
- **Secret Scrubbing**: Review engine automatically redacts GitHub tokens (`ghp_`), API keys (`sk-`), JWTs, and private keys (`_mask_secrets_in_content`) before sending payloads to LLMs.
- **MCP Security**: FastMCP SSE transport binds to `127.0.0.1` loopback by default; non-loopback host binding requires explicit `--allow-remote`.
- **Stream Bounds**: LLM responses are capped at `MAX_STREAM_BYTES` (50MB) to prevent memory exhaustion during streaming.
- **Path Traversal Guards**: Workspace path checks (`_is_safe_workspace_file`) enforce repository boundaries on file operations.
- **Binary Integrity**: `devops install-tools` verifies SHA-256 checksums before installing binaries to disk.
- **Subprocess Safety**: External tool invocations (`kubectl`, `argo`, `gh`, `docker`) use non-interactive mode with RFC 1123 argument validation and explicit timeout guards.
