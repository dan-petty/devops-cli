# Knowledge Base: uv (Python Package & Project Manager)

## 1. Overview & Purpose

`uv` is an extremely fast Python package manager and project orchestrator developed by Astral. Written in Rust, it serves as a drop-in replacement for `pip`, `pip-tools`, `virtualenv`, and `poetry`. In the `devops-cli` ecosystem, `uv` is the foundational tool used for all virtual environment lifecycle management, lockfile resolution (`uv.lock`), dependency installation, tool execution (`uvx`), and execution isolation (`uv run`).

---

## 2. Usage Information & Architecture

- **Native Resolution & Installation Engine**: Resolves dependency graphs concurrently with cryptographic hash validation and global caching under `~/.cache/uv`.
- **Workspace & Lockfile Model**: Uses `pyproject.toml` (PEP 517/518/621) and standard `uv.lock` lockfiles for deterministic environment reproducibility.
- **Global Binary Availability**: In DevContainer environments, `uv` and `uvx` binaries are installed directly into `/usr/local/bin/` so they are accessible to all users and shell sessions.
- **CLI Proxy Integration**: Commands such as `devops uv run` and `devops uv sync` provide explicit telemetry and subprocess tracking while executing native `uv` commands under the hood.

---

## 3. Common & Advanced Commands

### Project & Dependency Management
```bash
# Synchronize virtual environment with lockfile
uv sync

# Add a runtime dependency to pyproject.toml and update lockfile
uv add pydantic>=2.10.0

# Add a development dependency to the dev dependency group
uv add --dev pytest-xdist>=3.8.0

# Remove a dependency
uv remove requests

# Export dependencies to a standard requirements.txt format
uv export --format requirements-txt -o requirements.txt
```

### Execution & Tooling
```bash
# Execute a command within the project virtual environment (.venv)
uv run pytest tests/test_server.py

# Run a Python script or module directly
uv run python -m devops_cli.main --help

# Execute an isolated command-line tool without prior installation
uvx ruff check .
```

### Dependency Auditing
```bash
# Audit installed project dependencies for known CVE vulnerabilities
uv audit
```

---

## 4. Best Practice Guidance

1. **Always Use `uv run` for Script Execution**: Running commands via `uv run` ensures the correct project virtual environment (`.venv`) is activated and Python interpreter paths are resolved properly.
2. **Commit `uv.lock`**: Always commit `uv.lock` to source control to guarantee 100% bit-for-bit reproducibility across local workstations and CI environments.
3. **Use Dependency Groups**: Categorize development, linting, and testing dependencies under `[dependency-groups]` (e.g. `dev = ["pytest", "ruff", "mypy"]`) rather than polluting production runtime requirements.
4. **Leverage Global Cache**: Avoid clearing the `uv` cache unnecessarily; it significantly accelerates container rebuilds and local test iteration loops.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Malware Checks**: Keep `UV_MALWARE_CHECK=1` enabled in developer workstations to detect suspicious or typosquatted packages from PyPI before installation.
- **Lockfile Hash Verification**: Always install packages with locked hashes (`uv sync --frozen` in CI workflows) to prevent supply chain tampering.
- **Dependency Auditing**: Regularly run `uv audit` or `devops ci` to catch newly published CVE advisories affecting installed third-party wheels.

---

## 6. General Standards & Reference Guidelines

- **Python Version Tracking**: Target Python 3.14+ runtime environments (`requires-python = ">=3.14"` in `pyproject.toml`).
- **Build Backend**: Use standard build backends such as `hatchling` (`[build-system] requires = ["hatchling"]`).
- **Target Agnostic Tooling**: Never assume local project paths; always resolve the active repository root dynamically via `pyproject.toml` or `git rev-parse --show-toplevel`.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [astral.sh/uv](https://astral.sh/uv)
- **Public Git Repository**: [github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- **Official PyPI Package**: [pypi.org/project/uv](https://pypi.org/project/uv/)
- **Binary Releases**: [github.com/astral-sh/uv/releases](https://github.com/astral-sh/uv/releases)
- **DevOps CLI uv Wrapper**: [src/devops_cli/commands/uv.py](../../../commands/uv.py)
