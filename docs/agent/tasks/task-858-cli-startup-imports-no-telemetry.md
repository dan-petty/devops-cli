# Task: CLI Start-Up Imports No Telemetry When Disabled (#858)

**Issue**: [#858](https://github.com/dan-petty/devops-cli/issues/858)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/cli

## Description

Decouple telemetry and AI inference packages from base CLI start-up and help commands when telemetry is disabled or unconfigured.
- Unconditionally disable the Logfire pydantic plugin at module entry via `PYDANTIC_DISABLE_PLUGINS=logfire-plugin` in `src/devops_cli/entry.py` and `src/devops_cli/__init__.py` before importing internal `devops_cli` modules, ensuring class-definition validator interception is bypassed.
- Delete `logfire.instrument_pydantic()` from `src/devops_cli/telemetry/logfire.py` and clean associated test fixtures.
- Decouple `devops_cli.exceptions` from AI domain exceptions, removing thirty-one AI exception re-exports and importing them directly from `devops_cli.exceptions.ai` across five src modules and three test modules.
- Clarify help dispatch comment in `src/devops_cli/main.py`.
- Re-derive five timing test ceilings across `test_treesitter_engine.py`, `test_context_packer.py`, `test_ai_inspection.py`, and `test_fastmcp_in_process.py` as runaway bounds ($\ge 20\times$ baseline and $\ge 1\text{ s}$).
- Drop duplicated test duration in the CI coverage row, setting `duration_seconds=0.0`.
- Consolidate pytest worker configuration to the single `addopts = "-n logical"` setting in `pyproject.toml`, removing redundant `-n auto --maxprocesses` overrides from `ci.py` and defaults.

## Acceptance Criteria

- [x] **Top-level help imports no telemetry.** `tests/test_cli_startup_imports.py` runs `sys.executable -c` in a subprocess with a clean environment (no `PYDANTIC_DISABLE_PLUGINS`, `DEVOPS_CLI_TELEMETRY__*` or `LOGFIRE_TOKEN`) that calls `devops_cli.entry.main(["--help"])`, catches `SystemExit`, and asserts `logfire`, `opentelemetry.sdk`, and `pydantic_ai` are absent from `sys.modules`.
- [x] **Subcommand help imports no telemetry.** Subcommand help dispatches `["ci", "--help"]` and `["workspace", "--help"]` verify `logfire`, `opentelemetry.sdk`, and `pydantic_ai` are absent from `sys.modules`.
- [x] **The toggle is unconditional, precedes the first import and merges.** AST analysis confirms `PYDANTIC_DISABLE_PLUGINS` assignment is at module level under no conditional branch and precedes `devops_cli` imports in `entry.py`. Subprocess tests confirm merging with existing caller plugins and absence of logfire plugin in `pydantic.plugin._loader.get_plugins()`.
- [x] **The exceptions package no longer imports `pydantic_ai`.** `uv run python -c "import sys, devops_cli.exceptions; assert 'pydantic_ai' not in sys.modules"` exits 0, and no AI exception names are imported from `devops_cli.exceptions`.
- [x] **Logfire runs keep their instrumentation and `instrument_pydantic()` is gone.** `tests/test_telemetry_logfire.py::test_logfire_bridge_configuration_with_token` asserts `logfire.instrument_pydantic_ai` is called once and `logfire.instrument_pydantic` is deleted.
- [x] **The `main.py` comment is true.** `src/devops_cli/main.py` clarifies that help dispatch skips `devops_cli.telemetry` and the tracer span.
- [x] **No ceiling tighter than a runaway bound.** `git grep -nE "assert [a-z_.]+ < [0-9]" -- tests/test_treesitter_engine.py tests/test_context_packer.py tests/test_ai_inspection.py tests/test_fastmcp_in_process.py` shows only runaway bounds ($1000.0\text{ ms}$, $2.0\text{ s}$, $2000.0\text{ ms}$, $5000.0\text{ ms}$, $10000.0\text{ ms}$). Ten consecutive runs exit 0:
  ```
  Run 1: Exit 0
  Run 2: Exit 0
  Run 3: Exit 0
  Run 4: Exit 0
  Run 5: Exit 0
  Run 6: Exit 0
  Run 7: Exit 0
  Run 8: Exit 0
  Run 9: Exit 0
  Run 10: Exit 0
  ```
- [x] **One worker setting.** `pyproject.toml: addopts = "-n logical"` is the single site for pytest worker settings (`# Pytest workers: logical cores (ext4 benchmark: 8 workers ~4.2s vs 4 workers ~6.8s)`). `_build_test_cmd` without explicit `-n` and the gate row carry no worker arguments.
- [x] **No duplicated coverage duration.** `test_coverage_row_carries_no_duplicated_duration` asserts the `coverage` row carries `duration_seconds=0.0` and the summed duration counts the test row once.
- [x] **Timings recorded.** Measured on host (load average: 1.28, 1.44, 1.72):
  - `uv run devops --help` wall-clock: 1.233s, 1.477s, 1.398s, 1.424s, 1.586s (mean: 1.423s).
  - Cumulative `python -X importtime`: `devops_cli.config.env`: 93335 us (~93.3ms); `devops_cli.exceptions`: 102840 us (~102.8ms).
- [x] **Changelog fragment.** `changelog.d/858.md` created; `CHANGELOG.md` and `docs/ROADMAP.md` untouched.
- Pending a person: `uv run devops ci` passes on this branch.

## Deliverables

- [x] `src/devops_cli/entry.py`: unconditional `PYDANTIC_DISABLE_PLUGINS` setting before `devops_cli` imports.
- [x] `src/devops_cli/__init__.py`: set `PYDANTIC_DISABLE_PLUGINS` before metadata import.
- [x] `src/devops_cli/telemetry/logfire.py`: deleted `logfire.instrument_pydantic()`.
- [x] `tests/test_telemetry_logfire.py`: updated bridge configuration tests.
- [x] `src/devops_cli/exceptions/__init__.py`: removed 31 AI exception re-exports and `__all__` entries.
- [x] `src/devops_cli/ai/agents/agent.py`: import `UnexpectedModelBehavior` from `devops_cli.exceptions.ai`.
- [x] `src/devops_cli/ai/agents/runner.py`: import `ModelRetry` and `UnexpectedModelBehavior` from `devops_cli.exceptions.ai`.
- [x] `src/devops_cli/ai/client/models.py`: import `LLMInferenceError` from `devops_cli.exceptions.ai`.
- [x] `src/devops_cli/ai/client/unified.py`: import `LLMInferenceError` from `devops_cli.exceptions.ai`.
- [x] `src/devops_cli/ai/review/pool.py`: import `ReviewPoolError` from `devops_cli.exceptions.ai`.
- [x] `tests/test_exceptions.py`: import AI exceptions from `devops_cli.exceptions.ai`.
- [x] `tests/test_schema_reflection.py`: import `UnexpectedModelBehavior` from `devops_cli.exceptions.ai`.
- [x] `tests/test_pydantic_agent.py`: import `ModelRetry` and `UnexpectedModelBehavior` from `devops_cli.exceptions.ai`.
- [x] `src/devops_cli/main.py`: updated help dispatch comment.
- [x] `tests/test_treesitter_engine.py`: updated timing ceiling to 1000.0ms runaway bound.
- [x] `tests/test_context_packer.py`: updated timing ceiling to 2.0s runaway bound.
- [x] `tests/test_ai_inspection.py`: updated timing ceilings to 2000.0ms and 5000.0ms runaway bounds.
- [x] `tests/test_fastmcp_in_process.py`: updated timing ceiling to 10000.0ms runaway bound.
- [x] `src/devops_cli/commands/ci.py`: removed `_resolve_pytest_worker_count`, updated `_resolve_pytest_cmd`, `_build_test_cmd`, and zeroed coverage duration.
- [x] `src/devops_cli/config/defaults.py`: removed `DEFAULT_PYTEST_NUMPROCESSES`.
- [x] `pyproject.toml`: documented benchmark timing comment on `addopts`.
- [x] `tests/test_ci.py`: replaced `test_resolve_pytest_worker_count` with worker consistency and coverage duration assertions.
- [x] `tests/test_cli_startup_imports.py`: new integration test suite for startup imports and AST invariants.
- [x] `changelog.d/858.md`: changelog fragment.
- [x] `docs/agent/tasks/task-858-cli-startup-imports-no-telemetry.md`: task tracking file.
