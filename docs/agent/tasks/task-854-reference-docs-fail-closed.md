# Task #854: Reference Docs Fail Closed and Describe the Real Surface

**Issue**: [#854](https://github.com/dan-petty/devops-cli/issues/854)
**Status**: Done
**Scope**: `src/devops_cli/docs/generator.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `docs/`, `tests/test_docs.py`
**Feasibility**: Verified against `src/devops_cli/docs/generator.py` (`_introspect_single_group`, `_fetch_mcp_tools`, `_extract_mcp_prop_type`, `generate_configuration_docs`, `generate_error_catalog_docs`), `src/devops_cli/config/settings.py` (`Settings.model_fields` and `_find_project_config_path`), and `config.example.yaml`.

## Checklist
- [x] Remove catch-and-continue fallbacks in `DocGenerator._introspect_single_group`, `DocGenerator._fetch_mcp_tools`, and `DocGenerator._import_all_exception_modules` so introspection or import failures raise `RuntimeError` naming the module and stating that a missing optional dependency now fails the docs stage, by design.
- [x] Preserve group-callback options and usage on `CommandGroupDoc` and render them in `docs/commands/<group>.md` and `docs/CLI_REFERENCE.md` (`devops ci` lists `--check`, `--only`, and `--skip`; `devops review` lists `--explain`).
- [x] Render MCP array item types (`array[<type>]`) and enum values (`<type> (<v1>, <v2>, ...)`) in `_extract_mcp_prop_type` and `docs/MCP_TOOLS.md`.
- [x] Move project configuration file candidates to `CONST_PROJECT_CONFIG_CANDIDATES` in `src/devops_cli/config/constants.py`, use it in `_find_project_config_path` and `DocGenerator.generate_configuration_docs`, and iterate over `Settings.model_fields` in `generate_configuration_docs`.
- [x] Import all `devops_cli.exceptions.*` and domain exception modules in `DocGenerator.generate_error_catalog_docs`, instantiate each `DevOpsCLIError` subclass with its required constructor arguments so `ChecksumMismatchError`, `SecretExposureError`, `ToolDownloadError`, and `MemoryOperationConflictError` render their real error and exit codes, and add `CONST_EXIT_USAGE` and `CONST_EXIT_CANCELLED` to `src/devops_cli/config/constants.py`.
- [x] Add unit tests in `tests/test_docs.py` covering fail-closed group and MCP introspection, group-callback options, MCP array/enum parameter types, `CONFIGURATION.md` and `ERRORS.md` accuracy, and walking `config.example.yaml` against `Settings`.
- [x] Regenerate all reference documentation via `uv run devops docs generate --sync-readme` and verify `uv run devops docs check`.
