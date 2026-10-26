# Contributing to DevOps CLI

Thank you for your interest in contributing to DevOps CLI! This document outlines our engineering standards, development workflow, and pull request governance.

---

## 1. Development Philosophy & Core Invariants

These rules apply to every contributor. [`AGENTS.md`](AGENTS.md) sends agents here.

- **Test-First Implementation (TDD)**: All features, fixes, and refactorings **must** have tests written first. Tests serve as the executable documentation of public interfaces, edge cases, and architectural boundaries.
- **Complexity and Nesting Caps**:
  - Ruff caps cyclomatic complexity at 10 (`C901`) in `pyproject.toml`. `uv run devops ci` and the pre-commit `ruff-check` hook run it with `--config pyproject.toml`, and `tests/test_ruff_complexity_cap.py` checks the resolved settings and every `ruff check` command. Functions over the cap when it was turned on carry `# noqa: C901`, and `tests/test_architectural_invariants.py` keeps their count from growing. `devops scan complexity` reports the same McCabe count and does not gate.
  - Maximum nesting depth $\le 5$ (< 6 indentation levels) project-wide.
  - Decompose multi-step procedures into dedicated single-responsibility helpers and pure predicates.
  - For a closed set of cases, use `match` with `assert_never`, or a table. Do not write an `if`/`elif` chain.
- **Closed Lists and Standard Parsers**:
  - Match a value against a list of strings only when the list covers a closed domain, such as one that an RFC or a language grammar defines.
  - For an open domain, use a parser (`ast`, `tokenize`, `urllib.parse`, `ipaddress`, `packaging`) or an official registry, such as the Public Suffix List through `tldextract`.
  - Declare each list, tuple or frozen set that matches, classifies or filters values in `src/devops_cli/config/constants.py` or `src/devops_cli/config/defaults.py`.
- **Names**: Name each file, module, class and function for its responsibility. Do not use a placeholder name, such as `temp_util.py`. Ruff `N` checks the form.
- **Line Breaks Belong to Source Files**: Hard-wrap text only in source files and Markdown documents. Write emitted text (terminal messages, Rich renderables, log records, `lang/en/` strings) as continuous paragraphs. Split a long string in the source with implicit string concatenation.
- **Strongly Typed Domain Exceptions**:
  - All domain error states must raise strongly typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`.
  - Raising bare Python built-in exceptions (`ValueError`, `RuntimeError`, `TypeError`) is strictly prohibited.
- **Minimum 90% Code Coverage**: Continuous quality gate enforced by `devops ci` across all `src/` modules.
- **Pre-1.0 Alpha Status & Zero Backwards Compatibility**: DevOps CLI is pre-1.0 alpha software. Until at least release `1.0.0`, there is no intention of maintaining backwards compatibility. The codebase must remain clean of legacy references and obsolete shims at all times so that it can reach maturity at a reasonable rate. Any version after `1.0.0` will follow strict semantic versioning conventions, and employ all change management best practices including feature flags, deprecations, and migration functionality.
- **Zero Zombie Code & Legacy Remnants**: Ruthlessly remove obsolete shims, legacy workarounds, and deprecated aliases. Never introduce compatibility shims during the pre-1.0 development cycle.

---

## 2. Local Environment Setup

We use modern Python 3.14+ runtime tooling powered by [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Clone repository
git clone https://github.com/dan-petty/devops-cli.git
cd devops-cli

# 2. Synchronize virtual environment and all dependency groups
uv sync --all-groups --all-extras

# 3. Install pre-commit hooks
uv run pre-commit install
```

---

## 3. Test-First Development Cycle (Inner Loop)

1. **Write Specification via Tests**:
   Write the tests first, as [`docs/TESTING.md`](docs/TESTING.md) describes, and run the file you changed:
   ```bash
   uv run devops ci test <test-file>
   ```
2. **Implement Feature Code**:
   Write concise, well-factored code in `src/devops_cli/` to satisfy the tests.
3. **Verify Fast Local Loop**:
   ```bash
   uv run ruff check path/to/modified.py
   uv run mypy path/to/modified.py
   uv run devops ci test tests/test_architectural_invariants.py
   ```
