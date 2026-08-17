# Contributing to devops-cli

Thank you for contributing to `devops-cli`! This project tracks bleeding-edge Python standards (Python 3.14+), strict type safety (`mypy --strict`), and high-reliability SRE principles.

---

## 1. Development Environment Setup

We use [`uv`](https://github.com/astral-sh/uv) for fast, deterministic dependency management.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/devops-cli.git
cd devops-cli

# 2. Synchronize virtual environment
uv sync

# 3. Verify runtime environment
uv run devops ci
```

---

## 2. Coding Standards & Guidelines

- **Python Version**: Strictly Python 3.14+. Use modern typing syntax (`X | Y`, `type`, `Annotated`).
- **Code Style & Formatting**: PEP 8 compliant, line length strictly **100 characters** enforced via `ruff`.
  ```bash
  uv run ruff check --fix .
  uv run ruff format .
  ```
- **Type Safety**: Mandatory type hints on all public and private functions. Must pass `mypy --strict src`.
  ```bash
  uv run mypy --python-version 3.14 --strict src
  ```
- **Config & Literal Centralization**: Never scatter hardcoded strings or timeout literals throughout commands. Store constants in [`src/devops_cli/config/constants.py`](file:///workspaces/devops-cli/src/devops_cli/config/constants.py), defaults in [`src/devops_cli/config/defaults.py`](file:///workspaces/devops-cli/src/devops_cli/config/defaults.py), and user-facing messages in [`src/devops_cli/lang/en.py`](file:///workspaces/devops-cli/src/devops_cli/lang/en.py).
- **Test Mocking Policy**: All automated unit tests must use `unittest.mock` or dummy test doubles. Live network calls in unit tests are prohibited.

---

## 3. Documentation Standards

Documentation is generated dynamically and asserted in CI:
- When adding or modifying subcommands, flags, or FastMCP tools:
  ```bash
  # Regenerate markdown reference docs and update README Command Matrix
  uv run devops docs generate --sync-readme

  # Validate documentation freshness
  uv run devops docs check
  ```
- Never manually edit the Command Matrix in `README.md`.

---

## 4. Submitting Pull Requests & Branch Management
 
- **Protected `main` Branch**: Direct commits and pushes to `main` are strictly prohibited. All changes must be proposed via pull requests.
- **Dedicated Topic Branches**:
  - Features: `feat/<name>` or `feature/<name>`
  - Bug Fixes: `fix/<name>`
  - Documentation: `docs/<name>`
  - Maintenance: `chore/<name>`
  - Releases: `release/v<version>`
- **Conventional Commits**: PR titles and squashed commits must follow Conventional Commits standard (`feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `feat(release): vx.x.x`, etc.).
- **Quality Gate Assertion**: Ensure local CI passes before creating PR:
   ```bash
   uv run devops ci
   ```
- **Squash Merging**: PRs are squash-merged into `main` using `gh pr merge <id> --squash`.

