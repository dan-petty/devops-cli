# Task: Structural Startup Import Budget Invariant to Machine Load (#1687)

**Issue**: [#1687](https://github.com/dan-petty/devops-cli/issues/1687)
**Scope**: scope/ci
**Feasibility**: Verified that `-X importtime` module counts (unique modules and `devops_cli` modules) are 100% deterministic and invariant across runs and under CPU-bound worker load (456 total modules for `--help`, 477 for `--version`, 943 for `ai --help`), while importing an extra heavy package (`pydantic_ai`) inflates unique imports to 2085, breaching the structural limit and triggering forbidden heavy module detection.

## Description

The startup import budget test suite (`tests/test_cli_startup_imports.py`) previously measured cumulative wall-clock seconds reported by `-X importtime`, requiring an exclusive filesystem lock (`.data/importtime.lock`) and failing intermittently when running on a multi-core machine under heavy concurrent load (such as parallel test workers or shared CI hosts).

This deliverable (#1687) makes the startup import gate structural and deterministic:
- Replaces wall-clock execution time assertions on `--help`, `--version`, and `<command> --help` with deterministic structural assertions based on unique module counts and `devops_cli` module counts.
- Defines configurable structural ceilings in `src/devops_cli/config/defaults.py`:
  - `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION = 550` (actual: 456 for `--help`, 477 for `--version`)
  - `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION = 75` (actual: 38 for `--help`, 51 for `--version`)
  - `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP = 1100` (actual: 943 for `ai --help`, 904 for `review --help`, 763 for `k8s --help`)
  - `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP = 250` (actual: 207 for `ai --help`, 168 for `review --help`)
- Preserves forbidden heavy module enforcement (`CONST_CLI_HEAVY_MODULES`) across all startup paths.
- Removes obsolete wall-clock seconds constants (`CONST_STARTUP_IMPORT_BUDGET_MAIN_SECONDS`, `CONST_STARTUP_IMPORT_BUDGET_HELP_SECONDS`) and the cross-process lock file (`.data/importtime.lock`), enabling parallel test execution under `pytest -n` without serialization contention.
- Formats and outputs an informational diagnostic report of the slowest imported modules so performance regressions remain visible without flaking on CPU scheduling jitter.
- Adds an offline test verifying that importing an extra heavy package fails the structural budget (`test_startup_structural_budget_fails_when_extra_heavy_package_imported`).
- Adds an offline test verifying that startup module counts remain invariant and within budget under high CPU load (`test_startup_structural_budget_passes_under_cpu_load`).

## Acceptance Criteria

- [x] Startup import budget tests verify structural limits (unique module count, `devops_cli` module count, and forbidden heavy modules) rather than wall-clock seconds.
- [x] Budget limits are defined in `src/devops_cli/config/defaults.py` and exported via `devops_cli.config`.
- [x] An extra heavy package imported on startup fails the structural budget and forbidden module checks.
- [x] Structural module counts remain invariant and pass reliably under high CPU load.
- [x] Informational diagnostic timing reports display the slowest imports.
- [x] Cross-process lock file and obsolete wall-clock seconds constants removed.
- [x] Changelog fragment `changelog.d/1687.md` added.

## Deliverables

- [x] Added structural budget limits in `src/devops_cli/config/defaults.py` and re-exported in `src/devops_cli/config/__init__.py`.
- [x] Removed obsolete wall-clock seconds constants from `src/devops_cli/config/constants.py`.
- [x] Refactored `tests/test_cli_startup_imports.py` to use `_measure_startup_imports` and structural budget assertions.
- [x] Added `test_startup_structural_budget_fails_when_extra_heavy_package_imported` and `test_startup_structural_budget_passes_under_cpu_load`.
- [x] Added `docs/agent/tasks/task-1687-startup-import-budget-structural.md`.
- [x] Added `changelog.d/1687.md`.
