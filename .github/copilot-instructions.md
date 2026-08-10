# GitHub Copilot Instructions

## Project
**devops-cli** — DevOps CLI for managing repos, SSH keys, Kubernetes, and more

- Language: Python >=3.14
- Entry point: `devops`
- Virtual environment: `.venv/` (managed by `uv`)

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
  main.py              # Typer app, command registration
  config.py            # Pydantic Settings, keyring helpers
  commands/            # One file per command group
  ai/
    client.py          # Unified LLM client (Ollama / Claude / OpenAI-compat)
    personas.py        # Reviewer persona definitions (DevSecOps, Architect, PM, Auditor)
  github/client.py     # PyGithub + httpx2 wrapper
  git/operations.py    # GitPython helpers
  crypto/ssh_keys.py   # SSH key generation / rotation
  templates/           # Jinja2 templates for devcontainer scaffolding
tests/                 # pytest, pytest-asyncio, pytest-mock
```

## AI Features (`devops ai`, `devops review`)
- `devops ai config --provider <ollama|claude|copilot|openai>`
- `devops ai test` — verify LLM connectivity
- `devops ai agents` — (re)generate this file and siblings
- `devops review branch [<branch>] [--base main] [--persona <p>] [--all]`
- `devops review pr <number> [--post]` — review GitHub PRs; optionally post as comment
- Personas: `devsecops` · `architect` · `pm` · `auditor`

## Security Notes
- SSH private keys: `~/.ssh/id_ed25519-<YYYYMMM>` pattern; rotated every 90 days
- GitHub / Grafana / ArgoCD tokens stored in OS keyring only
- All HTTP clients use `httpx2` with explicit timeouts
- No credentials in config YAML or source files
