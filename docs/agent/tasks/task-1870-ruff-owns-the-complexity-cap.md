# Task: Ruff's Own Flags Protect the Complexity Cap, and the Configuration-Escape Tests and Key Allowlists Are Deleted (#1870)

**Issue**: [#1870](https://github.com/dan-petty/devops-cli/issues/1870)
**Scope**: scope/ci
**Feasibility**: Ruff 0.16.8 ran on a scratch project. A nested `ruff.toml` hides a function of complexity 13. The flag `--config pyproject.toml` brings the finding back. An ignore file also hides the function. The flag `--no-respect-gitignore` brings it back. The CI checkout is not clean, because `uv sync` creates `.venv` there. The `exclude` key of `pyproject.toml` removes the default exclusions of Ruff. On a copy of this tree, one bad file in `.venv` gave 4 errors with the flag. A test of the files that Ruff walks replaces the flag in CI.

## Description

Ruff alone holds the complexity cap of 10 (C901). The flags and settings of Ruff replace the tests that copied its configuration rules.

- The lint row of `devops ci` (`cmd` and `fix_cmd`) and the `ruff-check` pre-commit hook run `ruff check --config pyproject.toml`. This file is the only Ruff configuration. No nearer file can outrank it.
- `tests/test_ruff_complexity_cap.py` is new. It holds three checks and their negative controls.
- The settings test reads `ruff check --show-settings`. C901, PGH004, RUF100 and TID251 must be enabled. The cap must be 10. No per-file waiver and no lint exclusion can exist. The four banned socket APIs must stay listed.
- The walk test asks git for the tracked Python sources. It asks `ruff check --show-files` for the files that the gate walks. It fails for each tracked source that the walk skips.
- On this tree, the walk reaches all 1,090 tracked sources and `pyproject.toml`. The walk test closes the ignore files without the CI flag.
- The invocation test checks every `ruff check` in a `devops ci` row, in the pre-commit configuration and in a `.github` script. Each one must pass `--config pyproject.toml`. Each one may pass no flag other than `--fix`. The test joins a script line that ends in a backslash to the next line before it reads the command.
- The negative controls run in `tmp_path` projects. Six weakened `pyproject.toml` files cover a raised cap, a cap not selected, a cap ignored, a lint exclusion, a dropped banned API and a per-file waiver.
- The test builds each weakened file from the parsed `tool.ruff` table. It changes the table in memory and writes it back with a small TOML writer, because the project has no TOML writer dependency. A round-trip test and a control with no change show that the writer is exact.
- Four configuration files in four places ignore C901. The same tree passes without the flag. Four ignore files hide a tracked source. Seven invocations override the configuration.
- `tests/test_architectural_invariants.py` loses 529 lines and gains 94. The deleted code is the key allowlists, the scans for nested configuration files and ignore files, and the source scan. It is also the dedicated C901 marker counter with its ceiling test, and the table of 38 escape cases.
- The deleted counter read the raw text of `.py`, `.pyi` and `.ipynb` files under `src` and `tests`. The suppression counters read `.py` files only. This task does not claim that the two read the same files.
- `git ls-files` shows no tracked `.pyi` or `.ipynb` file under `src` or `tests`. `test_no_tracked_file_under_the_scanned_roots_is_one_the_suppression_scan_skips` fails when one appears. The first such file must come with a count of its comments over the raw text.
- The suppression counters already count each comment spelling in `.py` files that the deleted code counted. `test_every_ruff_suppression_spelling_is_counted` keeps all 14 spellings as tests of those counters. They are 4 C901 markers and 10 file-level or block directives. The ast-grep network gate stays, as the issue says.
- `src/devops_cli/config/constants.py` loses eight constants that only the deleted code used. They are `CONST_RUFF_TOP_LEVEL_KEYS`, `CONST_RUFF_LINT_KEYS`, `CONST_RUFF_MCCABE_KEYS`, `CONST_RUFF_EXCLUDE`, `CONST_RUFF_CONFIG_FILE_NAMES`, `CONST_RUFF_FILE_EXEMPTION`, `CONST_C901_SUPPRESSION` and `CONST_RUFF_C901_SUPPRESSION_COMMENT`. The file gains `CONST_RUFF_CHECK_GATE_FLAGS`. Five other Ruff constants stay, because a live test still reads each one.
- `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/TESTING.md` and `docs/ROUTINE_TASKS.md` describe the new controls. `AGENTS.md` has 39,948 characters, below its cap of 40,000.
- The old table held 38 cases. 36 of them were escapes. The resolved settings, `--config`, the walk test, the suppression counters or a Ruff error catch 35 of the 36.
- The 36th case, `max-complexity-missing`, is no escape. Ruff defaults to 10, and the new test asserts the resolved value of 10. The 2 cases that the table called clean stay clean.
- Every suppression ceiling equals the count that the collector of `tests/test_architectural_invariants.py` measures on this tree. No ceiling is loose. The `src noqa: C901` ceiling of 25 keeps the `# noqa: C901` markers bounded.

## Acceptance Criteria
- [x] The 38 escape cases no longer exist. The tree still cannot silence C901 through configuration, nested files, ignore files or flags. The negative controls of `tests/test_ruff_complexity_cap.py` show this.
- [x] No deleted symbol has a reference left in `src`, `tests` or the docs. The exceptions are `docs/agent/tasks`, `docs/agent/archive` and `CHANGELOG.md`. `uv run devops docs check` reports every file up to date.
- [x] `ruff check`, `ruff format --check`, `mypy` over `src`, `deptry` and the targeted tests pass. The targeted tests include `tests/test_architectural_invariants.py`, `tests/test_ruff_complexity_cap.py`, `tests/test_swallowed_failures_ratchet.py`, `tests/test_ci.py`, `tests/test_ci_dry_run.py`, `tests/test_workflow_contracts.py` and the tests of `AGENTS.md` claims and task files.
- Pending a person: `uv run devops ci` passes on the delivering tree. This change ran the targeted tests and not the gate.

## Deliverables
- [x] `--config pyproject.toml` in the lint row, its fix row and the `ruff-check` hook.
- [x] The settings test, the walk test, the invocation test and their negative controls.
- [x] The escape tests, the key allowlists and the constants that only they used are deleted.
- [x] A test that fails when a `.pyi` or `.ipynb` file is tracked under `src` or `tests`.
- `--no-respect-gitignore` is not in CI. The CI checkout holds `.venv`, and the walk test replaces the flag.