4. **Push Through the Fast Checks, and Merge Through CI**:
   The pre-push hook runs only the fast static checks: `uv run devops ci --check --only lint,format,actionlint,zizmor`. A push goes only when they pass. Never use `--no-verify`. The required checks of CI, `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, must pass on the pull request before it merges (#1752). The release pull request runs the same checks on each new `main`, so its status shows a defect that two pull requests make together. To run every check before a push, run the full gate by hand:
   ```bash
   uv run devops ci
   ```
   Validates every check `devops ci` runs concurrently: Python runtime, tests, 90% coverage, linting, formatting, strict typing, dependency audit, security scanning, the wheel and sdist build, workflow actionlint and zizmor, and documentation freshness.

---

## 4. Git Hygiene & Branch Management

- **Branch Naming**: Use descriptive topic branch prefixes:
  - `feat/<short-description>`: New features
  - `fix/<short-description>`: Defect repairs
  - `refactor/<short-description>`: Code structure improvements
  - `docs/<short-description>`: Documentation changes
- **Branch Targeting**: Every topic branch targets `main`. A maintainer squash-merges the pull request.
- **Drafts First**:
  - Open every pull request with `devops pr create`. It always opens a draft.
  - When all checks pass, mark the pull request ready with `devops pr ready <pr-number>`. This is the only way out of the draft.
- **The Title Is the Changelog Line**:
  The pull request title is a Conventional Commit, and the `Semantic PR title` check enforces it. The squash commit takes the title as its subject. release-please writes the changelog from these titles, so write the title for a reader of the changelog:
  ```
  feat(k8s): add automated minikube helm adoption check
  fix(runner): prevent thread pool executor blocking on tool timeout
  docs(sdlc): add enterprise lifecycle manual
  ```
  Before `1.0.0` nothing is a breaking change, so a title has no `!` and a body has no `BREAKING CHANGE:` footer. Only these types add a line to the changelog:

  | Title type | Changelog section |
  | :--- | :--- |
  | `feat` | Features |
  | `fix` | Bug Fixes |
  | `perf` | Performance Improvements |
  | `refactor` | Code Refactoring |
  | `revert` | Reverts |

  The other types (`docs`, `test`, `build`, `ci`, `style`, `chore`) add no line. Do not edit `CHANGELOG.md`: release-please writes it in its release pull request. [`RELEASE_CYCLE.md`](RELEASE_CYCLE.md) tells what happens after the merge.
- **The Body Is the Commit Message**: The squash commit takes the pull request body as its message, so `git log` keeps the body after the merge. Write the body as it will read there: what the change does, and why. End it with `Closes #<issue>`, the `Change:` line of the [template](.github/pull_request_template.md) and, when it applies, the `Fail-to-pass: not applicable: <reason>` line. Put test results, check status, steps for a person and the history of the issue in a comment on the pull request or on the issue, not in the body. When a push changes what the pull request does, change the body too.
- **Commits on the Branch**: Commits on a topic branch also follow the Conventional Commits format. The squash merge replaces them with one commit, with the title as its subject and the body as its message.
- **Fail-to-Pass Evidence**: A fix pull request cites its `fail-to-pass` check run in a comment (`devops ci fail-to-pass --base <ref>`, `.github/workflows/fail-to-pass.yml`). Do not type failure counts by hand. The check fails a pull request whose replay could not run on the base: pytest stopped, did not start or wrote no complete JUnit report. Such a pull request declares `Fail-to-pass: not applicable: <reason>` in its body. A changed test that only fails to collect on the base counts as errored.
- **Helper Scripts**: A committed helper script goes in `scripts/` as a PEP 723 file, and Ruff checks it. The pull request that adds the first script adds `scripts` to the mypy and Bandit targets. Scratch scripts stay untracked under `.data/agent/scratch/`.
- **Documentation Synchronization**:
  Run documentation introspection after any command or option change:
  ```bash
  uv run devops docs generate --sync-readme
  ```
  Every Markdown file belongs to exactly one class of the documentation inventory (`CONST_DOCS_INVENTORY` in `src/devops_cli/config/constants.py`), so a pull request that adds a document lists it there. `devops docs check` resolves the `devops` command lines of every hand-written and prompt document against the live command tree, so a command named in prose is a command that exists.

---

## 5. Routine Tasks Checklist

Before opening a pull request or handing off work, verify all applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) have been completed.
