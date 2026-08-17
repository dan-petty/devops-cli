# Release Cycle & Engineering Workflow — devops-cli

This document defines the end-to-end lifecycle for implementing features, verifying system integrity, and orchestrating releases for `devops-cli`.

---

## 1. Release Philosophy & Versioning Scheme

`devops-cli` adheres strictly to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`):
- **MAJOR (`X.0.0`)**: Incompatible API or breaking CLI command syntax changes.
- **MINOR (`0.Y.0`)**: Backward-compatible new functionality (e.g., new subcommands, security scanners, or FastMCP tools).
- **PATCH (`0.0.Z`)**: Backward-compatible bug fixes, performance optimizations, or prompt refinements.

### Ecosystem & Runtime Alignment
- **Bleeding-Edge Python**: Builds track Python 3.14+ runtime features (e.g., modern syntax, typing improvements, `pydantic v2`).
- **Zero-Plaintext Policy**: Secrets (GitHub tokens, OpenAI API keys, Grafana credentials) are managed exclusively through OS Keyring.
- **Network Egress Guardrails**: SSRF mitigation logic (`validate_service_url`) is enforced across all outbound network calls.

---

## 2. Feature Implementation Lifecycle

```mermaid
flowchart LR
    A[Feature Spec / Issue] --> B[Branch Development]
    B --> C[Centralize Config & Literals]
    C --> D[Unit Tests & Mocking]
    D --> E[7-Gate CI Quality Gate]
    E --> F[Automated Docs & README Sync]
    F --> G[PR Review & Merge]
    G --> H[Release Orchestration]
```

### Stage 1: Design & Branch Creation
1. Create a dedicated feature branch from `main`:
   ```bash
   git checkout -b feature/<feature-name>
   # or
   git checkout -b fix/<bug-name>
   ```
2. Ensure environment synchronization using `uv`:
   ```bash
   uv sync
   ```

### Stage 2: Code Implementation & Architectural Standards
- **Modular Subcommand Pattern**: New CLI subcommands must be implemented under `src/devops_cli/commands/` and registered in `src/devops_cli/main.py` via `_COMMAND_SPECS`.
- **FastMCP Tool Parity**: Infrastructure commands should expose corresponding lazy MCP tools under `src/devops_cli/ai/mcp/` where appropriate.
- **Literal & Constant Centralization**:
  - Centralize timeouts and defaults in [`src/devops_cli/config/defaults.py`](file:///workspaces/devops-cli/src/devops_cli/config/defaults.py).
  - Centralize static paths, regex patterns, and protocol constants in [`src/devops_cli/config/constants.py`](file:///workspaces/devops-cli/src/devops_cli/config/constants.py).
  - Centralize user-facing help messages, summaries, and error logs in [`src/devops_cli/lang/`](file:///workspaces/devops-cli/src/devops_cli/lang/).
- **Dry-Run Support**: All state-modifying subcommands must support the `--dry-run` flag via `devops_cli.dry_run`.

### Stage 3: Automated Testing & Mocking Standards
- **Mocking Policy**: All unit tests must isolate external side-effects using `unittest.mock`, `pytest-mock`, or generic mock placeholders (e.g., `http://node1.example.test`). Live provider calls or hardcoded personal credentials in tests are strictly prohibited.
- **Parallel Test Execution**: Run tests with `pytest-xdist`:
  ```bash
  uv run pytest
  ```

---

## 3. Documentation & Verification Standards

Documentation is dynamic and verified in CI. Handcrafted drift in CLI references is prevented by automated introspection.

### Automated Documentation Generation
When adding or modifying subcommands, options, environment variables, or FastMCP tools:
1. Regenerate Markdown documentation and update the Command Matrix in `README.md`:
   ```bash
   uv run devops docs generate --sync-readme
   ```
2. Verify documentation freshness:
   ```bash
   uv run devops docs check
   ```

