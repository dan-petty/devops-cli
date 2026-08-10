# devops-cli — Agent Instructions

> **Canonical source.** This file is the single source of truth for AI coding agent
> instructions in this repo. [CLAUDE.md](./CLAUDE.md) and
> [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers
> to this file, kept only because their tools look for those specific filenames. Edit
> this file (or regenerate via `devops ai agents`), not the pointer files.

## Project
**devops-cli** — DevOps CLI for managing repos, SSH keys, Kubernetes, and more

- Language: Python >=3.14
- Entry point: `devops`
- Virtual environment: `.venv/` (managed by `uv`)

## Environment & Modernization Policy
- This project is built to run **only inside the provided dev container** on a local
  DevOps Engineer's workstation — it is not intended for bare-metal installs, shared
  servers, or as a base image for other services.
- Tracking the **latest Python release, latest container base images, and latest
  dependency versions** is intentional, not an oversight. The dev container is rebuilt
  routinely, so staying current avoids accumulating upgrade debt and reduces exposure
  to unpatched legacy CVEs.
- This is safe specifically because of the test/lint/format/typecheck suite: `devops ci`
  is the guardrail that catches breakage from modernization before it merges. Treat a
  failing `devops ci` after a version bump as a signal to fix the break, not to pin
  backwards.
- When bumping Python, base images, or dependencies: update the version, run
  `devops ci`, and resolve any failures it surfaces before merging.

## Build & Test Commands
```bash
uv sync                        # install / sync dependencies
devops ci                      # run all checks (test + lint + format + typecheck)
devops ci test [-v] [-k expr]  # pytest
devops ci lint [--fix]         # ruff check
devops ci format [--fix]       # ruff format
devops ci typecheck            # mypy (strict)
```

## Code Conventions
- Python 3.14+, strict mypy, ruff (E/F/I/N/W/UP rules), 100-char line limit
- 4-space indent for Python; 2-space for JSON/YAML/TOML/shell
- LF line endings, trim trailing whitespace, final newline
- Type annotations on all public functions; `from __future__ import annotations`
- Import `Callable` from `collections.abc`, not `typing`
- Use `httpx2` (not `httpx`) for HTTP — `import httpx2`
- Secrets stored in OS keyring via `keyring`; never in config files or env vars

## Architecture
```
src/devops_cli/
  main.py              # Typer app entry point and command registration proxy
  core/                # Application initialization and dry-run execution context
    cli.py             # Typer app creation helpers (new_typer)
    dry_run.py         # Dry-run execution mode interceptor and state
  config/              # Centralized configuration subpackage
    settings.py        # Pydantic Settings, keyring helpers, and profile loaders
    options.py         # Canonical CLI option keys and secret mappings
    constants.py       # Non-configurable constants and URLs
    defaults.py        # CLI default values and HTTP timeout constants
    env.py             # Environment variable mappings
  http/                # Network security and HTTP client subpackage
    validation.py      # SSRF and private-IP network target validation
    client.py          # Shared HTTP client timeout configuration
  models/              # Centralized Pydantic domain models subpackage (git, ssh, github, grafana, prometheus, argo, ai)
  commands/            # CLI command submodules (one file per command group)
  ai/
    client.py          # Unified LLM client (Ollama / Claude / OpenAI-compat)
    agent.py           # Reusable PydanticAgent engine
    agent_tools.py     # Built-in agent tools
    personas.py        # Reviewer persona definitions (DevSecOps, Architect, PM, Auditor, QA)
  github/client.py     # PyGithub + httpx2 wrapper
  git/operations.py    # GitPython helpers
  crypto/ssh_keys.py   # SSH key generation / rotation
  templates/           # Jinja2 templates for devcontainer scaffolding
tests/                 # pytest, pytest-asyncio, pytest-mock
```

## Configuration & Environment Variables

Settings are loaded in this priority order (last wins):
1. `~/.config/devops-cli/config.yaml` — user-global settings
2. `config.yaml` (CWD) or the path in `DEVOPS_CLI_CONFIG` — project-level overrides
3. `DEVOPS_CLI_*` environment variables — override both files

| Config key | Environment variable | Notes |
|---|---|---|
| `github.default_org` | `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | |
| `ssh.key_dir` | `DEVOPS_CLI_SSH_KEY_DIR` | |
| `ssh.rotation_days` | `DEVOPS_CLI_SSH_ROTATION_DAYS` | |
| `repos.base_dir` | `DEVOPS_CLI_REPOS_BASE_DIR` | |
| `workspace.file` | `DEVOPS_CLI_WORKSPACE_FILE` | |
| `grafana.url` | `DEVOPS_CLI_GRAFANA_URL` | |
| `prometheus.url` | `DEVOPS_CLI_PROMETHEUS_URL` | |
| `argocd.url` | `DEVOPS_CLI_ARGOCD_URL` | |
| `ai.provider` | `DEVOPS_CLI_AI_PROVIDER` | `ollama` \| `claude` \| `copilot` \| `openai` |
| `ai.model` | `DEVOPS_CLI_AI_MODEL` | |
| `ai.ollama_url` | `DEVOPS_CLI_AI_OLLAMA_URL` | |
| `ai.api_base_url` | `DEVOPS_CLI_AI_API_BASE_URL` | |
| `ai.allow_private_network` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | `true` enables private-IP targets |
| — | `DEVOPS_CLI_CONFIG` | Absolute path to the project config file |

Secrets (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored in
the OS keyring only — never in config files or environment variables. Set them with
`devops config set <key> <value>`.

Inspect or export environment variables available for configuration:
`devops config output [--export|--json]` (aliases: `devops config env`, `devops config env-vars`).

## AI Features (`devops ai`, `devops review`)
- `devops ai config --provider <ollama|claude|copilot|openai>`
- `devops ai test` — verify LLM connectivity
- `devops ai agents` — (re)generate this file and siblings
- `devops review branch [<branch>] [--base main] [--persona <p>] [--all]`
- `devops review pr <number> [--post]` — review GitHub PRs; optionally post as comment
- `devops review path [<target>] [--pattern <glob>] [--persona <p>] [--all]` — respects `.gitignore` (uses `git ls-files --exclude-standard` + `git check-ignore`)
- `devops review findings [<session>] [--unverified|--invalidated|--verified]` — inspect findings for a review session
- `devops review verify <session> --index <N> --status <verified|invalidated> [--reason "..."]` — validate/invalidate findings & record feedback
- `devops review stats` — compute review accuracy metrics across saved sessions
- Personas: `devsecops` · `architect` · `pm` · `auditor` · `qa`
- All `devops review` commands execute Step 1/4 segment metadata extraction upfront before starting persona analysis. Metadata is computed using fast, deterministic static analysis (`SegmentMeta`) for 100% consistency and sub-millisecond execution time, extracting `primary_purpose`, `key_symbols`, `dependencies`, and `change_types`.
- All `devops review` commands save output to `.data/reviews/<YYMMDD-HHMM>-<title>/`:
  - `summary.md` — table of persona recommendations and links to all files
  - `segment-N.md` — raw content fed to the LLM for segment N
  - `<persona>-review.md` — rendered review from each persona
  - `findings.json` — structured findings with verification status and human feedback reasons
- All `devops review` commands load this file (AGENTS.md) from the target repo and
  inject it into the reviewer's system prompt, so findings must defer to conventions
  and policies documented here (e.g. the Environment & Modernization Policy above)
  rather than flag them as issues.

## Local Workstation vs. Production / CI Operations

- **Local Workstation / Dev Container Model (Default)**:
  - **High Timeouts**: Uses generous HTTP and subprocess timeouts (`DEFAULT_REVIEW_TIMEOUT_SECONDS = 3600.0`, `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 1800.0`) to accommodate local LLM inference (e.g., Ollama running large models on CPU/GPU) and slow corporate proxy connections. Do not flag high default timeouts as DoS risks.
  - **Host Key Material**: Mounts host `${localEnv:HOME}/.ssh` into `.devcontainer` by design to support local key generation, 90-day rotation tracking, and GitHub registration.
  - **Private Network Access**: Opt-in flag `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` permits connections to private-IP Ollama, ArgoCD, Grafana, and Prometheus endpoints.
  - **OS Keyring Secrets**: Secrets (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) are stored exclusively in the host/container OS keyring (`keyring`) — unencrypted fallback is explicitly rejected.

- **Production / CI Execution Guards**:
  - **Path & Workspace Boundary Enforcement**: File operations (`read_file`, `list_files`, `devops review path`, `devops workspace add`) enforce strict workspace boundary checks (`_is_safe_workspace_path`) to prevent path traversal outside the repository root.
  - **Non-Interactive Execution**: All external tool subcommands (`kubectl`, `argo`, `gh`, `docker`) run non-interactively with explicit `timeout` guards on `subprocess.run()` calls.

## Project Working Documentation
- Overview & Usage: [README.md](./README.md) — project summary, architecture, command reference matrix, and persona guides
- Roadmap: [docs/ROADMAP.md](./docs/ROADMAP.md) — project vision, phased milestone deliverables, and Value vs. Effort Prioritization Matrix
- Pending Features: [docs/PENDING_FEATURES.md](./docs/PENDING_FEATURES.md) — active proposals, feature specifications, and implementation ROI
- Known Issues: [docs/KNOWN_ISSUES.md](./docs/KNOWN_ISSUES.md) — unresolved edge cases, intentional design trade-offs, and remediation cost matrix

## Security Notes
- SSH private keys: `~/.ssh/id_ed25519-<YYYYMMM[DD]>` pattern; rotated every 90 days
- GitHub / Grafana / ArgoCD tokens stored in OS keyring only; env var fallbacks for secret tokens are rejected
- All HTTP clients use `httpx2` with explicit timeouts
- No credentials in config YAML or source files
- `devops_cli.ai.client.LLMClient` validates Ollama/Claude/OpenAI-compatible base URLs
  and refuses private/loopback/link-local targets unless
  `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is set — this mitigates SSRF via
  attacker- or config-controlled endpoints; do not flag this as unmitigated SSRF risk
- `devops_cli.http.validate_service_url` applies the same private-network check to all
  configured service URLs (ArgoCD, Grafana). Users with internal cluster URLs must set
  `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`; do not flag these as unmitigated SSRF risk
- `devops install-tools` verifies SHA-256 checksums for all downloaded binaries against
  release-provided checksum files before writing to disk; do not flag as unverified downloads
- Argo workflow/rollout `--namespace` and resource name arguments are validated against
  RFC 1123 before being passed to subprocess; do not flag as command injection
- All external tool subcommands (`argo`, `kubectl`, `gh`) use explicit `timeout` guards on `subprocess.run()` calls to prevent terminal hangs
- `.devcontainer/devcontainer.json` bind-mounts `${localEnv:HOME}/.ssh` into the container
  by design — this CLI's core purpose includes generating, rotating, and registering
  SSH keys, which requires direct access to the real key material. This is an accepted,
  intentional risk of the local-workstation-only usage model (see Environment &
  Modernization Policy); do not recommend SSH agent forwarding as a required fix
