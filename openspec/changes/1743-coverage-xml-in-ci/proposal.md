# Proposal

## Why

Issue #1743: after the last test, the test row of `devops ci` writes two coverage reports, one after another, on the gate's critical path. Only CI's `Changed-Line Coverage` step reads one of them, `coverage.xml`. The coverage clean-up also deletes the combined data file `.data/.coverage` once it is more than 60 s old, although its docstring says it removes worker files only.

## What Changes

- `_resolve_pytest_cmd` in `src/devops_cli/commands/ci.py` no longer asks pytest-cov for an XML report. The test row keeps `--cov=src` and the `term-missing` report, so the 85% floor (`fail_under`) and the missing-lines list stay. `devops ci coverage`, which runs the same command, also writes no XML.
- `_clean_coverage_artifacts` removes only the `.coverage.*` worker data files, so `.data/.coverage` stays for `devops ci coverage --build-index` and for CI. The removal of a root `coverage.xml` goes: since `[tool.coverage.xml]` sends the report to `.data/coverage.xml`, nothing writes a root file.
- The `Changed-Line Coverage` step of `.github/workflows/ci.yml` runs `uv run coverage xml -q` before diff-cover, so diff-cover still reads `.data/coverage.xml`. The step runs on pull requests only, so a push to `main` writes no XML.
- The gate's command and the files it keeps are observable, so the change carries a spec delta: the new capability `ci-coverage-reports`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ci-coverage-reports`: which coverage reports and data files the test row writes and keeps, and where CI gets the XML report.

## Impact

- `src/devops_cli/commands/ci.py`, `.github/workflows/ci.yml`, `tests/test_ci.py`.

## Feasibility

Measured on origin/main `cabfcd43` (2026-10-29) on the shared devcontainer host, 16 CPUs:

- `_resolve_pytest_cmd` returned `--cov=src --cov-report=term-missing --cov-report=xml`, and the only reader of `.data/coverage.xml` in the repository is the diff-cover command of the `Changed-Line Coverage` step (`git grep coverage.xml` over `src`, `tests`, `.github` and the docs).
- `_clean_coverage_artifacts` globbed `.coverage*` in the tree and in `.data/`. No worktree on this host held a `.data/.coverage` before this measurement: the clean-up at the start of each later gate had removed it.
- A full run of the suite with `--cov=src --cov-report=` (12,460 tests, 533 s at load 22 to 30) left a combined data file. On that file, each report alone, three runs each at load 13 to 29:

| Command | Run 1 | Run 2 | Run 3 |
| :--- | ---: | ---: | ---: |
| `coverage report -m` | 30.8 s | 33.9 s | 26.8 s |
| `coverage xml` | 24.7 s | 25.9 s | 21.1 s |
| `coverage --version` (start-up of `uv run` and coverage) | 1.8 s | 1.6 s | 2.2 s |

  pytest-cov writes the reports in its own process, so the XML pass costs the test row about 19 to 24 s at this load. The issue measured 8.8 s at load 23 and 55 to 98 s for the report phase at load 30 to 40.
- coverage.py's `coverage xml` reads the combined data file that `[tool.coverage.run] data_file` names, so CI gets the same report from the data that the gate keeps.

## Existing Tool Considered

coverage.py and pytest-cov cover all of it: pytest-cov's `--cov-report` options select the reports, and `coverage xml` writes the XML from the combined data. Nothing new is built. The change deletes the `--cov-report=xml` argument and the root `coverage.xml` removal.