### Documentation Files Managed by Generator
| Target Document | Description |
| :--- | :--- |
| [`README.md`](file:///workspaces/devops-cli/README.md) | Complete Command Matrix synchronized between `<!-- COMMAND_MATRIX_START -->` and `<!-- COMMAND_MATRIX_END -->`. |
| [`docs/CLI_REFERENCE.md`](file:///workspaces/devops-cli/docs/CLI_REFERENCE.md) | Consolidated reference for all CLI subcommands, options, and arguments. |
| [`docs/ENV_VARS.md`](file:///workspaces/devops-cli/docs/ENV_VARS.md) | Environment variables, corresponding config options, and defaults. |
| [`docs/MCP_TOOLS.md`](file:///workspaces/devops-cli/docs/MCP_TOOLS.md) | FastMCP tools, input schemas, and execution parameters. |
| `docs/commands/<group>.md` | Dedicated per-command-group reference manuals. |

---

## 4. Quality Gate & CI Validation

The `devops ci` quality gate is the authoritative validation gate. All checks must pass cleanly before any merge or release.

```bash
# Run full 7-gate CI validation suite
uv run devops ci run
```

### The 7 Quality Gates
1. **Python Version Check**: Strictly enforces Python 3.14+ runtime.
2. **Linting (`ruff check .`)**: Strict PEP 8 linting, import sorting, and unused symbol elimination.
3. **Formatting (`ruff format --check .`)**: Enforces 100-character line length standards.
4. **Type Checking (`mypy --strict src`)**: Full static type checking in strict mode.
5. **Documentation Validation (`devops docs check`)**: Asserts all docs and README matrices are synchronized.
6. **Unit Tests & Code Coverage (`pytest --cov=src`)**: Executes test suite with coverage thresholds.
7. **Security Scan (`bandit`)**: Static vulnerability and code safety analysis.

---

## 5. Release Subcommands Suite (`devops release`)

The `devops-cli` provides native first-class subcommands to automate every stage of the release lifecycle:

| Subcommand | Description | Example |
| :--- | :--- | :--- |
| `devops release status` | Displays release version consistency, git tag, changelog state, and docs freshness. | `devops release status` |
| `devops release prepare <ver>` | Bumps versions in `pyproject.toml` and `__init__.py`, updates `CHANGELOG.md`, and syncs docs/README. | `devops release prepare 0.1.8 [-p]` |
| `devops release pr [-v <ver>]` | Creates a release branch (`release/vX.Y.Z`), commits bumps, and opens a GitHub Release PR. | `devops release pr -v 0.1.8` |
| `devops release check` | Authoritative verification gate: asserts version matching, clean git tree, docs freshness, and 7-gate CI. | `devops release check` |
| `devops release notes [-v <ver>]` | Extracts and renders formatted markdown release notes from `CHANGELOG.md`. | `devops release notes -v 0.1.8` |
| `devops release tag [-v <ver>]` | Creates release commit and annotated git tag (used by CI release automation on `main`). | `devops release tag 0.1.8` |

---

## 6. GitHub Pull Request Merge Controls & Release Orchestration

Releases in `devops-cli` enforce **GitHub Pull Request Merge Controls** and Branch Protection rules on `main`. Direct manual pushes to `main` and direct developer tagging are prohibited; every release is gated behind peer review and automated CI quality checks.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / Maintainer
    participant CLI as devops release pr
    participant Git as GitHub (release/vX.Y.Z)
    participant CI as GitHub Actions (ci.yml)
    participant Main as Protected Branch (main)
    participant Rel as GitHub Actions (release.yml)

    Dev->>CLI: devops release prepare X.Y.Z --create-pr
    CLI->>Git: Push branch release/vX.Y.Z & Open Release PR
    Git->>CI: Trigger 7-Gate CI Quality Validation
    CI-->>Git: All 7 quality gates passed (Green)
    Dev->>Git: Peer Review & PR Approval
    Dev->>Main: Merge Pull Request into main
    Main->>Rel: Push to main triggers release.yml
    Rel->>Rel: Run authoritative devops release check
    Rel->>Rel: Extract release notes (devops release notes)
    Rel->>Git: Auto-cut annotated tag vX.Y.Z
    Rel->>Git: Publish GitHub Release & Assets
```

---

## 7. Step-by-Step Release Procedure

### Step 1: Check Current Status
```bash
uv run devops release status
```

### Step 2: Prepare Release & Open GitHub Release PR
Use the unified `--create-pr` flag (or `devops release pr`) to automate version bumping, changelog updating, docs regeneration, branch creation, commit, and PR submission:
```bash
# Prepares version, commits changes to branch 'release/vX.Y.Z', and opens GitHub PR
uv run devops release prepare X.Y.Z --create-pr
```

### Step 3: CI Quality Gate & PR Review Gate
1. The opened Pull Request triggers `.github/workflows/ci.yml` which validates:
   - Python 3.14 runtime environment
   - Ruff linting & formatting (`ruff check`, `ruff format --check`)
   - Mypy strict type checking (`mypy --strict src`)
   - Documentation freshness (`devops docs check`)
   - Pytest unit tests and test coverage thresholds
   - Bandit static security scanning
2. Maintainers review the release diff, changelog, and documentation updates.

### Step 4: Merge PR into `main`
Merge the approved Release Pull Request into `main` via the GitHub Web UI or CLI (`gh pr merge --squash` or `gh pr merge --merge`).

### Step 5: Automated Release Publishing (GitHub Actions)
Upon PR merge into `main`, [`.github/workflows/release.yml`](.github/workflows/release.yml) automatically:
1. Detects the release commit (`chore(release): bump version to vX.Y.Z`).
2. Runs authoritative verification (`devops release check --allow-dirty`).
3. Cuts and pushes the annotated git tag `vX.Y.Z`.
4. Extracts release notes using `devops release notes` and creates the official GitHub Release.

### Step 6: Post-Release DevContainer Validation
Verify DevContainer lifecycle operations:
```bash
uv run devops devcontainer run-lifecycle --all
```


