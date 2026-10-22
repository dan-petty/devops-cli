# Task: Delete the Dependency-Manifest Parsers, Vault Transit Helpers and Orphan Core Modules Nothing Calls (#1841)

**Issue**: [#1841](https://github.com/dan-petty/devops-cli/issues/1841)
**Scope**: scope/security, scope/core
**Feasibility**: At release/v0.2.39 5b72063e, `git grep` over the whole repository for every deleted name (`extract_dependencies_from_text`, the five `_extract_*_dependencies` parsers, `_find_package_line`, `transit_encrypt`, `transit_decrypt`, `CallableProvider`, `ProcessExecutionPipeline`, `ProcessExecutionResult`, `cli_command_handler`, `_record_success_metrics`, `_record_error_metrics`, `CONST_VAULT_PATH_TRANSIT_ENCRYPT`, `CONST_VAULT_PATH_TRANSIT_DECRYPT` and `CONST_SECRET_PROVIDER_TOOL`) found, in `src`, `tests`, `k8s` and `.github`, only the definitions, the export maps (`security/__init__.py`, `core/__init__.py`, `security/secrets.py`'s `__all__`) and the tests written for them. In documents it found `docs/SELF_IMPROVEMENT.md`, whose calibration record named `cli_command_handler` and `command_decorator.py:93` in two rows and is corrected here, and records of what was delivered or released then that stay as written: `CHANGELOG.md`, `docs/agent/archive/historical-phases-1-to-50.md` and the delivered task files `task-205`, `task-311`, `task-709`, `task-718`, `task-921` and `task-952` (task files record each item as it was delivered, and no other item edits them). No `@cli_command_handler` decorator is applied anywhere, no module under `commands/`, `server/` or `main.py` imports `core.process_pipeline` or `core.command_decorator`, and the last caller of `extract_dependencies_from_text` left with `pipeline.py` in v0.2.38 (#1799), which scans lockfiles with osv-scanner. The metric names the deleted modules recorded (`cli.command.*`, `subprocess.execution.duration_seconds`) appear in no dashboard, rule or document; the dashboards read `devops_cli_command_total` and `devops_cli_command_duration_seconds` from `main.py`. `run_subprocess` (`core/process.py`) already injects `TRACEPARENT` and sanitises the command it records, so nothing the pipeline did is lost. `packaging`, `tomllib` and `json` stay in use elsewhere, so no dependency or lockfile entry changes, and `DependencySpec` stays because the review pipeline still builds and renders it (#771 owns the now-empty `file_deps` chain). The swallowed-failure ratchet was run with `--lower` and moved `security/secrets.py` from 4 to 3, the one `except Exception` that `CallableProvider` carried.

## Description

Nothing replaces what is deleted: it has no caller, so it is removed under the pre-1.0 rule against zombie code.

- `security/reference_extractor.py` keeps its network-reference extractors and loses the pip, pyproject, package.json, Cargo and go.mod dependency parsers, `extract_dependencies_from_text`, `_find_package_line`, the `packaging.requirements` import, the `DependencySpec` import and the `__all__` entry. The module docstring names only network references.
- `security/vault_lease.py` loses `transit_encrypt` and `transit_decrypt`, and `config/constants.py` loses the two Transit path constants only they used. `VaultLeaseError`'s docstring, and the `docs/ERRORS.md` row generated from it, no longer name a Transit call.
- `security/secrets.py` loses `CallableProvider` and `CONST_SECRET_PROVIDER_TOOL`, the audit name only it carried.
- `core/process_pipeline.py` and `core/command_decorator.py` are deleted with their export-map entries in `core/__init__.py`.
- The tests written only for these (`tests/test_process_pipeline.py`, `tests/test_command_decorator.py`, `tests/test_consolidation_cli_errors.py`, the seven dependency-extraction tests in `tests/test_reference_extractor.py`, and the `CallableProvider` and Transit tests in `tests/test_secret_resolution.py`) are deleted. The one surviving test that built a `CallableProvider`, `test_providers_satisfy_the_protocol`, keeps its other four providers.
- `docs/SELF_IMPROVEMENT.md`'s calibration record of session `20260928-201857` loses the row that remediated `cli_command_handler`, and the row of session `20260930-133320` that cited `command_decorator.py:93` keeps its verdict on exception class names as metric labels without naming the deleted file or function.
- `ai_code_review.md` in the knowledge base described the static scan as "dependency extraction with OSV advisories"; it now says what #1799 made it, an offline osv-scanner scan of lockfiles.

## Acceptance Criteria

- [x] `extract_dependencies_from_text` and its five extractors, `transit_encrypt`, `transit_decrypt`, `CallableProvider`, `ProcessExecutionPipeline`, `ProcessExecutionResult` and `cli_command_handler` are deleted with every test that existed only for them; a `git grep` of `src` and `tests` for those names returns nothing.
- [x] `security/__init__.py` and `core/__init__.py` list no deleted name, and `tests/test_public_export_surface.py` passes.
- [x] The other tests in `tests/test_reference_extractor.py` and `tests/test_secret_resolution.py` pass; the only edit to a surviving test is the one tuple entry in `test_providers_satisfy_the_protocol`.
- [x] The constants, the exception docstring and the generated `docs/ERRORS.md` row, the ratchet ceiling and the knowledge-base line that only the deleted code made true are removed or corrected.

## Deliverables

- [x] Deletions in `src/devops_cli/security/`, `src/devops_cli/core/` and `src/devops_cli/config/constants.py`, and the export maps they were listed in.
- [x] The dead tests deleted, `tests/fixtures/swallowed_failures_ceilings.json` lowered, `docs/ERRORS.md` regenerated and `docs/SELF_IMPROVEMENT.md` corrected.
