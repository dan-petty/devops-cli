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
- **PR Base Branch Targeting (Release Branch First)**: All feature, bugfix, documentation, and maintenance pull requests MUST target the active release branch (`release/v<version>`, e.g., `--base release/v0.1.9`) rather than targeting `main` directly. Only release branches (`release/v<version>`) are permitted to target `main` when cutting an official release.
- **No Autonomous Merging by Agents**: AI agents must NEVER merge Pull Requests (`gh pr merge`) autonomously. Agents must create or update topic branches, push commits, open or update the Pull Request, verify CI checks are passing, and leave the merge decision to the user / maintainers.
- **Updating Existing PR Branches**: When revisions or additions are requested, push new commits directly to the existing topic branch (`git push origin <branch>`), which automatically updates the open PR.
- **No Commits to Unrelated or Merged Branches**: Never push unrelated changes to an existing branch or continue committing to a branch after its PR has already been merged. Always create a new dedicated topic branch from the active release branch for distinct features, fixes, or chores.
- **Conventional Commits**: PR titles and squashed commits must follow Conventional Commits standard (`feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `feat(release): vx.x.x`, etc.).

- **Quality Gate Assertion**: Ensure local CI passes before creating or updating PRs:
   ```bash
   uv run devops ci
   ```
- **Squash Merging**: Maintainers squash-merge approved PRs into the target branch using `gh pr merge <id> --squash`.


