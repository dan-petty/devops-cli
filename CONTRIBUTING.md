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

   Several agents share one host, and the full test suite starts one pytest worker for each CPU, so gates that run at once make each other several times slower (11189 tests took 247 s alone and 440 s each beside a second gate). A run that selects `test`, `security` or `typecheck`, and the full-suite `devops ci test` and `devops ci coverage`, therefore wait for a free gate slot first and say which process and worktree hold the slots. One slot exists for each 16 CPUs, and at least one; `ci.gate_slots` (or `DEVOPS_CLI_CI_GATE_SLOTS`) sets the number. The pre-push hook, a test run narrowed by paths or by `-n`, a dry run and a cached verdict never wait. The operating system frees a slot when its holder ends, also when it is killed. The wait is not part of the gate time and is recorded as the metric `ci.gate_slot_wait_seconds`.

---

## 4. Git Hygiene & Branch Management

- **Branch Naming**: [Section 5](#5-naming) gives the form of a branch name. The `no-commit-to-branch` pre-commit hook refuses a commit on a branch that breaks it.
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

## 5. Naming

This table holds the naming rules of the project. Each rule names the check that enforces it. A rule with no check is a convention: follow it, and expect a reviewer to ask for it.

| Artifact | Form | Check |
| :--- | :--- | :--- |
| Branch | `<type>/<issue>-<slug>` | The `no-commit-to-branch` pre-commit hook refuses a commit on a branch that breaks the form. `devops repos worktrees add` makes a branch in this form. |
| Pull request title and commit subject | `<type>(<scope>): <summary>` | The `Semantic PR title` check for the title. None for a commit on a branch. |
| Change folder | `<issue>-<slug>`, archived as `<YYYY-MM-DD>-<issue>-<slug>` | `devops openspec check` and `tests/test_change_folders.py`. |
| Python module, class, function and variable | PEP 8 | Ruff `N`. |
| Constant | `CONST_<NAME>` in `config/constants.py`; `DEFAULT_<NAME>` for a tunable value in `config/defaults.py` | None. |
| Test file and test function | The behavior it checks, in the terms of [CONTEXT.md](CONTEXT.md) ([docs/TESTING.md](docs/TESTING.md#names-and-assertions)) | None. |
| `devops` command and option | Lowercase words joined by hyphens | None. |
| Environment variable | `DEVOPS_CLI_<SECTION>_<NAME>` | The settings model sets the prefix, and `docs/ENV_VARS.md` is generated from it. |
| Metric | `devops_cli_<name>`; a counter ends in `_total` and no other metric does | `tests/test_telemetry_instruments.py` checks the `_total` suffix. |
| Issue label | `<category>/<value>`, from `.github/labels.yml` | `devops gh labels sync`. |
| Decision record | `docs/adr/<NNNN>-<slug>.md` | None. |
| Release tag | `v<major>.<minor>.<patch>` | release-please writes it. Nobody tags by hand. |
| Agent file, worktree and scratch script | Under `.data/agent/`. The worktree of an issue is `.data/agent/worktrees/w-<issue>`. | `.gitignore`. `devops repos worktrees add` makes the worktree. |

The parts of a branch name:

- `<type>` is the type of the pull request title: `feat`, `fix`, `perf`, `refactor`, `revert`, `docs`, `test`, `build`, `ci`, `style` or `chore`. `release-please-config.json` lists the same types. Only the first five add a line to the changelog.
- `<issue>` is the number of the one issue that the pull request closes.
- `<slug>` is lowercase words and digits, joined by single hyphens. It is the slug of the change folder.

Start the work on an issue with `devops repos worktrees add <issue> --type <type> --slug <slug>`. The command fetches `origin/main` and creates the worktree `.data/agent/worktrees/w-<issue>` on the branch `<type>/<issue>-<slug>`. The branch has no upstream, so the first push is `git push -u origin HEAD`. The command refuses the issue when a worktree has a branch for it (whatever the type and the slug), when the directory `w-<issue>` exists, or when `origin` has a branch for it, and its error names the holder. A local branch with no worktree holds nothing. `devops repos worktrees status` shows the issue of each worktree.

The rule covers the branches that you push to this repository. GitHub makes the branches of bots (`release-please--*` and `renovate/*`), and nobody commits on them locally. `devops branches jira` and `devops scan fix` name branches of other repositories.

---

## 6. Routine Tasks Checklist

Before opening a pull request or handing off work, verify all applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) have been completed.
