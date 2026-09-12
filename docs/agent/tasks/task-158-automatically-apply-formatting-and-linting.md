# Task 158: Automatically Apply Formatting and Linting Across CLI and CI Commands

**Issue**: [#158](https://github.com/dan-petty/devops-cli/issues/158)
**PR**: [#159](https://github.com/dan-petty/devops-cli/pull/159)
**Status**: Done
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

Provide automated formatting and linting by default across DevOps CLI developer workflows:
1. `devops ci`: Default `--fix` to True so that `ruff format .`, `ruff check --fix .`, and docs generation are executed automatically before running quality gates. Support `--check` / `--no-fix` for non-mutating validation.
2. `devops ci format`: Format code in-place by default with `ruff format .`, accepting `--check` to verify without modifying.
3. `devops ci lint`: Apply automated fixes with `ruff check --fix .` by default, accepting `--check` to verify without modifying.
4. Top-level CLI aliases: Add first-class `devops format` and `devops lint` commands to root `devops` CLI.
5. Quality & Invariants: Comprehensive unit tests, zero documentation drift, and strict adherence to cyclomatic complexity $\le 10$ and nesting depth $\le 5$.

---

## 2. Planned Changes

1. `src/devops_cli/commands/ci.py`:
   - `all_checks`: Set default `fix=True`, add `--check` option, compute `effective_fix = fix and not check`.
   - `fmt`: Format in-place by default, add `--check` option.
   - `lint`: Apply autofixes by default (`fix=True`), add `--check` option.
2. `src/devops_cli/main.py`:
   - Add `"format"` and `"lint"` to `_COMMAND_SPECS`.
   - In `_delegate`, forward `command_name` in args when routing to `devops_cli.commands.ci`.
3. `src/devops_cli/lang/en/help.py`:
   - Update descriptions for `format`, `lint`, and CI fix options.
4. `tests/test_ci.py`:
   - Update test expectations and add tests for default formatting, default linting fixes, and `--check` options.
5. `tests/test_all_commands_help_dryrun.py`:
   - Add entries for `format` and `lint` help and dry-run tests.

---

## 3. Progress Tracker

- [x] Grounding & Issue Creation ([#158](https://github.com/dan-petty/devops-cli/issues/158))
- [x] Dedicated Topic Branch (`feat/automatic-formatting-and-linting`)
- [x] Move `_layouts/` and `assets/` to `docs/` for Jekyll / GitHub Pages compliance
- [x] Test-First Specification in `tests/test_ci.py` and `tests/test_all_commands_help_dryrun.py`
- [x] Implementation in `src/devops_cli/commands/ci.py`
- [x] Implementation in `src/devops_cli/main.py`
- [x] Documentation synchronization & drift check (`devops docs generate --sync-readme`, `devops docs check`)
- [x] Architectural invariant validation (`tests/test_architectural_invariants.py`)
- [x] Quality gate verification (`devops ci`)
- [x] Pull Request authoring & CI monitoring ([#159](https://github.com/dan-petty/devops-cli/pull/159))
- [x] Address PR #159 review feedback (executor non-blocking cleanup, leaf alias introspection, Jekyll links and default layout)
